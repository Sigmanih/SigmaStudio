# ==============================================================================
# core/training/metrics.py — Storia delle metriche di un run e sua diagnosi
# Sigma Studio v7 — Modular Training Sub-package
# ==============================================================================
"""Cosa sta succedendo davvero dentro un training, letto dal suo log.

Gli script generati emettono una riga `[SIGMA-METRIC] {json}` a ogni logging
step e a ogni valutazione. Qui quelle righe diventano una serie storica, un
riepilogo e — la parte che serve davvero a chi guarda il Monitor — un giudizio:
sta ancora imparando, si e' fermato, o ha cominciato a memorizzare il dataset?

La serie non viene duplicata in un file a parte: `train.log` e' gia' l'artefatto
durevole del job, sopravvive al riavvio di Sigma e non puo' desincronizzarsi da
se' stesso. Rileggerlo costa poco (una riga su cento e' una metrica) e il
risultato viene messo in cache finche' il file non cambia.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

from core.logger import get_logger

log = get_logger(__name__)

METRIC_PREFIX = "[SIGMA-METRIC]"

# Quante valutazioni servono prima di poter dire qualcosa di sensato. Sotto
# questa soglia due punti in salita sono rumore, non overfitting.
_MIN_EVALS_FOR_VERDICT = 3

# Finestra (in frazione della serie) su cui si misura la pendenza recente.
_TREND_WINDOW = 0.25

# La eval loss e' risalita di piu' di questo rispetto al suo minimo: il modello
# ha smesso di generalizzare e sta iniziando a ricalcare i dati di training.
_OVERFIT_RISE = 0.05

# Train loss sotto questa frazione della eval loss: il divario e' troppo ampio
# perche' sia ancora apprendimento utile.
_MEMORIZATION_RATIO = 0.55

# Sotto questa pendenza relativa la loss e' ferma: continuare non aggiunge nulla.
_PLATEAU_SLOPE = 0.005

# Quante volte piu' lenti devono essere gli ultimi step per parlare di
# rallentamento. Un training oscilla sempre un po'; un fattore 3 no.
_SLOWDOWN_FACTOR = 3.0

# Sopra questa pendenza la loss sta salendo abbastanza da non essere rumore.
# Piu' alta della soglia di plateau perche' la loss oscilla sempre un po' e non
# vale la pena gridare al problema a ogni sussulto.
_RISING_SLOPE = 0.05


# --------------------------------------------------------------- descrizioni

# Cosa significa ogni numero, dove dovrebbe stare e quando preoccuparsi.
# Il Monitor lo mostra al passaggio del mouse: sono le stesse soglie che usano
# le diagnosi qui sotto, cosi' spiegazione e verdetto non possono divergere.
METRIC_GUIDE = {
    "loss": {
        "label": "Training loss",
        "what": "Quanto il modello sbaglia sugli esempi che sta vedendo. "
                "E' la quantita' che l'ottimizzatore minimizza.",
        "good": "In discesa, anche lenta. Il valore assoluto conta poco: "
                "dipende da dataset e tokenizer.",
        "bad": "Ferma per centinaia di step (non impara piu'), oppure a zero "
               "(sta ricopiando il dataset a memoria).",
        "optimal": "Discesa continua, senza scalini bruschi.",
    },
    "avg_loss": {
        "label": "Loss media (finestra)",
        "what": "Media della training loss sugli ultimi step: toglie il rumore "
                "che rende illeggibile il valore istantaneo.",
        "good": "Piu' bassa della media della finestra precedente.",
        "bad": "Uguale o piu' alta della finestra precedente.",
        "optimal": "Sempre in calo rispetto alla finestra precedente.",
    },
    "eval_loss": {
        "label": "Validation loss",
        "what": "L'errore su un 5% di dati tenuti da parte, che il modello non "
                "vede mai in training. E' l'unico numero che dice se ha "
                "imparato davvero o solo memorizzato.",
        "good": "Scende insieme alla training loss.",
        "bad": "Risale mentre la training loss continua a scendere: e' "
               "overfitting, il momento di fermarsi.",
        "optimal": "Il minimo della validation loss e' il checkpoint migliore.",
    },
    "perplexity": {
        "what": "exp(validation loss): quante alternative il modello si trova "
                "mediamente a dover distinguere per il token successivo. "
                "Perplexity 1 = certezza assoluta.",
        "label": "Perplexity",
        "good": "In calo. Sotto 10 su un dataset di istruzioni e' buon segno.",
        "bad": "In risalita, oppure sotto 1.5: e' memorizzazione, non "
               "comprensione.",
        "optimal": "Il minimo raggiunto sulla validation, prima della risalita.",
    },
    "gap": {
        "label": "Divario train/validation",
        "what": "Di quanto la training loss e' piu' bassa della validation. "
                "Misura quanto il modello e' avvantaggiato dall'aver gia' "
                "visto quei dati.",
        "good": "Piccolo e stabile.",
        "bad": "In crescita continua: sta imparando gli esempi, non il "
               "compito.",
        "optimal": "Sotto il 20% della validation loss.",
    },
    "learning_rate": {
        "label": "Learning rate",
        "what": "L'ampiezza del passo dell'ottimizzatore. Con lo scheduler "
                "coseno parte alto e scende fino a zero.",
        "good": "Segue la curva prevista dallo scheduler.",
        "bad": "Costante a zero da subito: lo scheduler e' mal configurato e "
               "il modello non si muove piu'.",
        "optimal": "Discesa morbida fino a ~0 alla fine del run.",
    },
    "grad_norm": {
        "label": "Norma del gradiente",
        "what": "Quanto e' grande la correzione che il passo sta applicando ai "
                "pesi.",
        "good": "Stabile, dello stesso ordine di grandezza per tutto il run.",
        "bad": "Picchi improvvisi o NaN: il training sta divergendo.",
        "optimal": "Sotto la soglia di clipping, senza toccarla di continuo.",
    },
}


# ------------------------------------------------------------------- lettura

_CACHE: dict[str, tuple[tuple[int, float], list[dict]]] = {}


def read_metric_history(log_path) -> list[dict]:
    """Every `[SIGMA-METRIC]` record a run has emitted so far, in order."""
    path = Path(log_path)
    if not path.exists():
        return []
    try:
        stat = path.stat()
    except OSError:
        return []

    stamp = (stat.st_size, stat.st_mtime)
    cached = _CACHE.get(str(path))
    if cached and cached[0] == stamp:
        return cached[1]

    records: list[dict] = []
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as handle:
            for line in handle:
                start = line.find(METRIC_PREFIX)
                if start < 0:
                    continue
                try:
                    record = json.loads(line[start + len(METRIC_PREFIX):].strip())
                except ValueError:
                    continue
                if isinstance(record, dict):
                    records.append(record)
    except OSError as exc:
        log.warning("lettura metriche da %s: %s", path, exc)
        return []

    _CACHE[str(path)] = (stamp, records)
    return records


#: Riga con cui `start_training_job` apre il log a ogni avvio. Un job fermato e
#: ripreso scrive nello stesso file, quindi senza questo taglio la serie
#: incollerebbe di fila run diversi: la loss "risalirebbe" di colpo al valore
#: iniziale del giro nuovo, e tendenza e media direbbero il falso.
RUN_HEADER = "===== Sigma Studio Training Lab ====="


def split_runs(log_path) -> list[list[dict]]:
    """Metric records grouped by run, oldest first."""
    path = Path(log_path)
    if not path.exists():
        return []
    runs: list[list[dict]] = []
    current: list[dict] = []
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as handle:
            for line in handle:
                if RUN_HEADER in line:
                    if current:
                        runs.append(current)
                    current = []
                    continue
                start = line.find(METRIC_PREFIX)
                if start < 0:
                    continue
                try:
                    record = json.loads(line[start + len(METRIC_PREFIX):].strip())
                except ValueError:
                    continue
                if isinstance(record, dict):
                    current.append(record)
    except OSError as exc:
        log.warning("lettura run da %s: %s", path, exc)
        return []
    if current:
        runs.append(current)
    return runs


def _series(history: list[dict], key: str) -> list[tuple[float, float]]:
    """(step, value) pairs for one metric, skipping records that lack it."""
    out = []
    for record in history:
        value = record.get(key)
        if value is None:
            continue
        try:
            number = float(value)
        except (TypeError, ValueError):
            continue
        if math.isnan(number) or math.isinf(number):
            continue
        out.append((float(record.get("step", len(out))), number))
    return out


def _relative_slope(points: list[tuple[float, float]]) -> float | None:
    """Recent trend as a fraction of the current value.

    Normalizzare sul valore corrente rende il numero confrontabile fra dataset
    diversi: una loss che scende da 8 a 7 e una che scende da 0.8 a 0.7 stanno
    migliorando allo stesso ritmo, e vanno giudicate allo stesso modo.
    """
    if len(points) < 4:
        return None
    window = max(4, int(len(points) * _TREND_WINDOW))
    tail = points[-window:]
    first = sum(v for _, v in tail[: len(tail) // 2]) / max(1, len(tail) // 2)
    last = sum(v for _, v in tail[len(tail) // 2:]) / max(1, len(tail) - len(tail) // 2)
    if first == 0:
        return None
    return (last - first) / abs(first)


def _throughput_drop(history: list[dict]) -> float | None:
    """Di quante volte gli ultimi step sono piu' lenti di quelli iniziali.

    Si legge da `elapsed_s`, che e' cumulativo: la differenza fra due record
    consecutivi e' il tempo di quello step.
    """
    stamps = [(r.get("step"), r.get("elapsed_s")) for r in history
              if isinstance(r.get("elapsed_s"), (int, float)) and r.get("step") is not None]
    if len(stamps) < 30:
        return None
    deltas = [(b[1] - a[1]) / max(1, b[0] - a[0]) for a, b in zip(stamps, stamps[1:])]
    deltas = [d for d in deltas if d > 0]
    if len(deltas) < 20:
        return None

    def median(values):
        ordered = sorted(values)
        return ordered[len(ordered) // 2]

    window = max(5, len(deltas) // 10)
    early = median(deltas[:window])
    late = median(deltas[-window:])
    return (late / early) if early > 0 else None


def summarize(history: list[dict]) -> dict:
    """Aggregates the Monitor shows next to the chart."""
    train = _series(history, "loss")
    evals = _series(history, "eval_loss")
    window = max(1, len(train) // 10)

    best_eval = min(evals, key=lambda p: p[1]) if evals else None
    summary = {
        "points": len(train),
        "eval_points": len(evals),
        "last_loss": train[-1][1] if train else None,
        "min_loss": min(v for _, v in train) if train else None,
        "avg_loss": (sum(v for _, v in train[-window:]) / len(train[-window:])
                     if train else None),
        "last_eval_loss": evals[-1][1] if evals else None,
        "best_eval_loss": best_eval[1] if best_eval else None,
        "best_eval_step": best_eval[0] if best_eval else None,
        "trend": _relative_slope(train),
        "eval_trend": _relative_slope(evals),
    }
    if summary["last_eval_loss"] is not None:
        # exp() esplode su loss grandi e il numero perde significato: oltre 20
        # la perplexity e' comunque "il modello non ha idea".
        summary["perplexity"] = (math.exp(min(summary["last_eval_loss"], 20.0))
                                 if summary["last_eval_loss"] > 0 else None)
        summary["best_perplexity"] = (math.exp(min(summary["best_eval_loss"], 20.0))
                                      if summary["best_eval_loss"] else None)
        if summary["last_loss"] is not None:
            summary["gap"] = summary["last_eval_loss"] - summary["last_loss"]
    return summary


# ------------------------------------------------------------------ diagnosi

def _verdict(code, level, title, detail, action=""):
    return {"code": code, "level": level, "title": title,
            "detail": detail, "action": action}


def diagnose(history: list[dict]) -> list[dict]:
    """Plain-language verdicts on how the run is going.

    L'ordine conta: le diagnosi che chiedono di fermare il run vengono prima di
    quelle che dicono di continuare, perche' il Monitor mostra la prima come
    stato principale.
    """
    train = _series(history, "loss")
    evals = _series(history, "eval_loss")
    verdicts: list[dict] = []

    if not train:
        return [_verdict("no_data", "info", "Nessuna metrica ancora",
                         "Il run non ha ancora emesso un logging step.")]

    # --- divergenza: batte tutto il resto ---------------------------------
    raw = [record.get("loss") for record in history if "loss" in record]
    if any(value is None or (isinstance(value, float) and math.isnan(value)) for value in raw):
        verdicts.append(_verdict(
            "diverged", "critical", "Training divergente",
            "La loss e' diventata NaN: i gradienti sono esplosi e i pesi non "
            "sono piu' recuperabili.",
            "Ferma il run. Abbassa il learning rate (di solito basta dividerlo "
            "per 10) e riparti dall'ultimo checkpoint buono."))
        return verdicts

    trend = _relative_slope(train)

    # --- la scheda non ce la fa ------------------------------------------
    # Una VRAM richiesta oltre quella fisica non da' errore su Windows: il
    # driver riversa in memoria di sistema e il training continua, dieci o
    # venti volte piu' lento. Senza dirlo, l'unico segnale e' un ETA che
    # cresce, e chi guarda pensa a un rallentamento passeggero.
    used = _series(history, "vram_gb")
    capacity = _series(history, "vram_total_gb")
    if used and capacity:
        peak = max(v for _, v in used)
        limit = capacity[-1][1]
        if limit and peak > limit:
            verdicts.append(_verdict(
                "vram_overcommit", "critical", "VRAM esaurita: la scheda sta paginando",
                f"Il run ha chiesto {peak:.1f} GB su una scheda da {limit:.1f} GB. "
                "Quello che non ci sta finisce in memoria di sistema, e ogni step "
                "paga il trasferimento sul bus.",
                "Ferma il run e dimezza il batch, oppure riduci il contesto: "
                "l'occupazione cresce con il prodotto dei due. A parita' di batch "
                "effettivo, alza il gradient accumulation."))

    slowdown = _throughput_drop(history)
    if slowdown and slowdown >= _SLOWDOWN_FACTOR:
        verdicts.append(_verdict(
            "slowdown", "warning", "Il training e' rallentato",
            f"Gli ultimi step vanno {slowdown:.0f} volte piu' lenti di quelli "
            "iniziali. Il tempo stimato alla fine non e' piu' quello di prima.",
            "Se la VRAM e' al limite e' paginazione: conviene fermarsi. "
            "Altrimenti guarda se un altro processo sta usando la GPU."))

    # --- overfitting: la eval risale mentre la train scende ----------------
    if len(evals) >= _MIN_EVALS_FOR_VERDICT:
        best = min(v for _, v in evals)
        latest = evals[-1][1]
        rise = (latest - best) / abs(best) if best else 0.0
        if rise > _OVERFIT_RISE and (trend is None or trend < 0):
            best_step = min(evals, key=lambda p: p[1])[0]
            verdicts.append(_verdict(
                "overfitting", "warning", "Overfitting in corso",
                f"La validation loss e' risalita del {rise * 100:.1f}% dal suo "
                f"minimo ({best:.4f} allo step {int(best_step)}) mentre la "
                "training loss continua a scendere: il modello sta migliorando "
                "solo sui dati che ha gia' visto.",
                f"Ferma il run e tieni il checkpoint dello step {int(best_step)}. "
                "Per andare oltre servono piu' dati, non piu' epoche."))

    # --- memorizzazione: divario train/eval troppo ampio -------------------
    if evals and train:
        last_eval, last_train = evals[-1][1], train[-1][1]
        if last_eval > 0 and last_train < last_eval * _MEMORIZATION_RATIO:
            verdicts.append(_verdict(
                "memorizing", "warning", "Sta imparando il dataset a memoria",
                f"La training loss ({last_train:.4f}) e' molto piu' bassa della "
                f"validation ({last_eval:.4f}): il modello riconosce gli esempi "
                "invece di aver imparato il compito.",
                "Riduci le epoche o il rank della LoRA, oppure allarga il "
                "dataset. Il modello cosi' generalizza male."))

    # --- plateau ----------------------------------------------------------
    # "Sta ancora imparando" e' vero anche mentre il modello va in overfitting —
    # la training loss scende comunque — ma affiancarlo a un avviso di
    # overfitting darebbe il messaggio opposto a quello giusto. Se c'e' gia' un
    # problema, la pendenza della training loss non e' piu' la notizia.
    if any(v["level"] in ("warning", "critical") for v in verdicts):
        pass
    elif trend is not None and trend > _RISING_SLOPE and len(train) > 20:
        # Caso che prima cadeva nel vuoto: la pendenza positiva non rientrava
        # ne' in "plateau" ne' in "sta imparando", e il verdetto restava muto
        # proprio quando c'era la cosa piu' importante da dire.
        verdicts.append(_verdict(
            "rising", "warning", "La loss sta risalendo",
            f"Nella finestra recente la training loss e' salita del "
            f"{trend * 100:.1f}%: il run sta peggiorando, non migliorando.",
            "Di solito e' un learning rate troppo alto per questa fase. "
            "Ferma, dimezzalo e riparti dall'ultimo checkpoint buono. Se la "
            "loss oscilla senza salire davvero, alza il batch effettivo "
            "(gradient accumulation) per ridurre il rumore."))
    elif trend is not None and abs(trend) < _PLATEAU_SLOPE and len(train) > 20:
        verdicts.append(_verdict(
            "plateau", "info", "La loss si e' fermata",
            f"Negli ultimi step la training loss si e' mossa dello "
            f"{trend * 100:+.2f}%: il run non sta piu' aggiungendo niente.",
            "Puoi fermarti qui. Per continuare servono un learning rate diverso "
            "o dati nuovi."))
    elif trend is not None and trend < -_PLATEAU_SLOPE:
        verdicts.append(_verdict(
            "learning", "good", "Sta ancora imparando",
            f"La training loss e' scesa del {abs(trend) * 100:.1f}% nella "
            "finestra recente.",
            "Lascia proseguire il run."))

    if len(evals) < _MIN_EVALS_FOR_VERDICT:
        verdicts.append(_verdict(
            "warming_up", "info", "Validation ancora insufficiente",
            f"Servono almeno {_MIN_EVALS_FOR_VERDICT} valutazioni per "
            f"distinguere overfitting da rumore: finora ne sono state fatte "
            f"{len(evals)}.",
            "Aspetta le prossime valutazioni prima di trarre conclusioni."))

    order = {"critical": 0, "warning": 1, "good": 2, "info": 3}
    verdicts.sort(key=lambda v: order.get(v["level"], 9))
    return verdicts


def job_metrics(job: dict) -> dict:
    """Everything the Monitor needs for one job, in a single payload.

    Curve e giudizi guardano solo l'ultimo avvio: e' quello in corso, ed e' su
    quello che si decide se continuare. Gli avvii precedenti restano contati,
    perche' sapere che un job e' stato ripreso spiega salti altrimenti
    incomprensibili nel log.
    """
    runs = split_runs(job.get("log_path", ""))
    history = runs[-1] if runs else []
    return {
        "success": True,
        "job_id": job.get("id"),
        "history": history,
        "run_count": len(runs),
        "previous_points": sum(len(r) for r in runs[:-1]),
        "summary": summarize(history),
        "diagnostics": diagnose(history),
        "guide": METRIC_GUIDE,
        "runs": job.get("runs", []),
    }

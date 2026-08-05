# ==============================================================================
# core/training/autopilot.py — Il ciclo che specializza un modello da solo
# Sigma Studio v7 — Training Lab Sub-package
# ==============================================================================
"""Profila un modello, sceglie dove è debole, addestra, misura, e tiene solo
ciò che migliora davvero. Va avanti finché non lo si ferma, e riprende da dove
era rimasto.

**Topologia parallela.** Ogni adapter parte dalla *stessa* base, non dal merge
del precedente. Tre ragioni, tutte misurate su questo progetto:

* la catena sequenziale dimentica — GSM8K è sceso da 93,3% a 84,7% in tre fasi;
* un adapter pesa ~120 MB, un merge 35 GB: in sequenziale il disco finisce in
  cinque iterazioni;
* solo adapter con la stessa inizializzazione si possono fondere fra loro, ed è
  la fusione a permettere di combinare le competenze invece di sovrascriverle.

**La regola che rende il ciclo un metodo e non una passeggiata.** Ogni round
viene accettato solo se batte il candidato corrente sul *set di selezione*, con
un test appaiato (McNemar). Applicata retroattivamente alla catena costruita a
mano, questa regola avrebbe scartato tutti e quattro i round e risparmiato due
giorni di GPU.

**Selezione e verifica sono separate.** Il ciclo decide guardando metà dei
quesiti e non guarda mai l'altra metà. Senza questa separazione un ciclo
automatico non migliora il modello: impara i quesiti su cui viene misurato.
"""

from __future__ import annotations

import json
import math
import os
import re
import shutil
import threading
import time
from datetime import datetime
from pathlib import Path

from core.logger import get_logger

log = get_logger(__name__)

BASE_DIR = Path(__file__).parent.parent.parent
#: Lo stato storico, quando c'era un ciclo solo per tutti i modelli.
STATE_FILE = BASE_DIR / "training_lab" / "autopilot_state.json"
#: Un file per modello, piu' il puntatore a quello che si sta guardando.
STATE_DIR = BASE_DIR / "training_lab" / "autopilot"
ACTIVE_FILE = STATE_DIR / "_attivo.json"

_lock = threading.RLock()
_worker: threading.Thread | None = None
_stop_requested = threading.Event()


# ---------------------------------------------------------------- competenze

#: Che cosa allenare quando una suite risulta debole. I dataset sono
#: deliberatamente **diversi** dalle suite che li misurano: allenare sullo split
#: di training del benchmark che poi si usa per giudicare produce un numero che
#: non significa nulla fuori da quel benchmark.
SKILL_MAP = {
    "gsm8k":      {"label": "Aritmetica applicata",
                   "datasets": ["meta-math/MetaMathQA", "nvidia/OpenMathInstruct-2"]},
    "math":       {"label": "Matematica avanzata",
                   "datasets": ["nvidia/OpenMathInstruct-2", "meta-math/MetaMathQA"]},
    "mmlu":       {"label": "Conoscenza generale",
                   "datasets": ["teknium/OpenHermes-2.5", "Open-Orca/OpenOrca"]},
    "mmlu_pro":   {"label": "Ragionamento su conoscenza",
                   "datasets": ["Open-Orca/OpenOrca", "teknium/OpenHermes-2.5"]},
    "bbh":        {"label": "Ragionamento multi-passo",
                   "datasets": ["Open-Orca/OpenOrca"]},
    "arc":        {"label": "Scienze",
                   "datasets": ["teknium/OpenHermes-2.5"]},
    "hellaswag":  {"label": "Buon senso",
                   "datasets": ["teknium/OpenHermes-2.5"]},
    "truthfulqa": {"label": "Veridicità",
                   "datasets": ["teknium/OpenHermes-2.5"]},
    "humaneval":  {"label": "Codice",
                   "datasets": ["sahil2801/CodeAlpaca-20k",
                                "iamtarun/python_code_instructions_18k_alpaca"]},
    "mbpp":       {"label": "Codice di base",
                   "datasets": ["sahil2801/CodeAlpaca-20k"]},
    "gpqa":       {"label": "Dominio specialistico",
                   "datasets": ["Open-Orca/OpenOrca"]},
}

#: Sopra questa accuratezza una suite non vale la pena: il margine residuo è
#: troppo piccolo perché un round possa guadagnarci qualcosa, e il rischio di
#: perdere ciò che il modello sa già è maggiore del guadagno atteso. È la
#: lezione di GSM8K al 93,3%.
CEILING = 0.88

#: Sotto questo numero di quesiti per suite il punteggio non è informativo.
MIN_ITEMS_PER_SUITE = 8

#: Soglia del test appaiato per accettare un round.
ALPHA = 0.05

#: Oltre questo silenzio il ciclo si considera morto. Il battito arriva a ogni
#: giro d'attesa (10s): un minuto di margine copre una macchina sotto carico
#: senza far sembrare vivo un processo terminato.
HEARTBEAT_TIMEOUT = 60.0

#: Quanti round consecutivi possono guastarsi prima di fermare il ciclo. Uno
#: puo' capitare (un dataset irraggiungibile, un OOM); due di fila sono un
#: problema sistematico, e insistere brucia i bersagli senza misurare nulla.
MAX_GUASTI = 2


def mcnemar_p(only_a: int, only_b: int) -> float:
    """Test esatto di McNemar sulle sole discordanze.

    Gli item su cui due modelli vanno d'accordo non portano informazione sulla
    differenza fra loro: contarli diluirebbe il segnale.
    """
    n = only_a + only_b
    if n == 0:
        return 1.0
    tail = sum(math.comb(n, i) for i in range(n + 1)
               if abs(i - n / 2) >= abs(only_a - n / 2))
    return min(1.0, tail / (2 ** n))


def compare(candidate: dict[str, bool], champion: dict[str, bool]) -> dict:
    """Il candidato batte il campione? Confronto appaiato sugli stessi quesiti."""
    shared = set(candidate) & set(champion)
    wins = sum(1 for i in shared if candidate[i] and not champion[i])
    losses = sum(1 for i in shared if champion[i] and not candidate[i])
    p = mcnemar_p(wins, losses)
    return {
        "items": len(shared), "wins": wins, "losses": losses, "p": round(p, 4),
        "delta": wins - losses,
        "accepted": bool(wins > losses and p < ALPHA),
        "verdict": ("migliora" if wins > losses and p < ALPHA
                    else "peggiora" if losses > wins and p < ALPHA
                    else "indistinguibile dal rumore"),
    }


# ------------------------------------------------------------------ lo stato

def _blank_state() -> dict:
    return {
        "status": "idle",
        "base_model": "",
        "rounds": [],
        "champion": {},
        "profile": {},
        "log": [],
        "created_at": "",
        "updated_at": "",
        "stop_reason": "",
        "current_job": {},
        "items": DEFAULT_ITEMS,
        "max_examples": 30000,
        "max_seq_length": 1024,
    }


def state_path(model: str = "") -> Path:
    """Il file di stato di un modello.

    **Un ciclo per modello.** Ogni modello parte da zero — mai addestrato, con
    le sue statistiche di partenza — e la sua storia non deve mescolarsi con
    quella di un altro: il profilo di Ailo non dice niente su Qwythos, e un
    round accettato sull'uno non e' un round dell'altro. Un file per modello e
    un puntatore a quello attivo.
    """
    model = (model or "").strip()
    if not model:
        return STATE_FILE
    slug = re.sub(r"[^a-zA-Z0-9._-]+", "-", model).strip("-.")[:80] or "senza-nome"
    return STATE_DIR / f"{slug}.json"


def active_model() -> str:
    """Il modello del ciclo che si sta guardando."""
    try:
        return json.loads(ACTIVE_FILE.read_text(encoding="utf-8")).get("model", "")
    except Exception:
        return ""


def set_active_model(model: str) -> None:
    ACTIVE_FILE.parent.mkdir(parents=True, exist_ok=True)
    _atomic_write(ACTIVE_FILE, {"model": model})


def known_cycles() -> list:
    """I cicli gia' avviati, dal piu' recente: uno per modello."""
    out = []
    for path in sorted(STATE_DIR.glob("*.json")):
        if path == ACTIVE_FILE:
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        rounds = data.get("rounds") or []
        holdout = (data.get("champion") or {}).get("holdout_accuracy")
        profile = data.get("profile") or {}
        tot_passed = sum(v.get("passed", 0) for v in profile.values()) if isinstance(profile, dict) else 0
        tot_items = sum(v.get("total", 0) for v in profile.values()) if isinstance(profile, dict) else 0
        profile_acc = (tot_passed / tot_items) if tot_items > 0 else None
        accuracy = holdout if holdout is not None else profile_acc
        last_run = data.get("last_run_at") or data.get("updated_at") or data.get("created_at") or ""
        out.append({
            "model": data.get("base_model", ""),
            "train_model": data.get("train_model", ""),
            "status": data.get("status", ""),
            "rounds": len(rounds),
            "accepted": sum(1 for r in rounds if r.get("accepted")),
            "holdout": holdout,
            "accuracy": accuracy,
            "accuracy_pct": round(accuracy * 100, 1) if accuracy is not None else None,
            "updated_at": data.get("updated_at", ""),
            "last_run_at": last_run,
        })
    out.sort(key=lambda c: c["last_run_at"] or c["updated_at"], reverse=True)
    return out


def migrate_legacy_state() -> str:
    """Porta il vecchio file unico nella cartella per modello.

    C'era un ciclo solo, condiviso da tutti i modelli. Chi aveva gia' del
    lavoro fatto non deve perderlo perche' abbiamo cambiato come si salva.
    """
    try:
        data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return ""
    modello = data.get("base_model") or ""
    if not modello:
        return ""
    destinazione = state_path(modello)
    if destinazione.exists():
        return ""
    _atomic_write(destinazione, data)
    if not active_model():
        set_active_model(modello)
    log.info("stato del ciclo di %s migrato in %s", modello, destinazione.name)
    return modello


def load_state(model: str = "") -> dict:
    """Lo stato di un modello, o quello attivo se non si specifica nulla."""
    target = model or active_model()
    for path in (state_path(target), STATE_FILE) if target else (STATE_FILE,):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        # Il file storico non ha un nome nel percorso: vale solo se e' del
        # modello che stiamo cercando, altrimenti restituiremmo la storia di
        # un altro modello come se fosse questa.
        if path == STATE_FILE and target and data.get("base_model") != target:
            continue
        return data
    return _blank_state()


def _atomic_write(path: Path, payload: dict) -> None:
    """Scrive senza lasciare un file mezzo scritto se qualcosa va storto.

    Il temporaneo porta pid e thread nel nome: con un solo `.tmp` condiviso,
    due processi Sigma che salvano insieme si contendono lo stesso file e su
    Windows la `replace` muore con *[WinError 5] Accesso negato* — ammazzando
    il ciclo a meta' lavoro. E la sostituzione si riprova: un antivirus che
    tiene aperto il file per un istante non e' un buon motivo per fermarsi.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(f".{os.getpid()}.{threading.get_ident()}.tmp")
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    ultimo = None
    for tentativo in range(6):
        try:
            tmp.replace(path)
            return
        except OSError as err:
            ultimo = err
            time.sleep(0.05 * (tentativo + 1))
    tmp.unlink(missing_ok=True)
    raise ultimo


def save_state(state: dict) -> None:
    state["updated_at"] = datetime.now().isoformat(timespec="seconds")
    _atomic_write(state_path(state.get("base_model", "")), state)


def note(state: dict, level: str, message: str) -> None:
    """Una riga nel diario del ciclo, che è ciò che l'utente legge in tempo reale."""
    entry = {"at": datetime.now().isoformat(timespec="seconds"),
             "level": level, "message": message}
    state.setdefault("log", []).append(entry)
    # Il diario e' la memoria del ciclo, non un log applicativo: le righe vecchie
    # non servono a nessuno e farebbero crescere lo stato senza limite.
    del state["log"][:-400]
    log.info("[autopilot] %s", message)
    save_state(state)


# ------------------------------------------------------------- scelta target

def pick_targets(profile: dict, done: list[str]) -> list[dict]:
    """Le competenze su cui conviene lavorare, dalla più promettente.

    L'ordine è per **margine recuperabile**, non per debolezza assoluta: una
    suite al 40% con soli 8 quesiti misurati promette meno di una al 65% con 40,
    perché sul primo numero non si riesce nemmeno a stabilire se un round ha
    funzionato.
    """
    targets = []
    for suite, stats in profile.items():
        if suite in done or suite not in SKILL_MAP:
            continue
        total = stats.get("total", 0)
        if total < MIN_ITEMS_PER_SUITE:
            continue
        accuracy = stats.get("passed", 0) / max(1, total)
        if accuracy >= CEILING:
            continue
        targets.append({
            "suite": suite,
            "label": SKILL_MAP[suite]["label"],
            "datasets": SKILL_MAP[suite]["datasets"],
            "accuracy": round(accuracy, 4),
            "items": total,
            # Margine pesato dalla numerosità: quanto si può guadagnare, e
            # quanto quel guadagno sarà misurabile.
            "headroom": round((1 - accuracy) * math.log1p(total), 4),
        })
    return sorted(targets, key=lambda t: -t["headroom"])


# --------------------------------------------------------------- pulizia

def discardable_artifacts(state: dict) -> list[dict]:
    """Che cosa si può cancellare senza perdere nulla di utile.

    Un round scartato ha prodotto un adapter che non batte il campione: tenerlo
    occupa disco e basta. I round accettati restano, perché il campione corrente
    è fatto di quelli.
    """
    campione = state.get("champion", {})
    keep = {r.get("job_id") for r in state.get("rounds", []) if r.get("accepted")}
    keep |= {r.get("merge_job_id") for r in state.get("rounds", []) if r.get("accepted")}
    keep.add(campione.get("job_id"))

    def peso(job_id):
        cartella = BASE_DIR / "training" / "jobs" / str(job_id)
        if not cartella.is_dir():
            return 0
        return sum(f.stat().st_size for f in cartella.rglob("*") if f.is_file())

    out = []
    for round_ in state.get("rounds", []):
        job_id = round_.get("job_id")
        if not job_id or job_id in keep or round_.get("cleaned"):
            continue
        # Un round scartato lascia tre cose, non una: l'adapter del training,
        # il modello fuso (che e' il piu' pesante, decine di GB) e la copia
        # dentro Ollama. Cancellare solo la prima lasciava indietro quasi tutto
        # lo spazio che si voleva liberare.
        merge_id = round_.get("merge_job_id")
        if merge_id in keep:
            merge_id = None
        modello = round_.get("ollama_model")
        if modello and modello == campione.get("model"):
            modello = None
        size = peso(job_id) + (peso(merge_id) if merge_id else 0)
        out.append({"job_id": job_id, "merge_job_id": merge_id,
                    "ollama_model": modello, "suite": round_.get("suite"),
                    "reason": round_.get("verdict", "scartato"),
                    "bytes": size, "gb": round(size / 1024 ** 3, 2)})
    return out


def _rimuovi_da_ollama(nome: str) -> bool:
    """Toglie un candidato dall'archivio di Ollama.

    Un candidato scartato che resta installato non e' solo spazio: continua a
    comparire fra i modelli disponibili, e prima o poi qualcuno lo sceglie
    credendo sia una versione migliorata.
    """
    import subprocess

    binario = shutil.which("ollama")
    if not binario:
        return False
    try:
        esito = subprocess.run([binario, "rm", nome], capture_output=True,
                               text=True, encoding="utf-8", errors="replace",
                               timeout=60)
        if esito.returncode != 0:
            log.warning("ollama rm %s: %s", nome, (esito.stderr or "")[:120])
        return esito.returncode == 0
    except Exception as exc:
        log.warning("ollama rm %s fallito: %s", nome, exc)
        return False


def cleanup(state: dict, dry_run: bool = False) -> dict:
    """Rimuove gli artefatti dei round che non hanno portato nulla."""
    victims = discardable_artifacts(state)
    freed = 0
    for victim in victims:
        if dry_run:
            continue
        try:
            for job_id in (victim["job_id"], victim.get("merge_job_id")):
                if job_id:
                    shutil.rmtree(BASE_DIR / "training" / "jobs" / str(job_id),
                                  ignore_errors=True)
            if victim.get("ollama_model"):
                _rimuovi_da_ollama(victim["ollama_model"])
            freed += victim["bytes"]
            for round_ in state["rounds"]:
                if round_.get("job_id") == victim["job_id"]:
                    round_["cleaned"] = True
        except Exception as exc:
            log.warning("pulizia di %s fallita: %s", victim["job_id"], exc)
    if not dry_run and victims:
        note(state, "info",
             f"Liberati {freed / 1024**3:.1f} GB da {len(victims)} round scartati.")
    return {"success": True, "candidates": victims,
            "freed_gb": round(freed / 1024 ** 3, 2), "dry_run": dry_run}


# ------------------------------------------------------------------- le fasi

#: Nome stabile del campione su Ollama. Resta lo stesso a ogni promozione, cosi'
#: chi lo usa in chat non deve inseguire un nome nuovo a ogni round.
CHAMPION_MODEL = "sigma-champion"

#: Quesiti per ciclo. Meta' guidano le decisioni, meta' restano da parte.
DEFAULT_ITEMS = 300

#: Spazio che deve restare libero per materializzare un candidato: merge a 16
#: bit (~18 GB) + GGUF (~17 GB) + copia dentro Ollama (~10 GB), piu' margine.
REQUIRED_FREE_GB = 60

#: Ogni quanti round accettati provare a fondere gli adapter fra loro.
SOUP_EVERY = 3

PHASES = ("profile", "train", "materialize", "evaluate", "judge", "soup")


def _free_gb() -> float:
    return shutil.disk_usage(BASE_DIR).free / 1024 ** 3


def _ferma_lavoro(job_id: str, kind: str) -> None:
    """Chiude il job in corso, qualunque sia il suo tipo."""
    try:
        if kind == "training":
            from core.training.jobs import stop_training_job
            stop_training_job(job_id)
        else:
            from core.training.benchmarks import cancel_benchmark_job
            cancel_benchmark_job(job_id)
    except Exception as exc:
        log.warning("chiusura di %s (%s) fallita: %s", job_id, kind, exc)


def _wait_for_job(job_id: str, kind: str, state: dict, poll: float = 10.0,
                  label: str = "") -> str:
    """Aspetta che un job finisca, restituendo il suo stato finale.

    **Lo stop ferma subito.** Questo docstring diceva che lo stop veniva
    onorato qui, ma il ciclo non lo controllava mai: chi premeva Ferma
    aspettava che finisse il training in corso — ore — mentre il pannello
    diceva "fermato". Ora il job viene chiuso al primo controllo utile.

    Non si perde il lavoro fatto: il training salva un checkpoint a cadenza
    regolare, e riprendere riparte da li'. Perdere qualche decina di passi e'
    incomparabilmente meglio che aspettare mezza giornata.

    Qui passa ogni attesa del ciclo, quindi e' il posto giusto per dire alla UI
    su cosa stiamo lavorando adesso: senza questo, un ciclo di sei ore mostra
    solo un diario che avanza a scatti, e la curva di loss del training in
    corso resterebbe invisibile.
    """
    from core.training.jobs import get_job_status
    from core.training.benchmarks import list_benchmark_jobs

    state["current_job"] = {"id": job_id, "kind": kind, "label": label,
                            "since": datetime.now().isoformat(timespec="seconds")}
    save_state(state)
    try:
        while True:
            if kind == "training":
                payload = get_job_status(job_id)
                status = (payload.get("job") or payload).get("status", "unknown")
            else:
                # `list_benchmark_jobs` restituisce la lista, non un
                # involucro: chiamarci .get() sopra sollevava AttributeError
                # e ammazzava il ciclo alla prima attesa.
                jobs = list_benchmark_jobs()
                found = next((j for j in jobs if j.get("id") == job_id), None)
                status = found.get("status", "unknown") if found else "unknown"

            if status in ("completed", "failed", "stopped", "cancelled",
                          "interrupted", "unknown"):
                return status

            if _stop_requested.is_set():
                note(state, "warning",
                     f"Stop richiesto: chiudo {label or job_id} e mi fermo. "
                     "Il lavoro fatto resta nell'ultimo checkpoint.")
                _ferma_lavoro(job_id, kind)
                return "stopped"

            # Il battito dice "sono vivo" a chiunque legga lo stato, anche da
            # un altro processo: `_worker` e' una variabile locale a chi ha
            # avviato il ciclo, e chi risponde alla UI puo' non essere lo
            # stesso — dichiarava interrotto un ciclo che stava lavorando.
            state["heartbeat"] = time.time()
            save_state(state)
            time.sleep(poll)
    finally:
        state["current_job"] = {}
        save_state(state)


def _benchmark_scores(bench_job_id: str, only: set[str] | None = None) -> dict[str, bool]:
    """Esito per quesito di un run di benchmark: {id: passato}."""
    from core.training import benchmark_store as store

    scores: dict[str, bool] = {}
    page, pages = 1, 1
    while page <= pages:
        chunk = store.read_page(bench_job_id, page=page, page_size=1000)
        for row in chunk.get("results", []):
            item_id = row.get("id")
            if item_id and (only is None or item_id in only):
                scores[item_id] = row.get("verdict") == "pass"
        pages = chunk.get("pages", 1)
        page += 1
    return scores


def _suite_profile(scores: dict[str, bool]) -> dict:
    """Accuratezza per suite, dedotta dagli id dei quesiti (`gsm8k_412`)."""
    profile: dict[str, dict] = {}
    for item_id, passed in scores.items():
        suite = str(item_id).rsplit("_", 1)[0]
        stats = profile.setdefault(suite, {"passed": 0, "total": 0})
        stats["total"] += 1
        stats["passed"] += int(passed)
    return profile


def _run_benchmark(model: str, state: dict, items: int) -> tuple[str, dict]:
    """Valuta un modello e restituisce (job_id, esiti per quesito)."""
    from core.training.benchmarks import start_benchmark_run

    # La seconda scheda sta ferma mentre la prima misura. Se il modello ci
    # entra e i quesiti sono abbastanza da ripagare l'avvio, si mette al
    # lavoro anche quella: il pool alterna le richieste fra i servitori.
    try:
        from core.training.endpoints import prepara_parallelo
        p = prepara_parallelo(model, items)
        note(state, "info" if p["parallelo"] else "warning",
             ("Benchmark in parallelo: " if p["parallelo"] else "Benchmark su una scheda sola: ")
             + p["motivo"])
    except Exception as exc:
        # Non riuscire ad andare piu' veloce non e' un motivo per non partire.
        note(state, "warning", f"Parallelismo non valutabile ({exc}): proseguo su una scheda.")

    started = start_benchmark_run(model, suite_id="all", num_samples=items,
                                  mode="sample")
    # `start_benchmark_run` restituisce il job, non un esito con "success":
    # chiederglielo dava sempre None, e il ciclo moriva al primo passo con
    # "benchmark non avviato: None" — cioe' senza dire niente.
    job_id = started.get("id") or started.get("job_id")
    if not job_id:
        raise RuntimeError("benchmark non avviato: "
                           f"{started.get('error') or 'nessun job creato'}")
    note(state, "info", f"Valutazione di {model} avviata ({items} quesiti).")
    final = _wait_for_job(job_id, "benchmark", state,
                          label=f"benchmark di {model}")
    if final != "completed":
        raise RuntimeError(f"benchmark terminato come '{final}'")
    return job_id, _benchmark_scores(job_id)


def _split_scores(scores: dict[str, bool], state: dict) -> tuple[dict, dict]:
    """Separa gli esiti in set di selezione e set di verifica.

    La partizione e' fissata al primo profilo e poi riusata: cambiarla a ciclo
    iniziato renderebbe i round non confrontabili fra loro.
    """
    from core.training.benchmarks import split_selection_holdout

    if not state.get("selection_ids"):
        items = [{"id": i, "suite": str(i).rsplit("_", 1)[0]} for i in sorted(scores)]
        selection, holdout = split_selection_holdout(items)
        state["selection_ids"] = sorted(i["id"] for i in selection)
        state["holdout_ids"] = sorted(i["id"] for i in holdout)
        save_state(state)
    picked = set(state["selection_ids"])
    return ({k: v for k, v in scores.items() if k in picked},
            {k: v for k, v in scores.items() if k not in picked})


def _accuracy(scores: dict[str, bool]) -> float:
    return round(sum(scores.values()) / max(1, len(scores)), 4)


def _publish_champion(state: dict, job_id: str, label: str) -> None:
    """Porta il campione su Ollama sotto un nome stabile, con le sue statistiche."""
    from core.training.jobs import export_to_ollama

    # Il campione eredita il formato di conversazione del modello da cui
    # discende: senza, chi lo interroga riceve continuazioni invece di
    # risposte, e il punteggio crolla per una ragione che non c'entra con
    # quanto ha imparato.
    result = export_to_ollama(job_id, CHAMPION_MODEL, quantization="q4_K_M",
                              template_from=state.get("base_model", ""))
    if result.get("success"):
        note(state, "good", f"Campione aggiornato: {label} -> `ollama run {CHAMPION_MODEL}`")
    else:
        note(state, "warning", f"Campione non pubblicato su Ollama: {result.get('error')}")
    state["champion"]["published"] = bool(result.get("success"))
    save_state(state)


# ------------------------------------------------------------------ comandi

def _phase_profile(state: dict, items: int) -> None:
    """Misura il modello di partenza: è il metro di tutto ciò che segue."""
    base = state["base_model"]
    note(state, "info", f"Profilo del modello di partenza: {base}")
    bench_id, scores = _run_benchmark(base, state, items)
    selection, holdout = _split_scores(scores, state)

    state["profile"] = _suite_profile(selection)
    state["champion"] = {
        "label": "modello di partenza", "model": base, "job_id": None,
        "bench_id": bench_id, "adapters": [],
        "selection_accuracy": _accuracy(selection),
        "holdout_accuracy": _accuracy(holdout),
        "scores": selection,
    }
    save_state(state)
    note(state, "good",
         f"Partenza: {_accuracy(selection)*100:.1f}% su {len(selection)} quesiti di "
         f"selezione, {_accuracy(holdout)*100:.1f}% sui {len(holdout)} di verifica.")
    for target in pick_targets(state["profile"], done=[])[:4]:
        note(state, "info",
             f"  bersaglio: {target['label']} — {target['accuracy']*100:.0f}% "
             f"su {target['items']} quesiti")


def _lr_for_model(state: dict) -> float:
    """Learning rate adattato alla dimensione del modello.

    I modelli piccoli (<1B) sono piu' sensibili: un LR troppo alto distrugge
    cio' che sanno gia'. I modelli grandi (>3B) tollerano LR piu' alti e ne
    hanno bisogno per muovere pesi sufficienti in una sola epoca.
    """
    model_name = (state.get("train_model") or state.get("base_model", "")).lower()
    # Euristica dal nome del modello: quasi tutti contengono il conteggio di
    # parametri nel nome (0.5b, 1.5b, 3b, 7b, 8b, 14b, 70b...).
    import re
    match = re.search(r'(\d+(?:\.\d+)?)b', model_name)
    if match:
        params_b = float(match.group(1))
        if params_b < 1.0:
            return 2e-5
        if params_b < 3.0:
            return 5e-5
        return 1e-4
    # Fallback conservativo per modelli piccoli.
    return 5e-5


def _phase_round(state: dict, target: dict, items: int) -> dict:
    """Un round completo: allena dalla base, materializza, misura, giudica."""
    from core.training.jobs import (create_training_job, merge_job_adapter,
                                    start_training_job)
    from core.training.datasets import register_hf_dataset

    suite, dataset_id = target["suite"], target["datasets"][0]
    round_ = {"suite": suite, "label": target["label"], "dataset": dataset_id,
              "started_at": datetime.now().isoformat(timespec="seconds"),
              "accepted": False, "verdict": "in corso"}
    state.setdefault("rounds", []).append(round_)
    note(state, "info", f"Round su {target['label']} con {dataset_id}.")

    registered = register_hf_dataset(dataset_id)
    if not registered.get("success"):
        round_["verdict"] = f"dataset non disponibile: {registered.get('error', '')[:120]}"
        round_["broken"] = True
        save_state(state)
        return round_

    created = create_training_job({
        # L'addestramento parte dai pesi, non dal nome Ollama: sono due
        # identita' diverse dello stesso modello.
        "base_model": state.get("train_model") or state["base_model"],
        "method": "lora_unsloth",
        "dataset_id": registered["dataset"]["id"],
        "name": f"auto · {target['label']}",
        "hyperparams": {"num_epochs": 1, "max_examples": state.get("max_examples", 30000),
                        # Il contesto lo sceglie chi avvia il ciclo: e' la voce
                        # che pesa di piu' sulla memoria, e la manopola non
                        # serve a niente se non arriva fin qui.
                        "max_seq_length": int(state.get("max_seq_length") or 1024),
                        "learning_rate": _lr_for_model(state),
                        # Deciso una volta all'avvio del ciclo, non a ogni
                        # round: e' una scelta sul modello, non sul bersaglio.
                        "trust_remote_code": bool(state.get("trust_remote_code"))},
    })
    if not created.get("success"):
        round_["verdict"] = f"job non creato: {created.get('error', '')[:120]}"
        round_["broken"] = True
        save_state(state)
        return round_

    round_["job_id"] = created["job_id"]
    save_state(state)
    # Se l'avvio fallisce il job resta "ready", che non e' uno stato
    # terminale: senza questo controllo il ciclo aspetterebbe per sempre un
    # processo che non e' mai partito.
    avviato = start_training_job(round_["job_id"])
    if not avviato.get("success"):
        round_["verdict"] = f"training non avviato: {avviato.get('error', '')[:120]}"
        round_["broken"] = True
        save_state(state)
        return round_
    final = _wait_for_job(round_["job_id"], "training", state,
                          label=f"training su {target['label']}")
    if final != "completed":
        round_["verdict"] = f"training terminato come '{final}'"
        round_["broken"] = True
        save_state(state)
        return round_

    merged = merge_job_adapter(round_["job_id"], {"stage_name": f"auto {suite}"})
    if not merged.get("success"):
        round_["verdict"] = f"merge fallito: {merged.get('error', '')[:120]}"
        round_["broken"] = True
        save_state(state)
        return round_
    round_["merge_job_id"] = merged["job_id"]
    save_state(state)
    if _wait_for_job(merged["job_id"], "training", state,
                     label=f"fusione dell'adapter {suite}") != "completed":
        round_["verdict"] = "merge non completato"
        round_["broken"] = True
        save_state(state)
        return round_

    candidate_model = f"sigma-cand-{round_['job_id']}"
    from core.training.jobs import export_to_ollama
    exported = export_to_ollama(merged["job_id"], candidate_model, quantization="q4_K_M",
                                template_from=state.get("base_model", ""))
    if not exported.get("success"):
        round_["verdict"] = f"export fallito: {exported.get('error', '')[:120]}"
        round_["broken"] = True
        save_state(state)
        return round_
    round_["ollama_model"] = candidate_model

    # L'id della valutazione va tenuto: e' l'unico modo per risalire ai
    # singoli quesiti quando si vuole capire *perche'* un round e' stato
    # scartato, invece di leggere solo il verdetto.
    bench_id, scores = _run_benchmark(candidate_model, state, items)
    round_["bench_id"] = bench_id
    selection, holdout = _split_scores(scores, state)
    round_["selection_accuracy"] = _accuracy(selection)
    round_["holdout_accuracy"] = _accuracy(holdout)

    outcome = compare(selection, state["champion"].get("scores", {}))
    round_.update(outcome)
    round_["finished_at"] = datetime.now().isoformat(timespec="seconds")
    save_state(state)

    if outcome["accepted"]:
        note(state, "good",
             f"{target['label']}: vince {outcome['wins']}, perde {outcome['losses']}, "
             f"p={outcome['p']} — accettato.")
        state["champion"] = {
            "label": f"auto · {target['label']}",
            "model": candidate_model, "job_id": merged["job_id"],
            "adapters": state["champion"].get("adapters", []) + [round_["job_id"]],
            "selection_accuracy": round_["selection_accuracy"],
            "holdout_accuracy": round_["holdout_accuracy"],
            "scores": selection,
        }
        save_state(state)
        _publish_champion(state, merged["job_id"], state["champion"]["label"])
    else:
        note(state, "info",
             f"{target['label']}: vince {outcome['wins']}, perde {outcome['losses']}, "
             f"p={outcome['p']} — {outcome['verdict']}, scartato.")
        _drop_candidate(state, round_)
    return round_


def _drop_candidate(state: dict, round_: dict) -> None:
    """Libera ciò che un round scartato ha materializzato.

    L'adapter resta — pesa ~120 MB e potrebbe servire a una fusione futura —
    mentre merge, GGUF e modello Ollama sono decine di GB che non servono a
    nulla se il round non ha vinto.
    """
    from core.training.jobs import delete_job

    if round_.get("merge_job_id"):
        delete_job(round_["merge_job_id"])
    if round_.get("ollama_model"):
        try:
            ollama = shutil.which("ollama")
            if ollama:
                import subprocess
                subprocess.run([ollama, "rm", round_["ollama_model"]],
                               capture_output=True, timeout=120)
        except Exception as exc:
            log.warning("rimozione del modello candidato: %s", exc)
    round_["cleaned_heavy"] = True
    save_state(state)
    note(state, "info", f"Artefatti pesanti del round scartato liberati "
                        f"({_free_gb():.0f} GB liberi).")


def _ensure_eval_identity(state: dict) -> None:
    """Porta il modello in Ollama, se non c'e' gia'.

    Scegliere un modello da HuggingFace e poi doverlo importare a mano prima di
    poter premere Avvia era un passaggio che l'utente non ha ragione di
    conoscere: se i pesi ci sono, l'identita' di valutazione si costruisce da
    sola. Sta qui dentro al ciclo e non in `start` perche' un modello da 9B ci
    mette dei minuti, e la UI non deve restare appesa ad attenderlo.
    """
    from core.training.model_catalog import _fingerprint, _ollama_index, ensure_ollama_identity

    base = state.get("base_model") or ""
    if _fingerprint(base) in _ollama_index():
        return

    pesi = state.get("train_model") or ""
    if not pesi or Path(pesi).is_dir():
        # Una cartella locale non e' un repo da scaricare: va esportata, ed e'
        # un'altra strada (quella dei job). Meglio dirlo che fallire piu' tardi.
        raise RuntimeError(
            f"'{base}' non e' in Ollama e non c'e' un repo HuggingFace da cui "
            "importarlo: esporta prima il modello dalla tab Studio.")

    note(state, "info", f"'{base}' non e' in Ollama: lo importo da {pesi}.")
    esito = ensure_ollama_identity(pesi)
    if not esito.get("success"):
        raise RuntimeError(f"import di {pesi} in Ollama fallito: {esito.get('error')}")
    state["base_model"] = esito["model_name"]
    note(state, "good", f"Importato in Ollama come '{esito['model_name']}'.")
    save_state(state)


def senza_misura(round_: dict) -> bool:
    """Il round e' finito senza arrivare a un confronto?

    Il marchio `broken` lo mettono le vie d'uscita di `_phase_round`, ma non
    c'e' negli stati salvati prima che esistesse — e quei round continuavano a
    consumare bersagli. La prova che regge sempre e' l'assenza di `wins`:
    quella chiave la scrive solo `compare`, cioe' solo un round che ha davvero
    misurato qualcosa.
    """
    return bool(round_.get("broken")) or "wins" not in round_


def _cycle(state: dict, items: int) -> None:
    """Il ciclo vero. Ogni passo salva prima di cominciare il successivo."""
    guasti = 0
    try:
        _ensure_eval_identity(state)
        if not state.get("profile"):
            _phase_profile(state, items)

        while not _stop_requested.is_set():
            if _free_gb() < REQUIRED_FREE_GB:
                state["stop_reason"] = "spazio su disco insufficiente"
                note(state, "warning",
                     f"Restano {_free_gb():.0f} GB liberi, ne servono {REQUIRED_FREE_GB} "
                     "per materializzare un candidato. Ciclo in pausa.")
                break

            # Un round rotto non ha misurato niente: la competenza resta da
            # provare, altrimenti un guasto ripetibile si mangia tutti i
            # bersagli e il ciclo dichiara di aver finito senza aver fatto
            # nulla. E' successo: quattro round di fila caduti sullo stesso
            # TypeError, e il diario ha concluso "nessuna competenza
            # migliorabile rimasta".
            done = [r.get("suite") for r in state.get("rounds", [])
                    if not senza_misura(r)]
            targets = pick_targets(state.get("profile", {}), done)
            if not targets:
                state["stop_reason"] = "nessun bersaglio rimasto"
                note(state, "good", "Nessuna competenza migliorabile rimasta: ciclo concluso.")
                break

            round_ = _phase_round(state, targets[0], items)

            # Riprovare lo stesso bersaglio una volta copre il guasto
            # occasionale; alla seconda e' sistematico, e continuare
            # significherebbe soltanto rifare lo stesso errore su ogni
            # competenza.
            if senza_misura(round_):
                guasti += 1
                if guasti >= MAX_GUASTI:
                    state["stop_reason"] = round_.get("verdict", "guasto ripetuto")
                    note(state, "error",
                         f"Due round di fila non sono arrivati a una misura: "
                         f"{round_.get('verdict', '')}. Ciclo fermato — "
                         "e' un problema da risolvere, non un bersaglio da cambiare.")
                    break
            else:
                guasti = 0

        state["status"] = "stopped" if _stop_requested.is_set() else "done"
        if _stop_requested.is_set():
            state["stop_reason"] = state.get("stop_reason") or "richiesta dall'utente"
    except Exception as exc:
        state["status"] = "interrupted"
        state["stop_reason"] = str(exc)[:300]
        note(state, "error", f"Ciclo interrotto: {exc}")
    finally:
        state["heartbeat"] = 0
        save_state(state)
        _stop_requested.clear()


def resolve_pair(eval_model: str, train_model: str = "") -> dict:
    """Le due identità dello stesso modello, verificate prima di partire.

    Un modello nel ciclo ha bisogno di **due** nomi diversi, e confonderli è un
    errore che si paga un'ora dopo:

    * l'identità di **valutazione** è un modello Ollama, perché i benchmark
      passano da lì;
    * l'identità di **addestramento** è un repo HuggingFace o una cartella di
      pesi, perché LoRA non sa caricare un GGUF.

    Molti modelli hanno entrambe. Alcuni no: un modello pubblicato solo su
    Ollama si può misurare ma non specializzare, e va detto adesso — non dopo
    aver speso un'ora di profilazione.
    """
    from core.training.jobs import resolve_base_model

    candidate = (train_model or "").strip()
    if not candidate:
        # Un tag Ollama "owner/nome:tag" spesso rispecchia un repo HuggingFace:
        # si prova, ma la conferma la da' comunque la validazione qui sotto.
        candidate = eval_model.rsplit(":", 1)[0]

    try:
        resolved = resolve_base_model(candidate)
    except ValueError as exc:
        return {"ok": False, "error": (
            f"'{eval_model}' si può valutare ma non addestrare: {exc} "
            "Indica il repo HuggingFace corrispondente, oppure scegli un "
            "modello che esista anche fuori da Ollama.")}

    # Il formato valido non basta: `Alieno/ailo-340m-v4` e' un id ben scritto e
    # inesistente. Senza questo controllo il ciclo scoprirebbe il problema dopo
    # un'ora di profilazione, al primo tentativo di training.
    if not Path(resolved).is_dir():
        reachable, detail = _hf_model_exists(resolved)
        if not reachable:
            return {"ok": False, "error": (
                f"I pesi di '{eval_model}' non sono raggiungibili: "
                f"'{resolved}' su HuggingFace risponde {detail}. "
                "Il modello si può valutare ma non specializzare. Indica il "
                "repo corretto, oppure scegli un modello pubblicato anche "
                "fuori da Ollama.")}
    return {"ok": True, "eval_model": eval_model, "train_model": resolved}


def _hf_model_exists(repo_id: str) -> tuple[bool, str]:
    """Il repo esiste ed è accessibile con le credenziali che abbiamo?"""
    import urllib.error
    import urllib.request

    url = f"https://huggingface.co/api/models/{repo_id}"
    request = urllib.request.Request(url, headers={"User-Agent": "SigmaStudio/7.0"})
    token = os.environ.get("HF_TOKEN")
    if token:
        request.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return response.status == 200, str(response.status)
    except urllib.error.HTTPError as exc:
        if exc.code in (401, 403):
            return False, f"{exc.code} (privato o ad accesso ristretto)"
        return False, str(exc.code)
    except Exception as exc:
        # Rete assente: meglio lasciar procedere che bloccare per un timeout.
        log.warning("verifica di %s non riuscita: %s", repo_id, exc)
        return True, "non verificabile"


def start(base_model: str, items: int = DEFAULT_ITEMS,
          max_examples: int = 30000, train_model: str = "",
          trust_remote_code: bool = False, max_seq_length: int = 1024) -> dict:
    """Avvia il ciclo su un modello. Se uno stato esiste già, riprende da lì."""
    global _worker
    with _lock:
        if _worker is not None and _worker.is_alive():
            return {"success": False, "error": "Il ciclo è già in esecuzione."}
        vivo_altrove = time.time() - float(load_state(base_model).get("heartbeat") or 0)
        if vivo_altrove < HEARTBEAT_TIMEOUT:
            return {"success": False,
                    "error": "Il ciclo è già in esecuzione (avviato poco fa)."}
        if not base_model and train_model:
            # Scegliendo un modello che sta solo su HuggingFace l'identita' di
            # valutazione non esiste ancora: la prepara il ciclo, ma il nome lo
            # decidiamo adesso perche' e' la chiave con cui si riprende.
            from core.training.model_catalog import ollama_name_for
            base_model = ollama_name_for(train_model)
        if not base_model:
            return {"success": False, "error": "Nessun modello indicato."}
        if _free_gb() < REQUIRED_FREE_GB:
            return {"success": False,
                    "error": (f"Servono almeno {REQUIRED_FREE_GB} GB liberi per "
                              f"materializzare un candidato, ce ne sono {_free_gb():.0f}.")}

        # La validazione sta qui, prima di qualunque lavoro: un modello non
        # addestrabile deve fermare il ciclo adesso, non dopo la profilazione.
        pair = resolve_pair(base_model, train_model)
        if not pair["ok"]:
            return {"success": False, "error": pair["error"]}

        # Lo stato di *questo* modello, non l'ultimo che si e' guardato: ogni
        # modello ha il suo ciclo e comincia da zero.
        state = load_state(base_model)
        resuming = state.get("base_model") == base_model and state.get("rounds")
        if not resuming:
            state = _blank_state()
            state["base_model"] = base_model
            state["train_model"] = pair["train_model"]
            state["created_at"] = datetime.now().isoformat(timespec="seconds")
        set_active_model(base_model)
        state["status"] = "running"
        state["last_run_at"] = datetime.now().isoformat(timespec="seconds")
        # Le impostazioni vivono nello stato, non nella chiamata: alla ripresa
        # il ciclo deve rifare quello che stava facendo, non tornare ai valori
        # di fabbrica perche' chi lo riprende non li ha ridigitati.
        state["max_examples"] = max_examples
        state["items"] = int(items)
        state["max_seq_length"] = int(max_seq_length)
        state["trust_remote_code"] = bool(trust_remote_code)
        state["stop_reason"] = ""
        save_state(state)
        note(state, "info",
             ("Ciclo ripreso" if resuming else "Ciclo avviato")
             + f" su {base_model} (pesi: {state.get('train_model')}).")

        _stop_requested.clear()
        _worker = threading.Thread(target=_cycle, args=(state, int(items)),
                                   daemon=True, name="sigma-autopilot")
        _worker.start()
    return {"success": True, "message": f"Ciclo avviato su {base_model}.",
            "resumed": bool(resuming)}


def status(model: str = "") -> dict:
    """Lo stato del ciclo di un modello, per la UI."""
    migrate_legacy_state()
    state = load_state(model)
    # Vivo se il thread e' qui, oppure se il battito su disco e' recente: la
    # seconda condizione copre il caso in cui la richiesta arriva a un
    # processo diverso da quello che sta lavorando.
    fresco = time.time() - float(state.get("heartbeat") or 0) < HEARTBEAT_TIMEOUT
    running = (_worker is not None and _worker.is_alive()) or fresco
    if state.get("status") == "running" and not running:
        # Sigma e' stato riavviato mentre il ciclo girava: lo stato su disco
        # direbbe ancora "running" e la UI aspetterebbe per sempre.
        #
        # La correzione si applica a cio' che si restituisce, **non** al file.
        # Una lettura che scrive e' il modo in cui un processo vecchio
        # sabota un ciclo vivo: ne bastava uno con il modulo caricato prima
        # di questa riga per riscrivere "interrupted" ogni tre secondi sopra
        # un training in corso. Chi riprende il ciclo sistema lo stato vero;
        # qui si racconta soltanto.
        state = dict(state)
        state["status"] = "interrupted"
        # E con lui il round che stava lavorando: senza questo resta "in
        # corso" per sempre, un fantasma in cima alla lista che non finira'
        # mai perche' non c'e' piu' nessuno a farlo finire.
        state["rounds"] = [
            dict(r, verdict="interrotto dall'arresto di Sigma", broken=True)
            if r.get("verdict") == "in corso" else r
            for r in state.get("rounds", [])
        ]
        state["current_job"] = {}
    return {
        "success": True,
        "state": state,
        "running": running,
        # Lo stesso criterio del ciclo, altrimenti la UI dice "0 bersagli
        # rimasti" mentre il ciclo ne ha ancora quattro da provare.
        "targets": pick_targets(state.get("profile", {}),
                                [r.get("suite") for r in state.get("rounds", [])
                                 if not senza_misura(r)]),
        "discardable": discardable_artifacts(state),
        # `profile` e' com'era il modello alla partenza e non cambia mai: e' il
        # metro. Questo e' com'e' adesso il campione, sugli stessi quesiti, e
        # serve a vedere il guadagno competenza per competenza invece che in
        # un solo numero complessivo.
        "profile_now": _suite_profile(state.get("champion", {}).get("scores", {})),
        "champion_label": state.get("champion", {}).get("label", ""),
        # Ogni modello ha il suo ciclo: qui ci sono tutti, per poter passare
        # dall'uno all'altro senza perdere quello che si sta guardando.
        "cycles": known_cycles(),
        "active_model": state.get("base_model", "") or active_model(),
    }


def request_stop(model: str = "") -> dict:
    """Ferma il ciclo alla fine del passo corrente, senza perdere il lavoro fatto."""
    state = load_state(model)
    if state.get("status") != "running":
        return {"success": False, "error": "Il ciclo non è in esecuzione."}
    _stop_requested.set()
    state["stop_reason"] = "richiesta dall'utente"
    note(state, "info", "Stop richiesto: il ciclo si ferma alla fine del passo corrente.")
    return {"success": True, "message": "Il ciclo si fermerà appena il passo corrente è concluso."}


def reopen_targets(model: str = "") -> dict:
    """Rende di nuovo disponibili le competenze gia' provate e scartate.

    Un round scartato consuma il suo bersaglio per sempre, ed e' giusto:
    riprovare all'infinito la stessa cosa non e' un metodo. Ma se il verdetto
    era viziato — misure fatte con un export che toglieva al modello il suo
    formato di conversazione, quindi zero risposte valide per tutti i
    candidati — quei bersagli vanno restituiti, altrimenti il ciclo si
    dichiara concluso senza aver mai davvero misurato niente.

    I round accettati restano: il campione e' fatto di quelli.
    """
    stato = load_state(model)
    riaperti = []
    for round_ in stato.get("rounds", []):
        if round_.get("accepted") or senza_misura(round_):
            continue
        round_["broken"] = True
        round_["verdict"] = (round_.get("verdict", "") + " — verdetto annullato, "
                             "bersaglio riaperto").strip(" —")
        riaperti.append(round_.get("suite"))
    if not riaperti:
        return {"success": False, "error": "Nessun bersaglio da riaprire."}
    stato["status"] = "stopped"
    stato["stop_reason"] = ""
    save_state(stato)
    note(stato, "info",
         f"Bersagli riaperti: {', '.join(riaperti)}. I round precedenti restano "
         "in elenco ma non contano piu' come misure.")
    return {"success": True, "riaperti": riaperti,
            "message": f"{len(riaperti)} bersagli tornano disponibili."}


def drop_rounds(model: str = "", quanti: int = 0) -> dict:
    """Cancella gli ultimi round e riporta il ciclo allo stato precedente.

    Riaprire un bersaglio lascia il round in elenco; a volte invece si vuole
    proprio buttarlo — quando la misura era viziata da un difetto che abbiamo
    corretto, e tenerne traccia confonde e basta. Con `quanti` a zero si
    cancella tutto.

    Non e' un `reset`: profilo e campione restano. Se pero' il campione veniva
    da uno dei round cancellati, torna il modello di partenza — non si puo'
    tenere per campione qualcosa la cui storia non esiste piu'.
    """
    stato = load_state(model)
    rounds = stato.get("rounds", [])
    if not rounds:
        return {"success": False, "error": "Nessun round da cancellare."}
    quanti = len(rounds) if quanti <= 0 else min(int(quanti), len(rounds))
    tolti, restano = rounds[-quanti:], rounds[:-quanti]

    # Gli artefatti dei round cancellati vanno con loro: tenerli occuperebbe
    # disco per una storia che non c'e' piu'.
    liberati = 0
    for round_ in tolti:
        for job_id in (round_.get("job_id"), round_.get("merge_job_id")):
            if not job_id:
                continue
            cartella = BASE_DIR / "training" / "jobs" / str(job_id)
            if cartella.is_dir():
                liberati += sum(f.stat().st_size for f in cartella.rglob("*") if f.is_file())
                shutil.rmtree(cartella, ignore_errors=True)
        if round_.get("ollama_model"):
            _rimuovi_da_ollama(round_["ollama_model"])

    stato["rounds"] = restano
    campione = stato.get("champion") or {}
    if campione.get("job_id") and campione["job_id"] in {r.get("job_id") for r in tolti}:
        accettati = [r for r in restano if r.get("accepted")]
        if not accettati:
            stato["champion"] = {**campione, "label": "modello di partenza",
                                 "model": stato.get("base_model", ""), "job_id": None,
                                 "adapters": []}
    stato["status"] = "stopped"
    stato["stop_reason"] = ""
    save_state(stato)
    note(stato, "info",
         f"{len(tolti)} round cancellati, {liberati / 1024**3:.1f} GB liberati. "
         f"Ne restano {len(restano)}.")
    return {"success": True, "cancellati": len(tolti), "restano": len(restano),
            "freed_gb": round(liberati / 1024 ** 3, 2),
            "message": f"{len(tolti)} round cancellati."}


def reset(model: str = "") -> dict:
    """Azzera il ciclo di un modello, lasciando intatti job e modelli."""
    if _worker is not None and _worker.is_alive():
        return {"success": False, "error": "Ferma il ciclo prima di azzerarlo."}
    bersaglio = model or active_model()
    vuoto = _blank_state()
    # Il nome resta: azzerare vuol dire ricominciare da capo su *questo*
    # modello, non dimenticare quale fosse.
    vuoto["base_model"] = bersaglio
    save_state(vuoto)
    return {"success": True,
            "message": f"Ciclo di {bersaglio or 'questo modello'} azzerato."}

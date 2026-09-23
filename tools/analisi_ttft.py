"""La regola del tempo al primo token, misurata invece che dichiarata.

La prima stesura di questo strumento correlava `ttft_ms` con il numero di
turni e poi STAMPAVA una regola ("il TTFT cresce con la dimensione del
prompt") senza averla calcolata: usciva sempre con zero, e quindi valeva
come una verifica che non ha verificato niente. Qui la regola esce dai
numeri, e quando i numeri non la sostengono lo strumento lo dice.

Le tre grandezze non hanno lo stesso peso, e lo strumento lo dichiara:

* `ttft_ms`      misura vera: orologio da inizio chiamata al primo token.
* `prompt_tokens` e' una STIMA (caratteri del contesto / 4) finche' il
  provider non consegna `usage` o `timings`; le righe lo dicono.
* `reuse_tokens` e' il numero che deciderebbe tutto, e sul percorso
  llama-server non lo riempie nessuno: si conta quante sessioni lo hanno
  a zero, senza spacciare quel silenzio per una misura di zero.

Uso:
    python tools/analisi_ttft.py
    python tools/analisi_ttft.py --sessione task_1790196974219_pueka

Ultima riga dell'output, sempre: SIGMA-CHECK. `checked` e' il numero di
turni esaminati, `problems` quelli con una misura spaiata (ttft presente e
prompt assente) piu' i file illeggibili. Esce diverso da zero se ce ne sono.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

RADICE = Path(__file__).resolve().parent.parent
CARTELLA = RADICE / "var" / "dev_sessions"


# ----------------------------------------------------------------- lettura


def _turni_di_sessione(percorso: Path) -> Tuple[List[Dict[str, Any]], Optional[str]]:
    """Le righe di turno di una sessione, o l errore che ne ha impedito la lettura."""
    try:
        dati = json.loads(percorso.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return [], "%s: %s" % (percorso.name, exc)

    metrica = dati.get("metrics") or {}
    righe = metrica.get("turns_detail") or []
    if not isinstance(righe, list):
        return [], "%s: turns_detail non e' una lista" % percorso.name

    comune = {
        "sessione": str(dati.get("session_id") or percorso.stem),
        "modello": str(dati.get("model") or metrica.get("model") or ""),
        "provider": str(metrica.get("provider") or ""),
        "esito": str(dati.get("status") or ""),
        "obiettivo_raggiunto": bool(metrica.get("goal_reached")),
    }
    fuori: List[Dict[str, Any]] = []
    for riga in righe:
        if not isinstance(riga, dict):
            continue
        voce = dict(comune)
        voce.update({
            "turn": int(riga.get("turn") or 0),
            "ttft_ms": _numero(riga.get("ttft_ms")),
            "prompt_tokens": _numero(riga.get("prompt_tokens")),
            "generated_tokens": _numero(riga.get("generated_tokens")) or 0.0,
            "reuse_tokens": _numero(riga.get("reuse_tokens")) or 0.0,
            "tps": _numero(riga.get("tps")) or 0.0,
            "state_chars": _numero(riga.get("state_chars")) or 0.0,
        })
        fuori.append(voce)
    return fuori, None


def _numero(valore: Any) -> Optional[float]:
    """Un numero, o None: un Turno senza misura non e' un turno da zero."""
    if valore is None or isinstance(valore, bool):
        return None
    try:
        return float(valore)
    except (TypeError, ValueError):
        return None


def carica(cartella: Path) -> Tuple[List[Dict[str, Any]], List[str]]:
    turni: List[Dict[str, Any]] = []
    errori: List[str] = []
    if not cartella.is_dir():
        return [], ["cartella inesistente: %s" % cartella]
    for percorso in sorted(cartella.glob("*.json")):
        righe, errore = _turni_di_sessione(percorso)
        if errore:
            errori.append(errore)
        turni.extend(righe)
    return turni, errori


def carica_sessioni(cartella: Path) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
    """Le sessioni come le racconta il loro consuntivo, una riga per run.

    Questo e' il livello che ha centosessanta sessioni, e la sua misura non e'
    quella dei turni: `ttft_ms` qui e' l'attesa del PRIMO token del run,
    misurata da prima del caricamento del modello. Un run che carica i pesi
    paga in questa colonna quello che un run con il modello gia' caldo non
    paga: le due colonne non si possono mettere nello stesso grafico.
    """
    sessioni: List[Dict[str, Any]] = []
    copertura = {"file": 0, "con_consuntivo": 0, "senza_consuntivo": 0}
    if not cartella.is_dir():
        return sessioni, copertura
    for percorso in sorted(cartella.glob("*.json")):
        copertura["file"] += 1
        try:
            dati = json.loads(percorso.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            copertura["senza_consuntivo"] += 1
            continue
        metrica = dati.get("metrics") or {}
        if "ttft_ms" not in metrica and "turns" not in metrica:
            copertura["senza_consuntivo"] += 1
            continue
        copertura["con_consuntivo"] += 1
        turni = _numero(metrica.get("turns")) or 0.0
        prompt = _numero(metrica.get("prompt_tokens")) or 0.0
        sessioni.append({
            "sessione": str(dati.get("session_id") or percorso.stem),
            "modello": str(dati.get("model") or metrica.get("model") or ""),
            "provider": str(metrica.get("provider") or ""),
            "esito": str(dati.get("status") or ""),
            "turni": turni,
            "prompt_tokens": prompt,
            "prompt_per_turno": (prompt / turni) if turni else 0.0,
            "ttft_ms": _numero(metrica.get("ttft_ms")),
            "reuse_tokens": _numero(metrica.get("reuse_tokens")) or 0.0,
            "generated_tokens": _numero(metrica.get("generated_tokens")) or 0.0,
            "obiettivo_raggiunto": bool(metrica.get("goal_reached")),
            "turni_esauriti": bool(metrica.get("exhausted_turns")),
        })
    return sessioni, copertura


def _mediana(valori: List[float]) -> Optional[float]:
    return statistics.median(valori) if valori else None


def _f(valore: Optional[float], cifre: int = 0) -> str:
    """Un numero per l'occhio, o un trattino: None non e' zero."""
    if valore is None:
        return "-"
    return ("%%.%df" % cifre) % valore


def analisi_per_sessione(sessioni: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Il tempo del primo token a livello di run, e con chi sta insieme."""
    letti = [s for s in sessioni if s["ttft_ms"] is not None and s["ttft_ms"] > 0]
    raggiunti = [s for s in letti if s["obiettivo_raggiunto"]]
    esauriti = [s for s in letti if s["turni_esauriti"]]
    altri = [s for s in letti
             if not s["obiettivo_raggiunto"] and not s["turni_esauriti"]]

    coppie_prompt = [(s["prompt_per_turno"], s["ttft_ms"]) for s in letti
                     if s["prompt_per_turno"] > 0]
    coppie_turni = [(s["turni"], s["ttft_ms"]) for s in letti if s["turni"] > 0]
    minimo = min((s["ttft_ms"] for s in letti), default=None)
    massimo = max((s["ttft_ms"] for s in letti), default=None)
    return {
        "letti": len(letti),
        "min": minimo,
        "max": massimo,
        "rapporto": (massimo / minimo) if minimo else None,
        "mediana": _mediana([s["ttft_ms"] for s in letti]),
        "raggiunti": len(raggiunti),
        "esauriti": len(esauriti),
        "altri": len(altri),
        "ttft_raggiunti": _mediana([s["ttft_ms"] for s in raggiunti]),
        "ttft_esauriti": _mediana([s["ttft_ms"] for s in esauriti]),
        "turni_raggiunti": _mediana([s["turni"] for s in raggiunti]),
        "turni_esauriti": _mediana([s["turni"] for s in esauriti]),
        "r_prompt": pearson(coppie_prompt),
        "r_turni": pearson(coppie_turni),
        "n_coppie_prompt": len(coppie_prompt),
        "n_coppie_turni": len(coppie_turni),
        "senza_modello": sum(1 for s in sessioni if not s["modello"]),
        "senza_provider": sum(1 for s in sessioni if not s["provider"]),
    }


# ------------------------------------------------------------- statistica


def pearson(coppie: List[Tuple[float, float]]) -> Optional[float]:
    """Il coefficiente di Pearson, o None quando una delle due serie e' piatta."""
    n = len(coppie)
    if n < 3:
        return None
    xs = [c[0] for c in coppie]
    ys = [c[1] for c in coppie]
    mx = sum(xs) / n
    my = sum(ys) / n
    sxy = sum((xs[i] - mx) * (ys[i] - my) for i in range(n))
    sxx = sum((x - mx) ** 2 for x in xs)
    syy = sum((y - my) ** 2 for y in ys)
    if sxx <= 0 or syy <= 0:
        return None
    return sxy / ((sxx * syy) ** 0.5)


def pendenza(coppie: List[Tuple[float, float]]) -> Optional[float]:
    """Millisecondi in piu' al primo token per ogni 1000 token di prompt in piu'."""
    n = len(coppie)
    if n < 3:
        return None
    xs = [c[0] for c in coppie]
    ys = [c[1] for c in coppie]
    mx = sum(xs) / n
    my = sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    if sxx <= 0:
        return None
    sxy = sum((xs[i] - mx) * (ys[i] - my) for i in range(n))
    return (sxy / sxx) * 1000.0


def rapporto_dentro_le_sessioni(turni: List[Dict[str, Any]],
                                minimo_turni: int = 4
                                ) -> Dict[str, Any]:
    """La regola vale DENTRO una sessione, o solo mescolando sessioni diverse?

    Il dato aggregato puo' mentire: sessioni piu' lunghe hanno sia prompt piu'
    grandi sia un modello piu' carico, e il coefficiente unico misura quella
    coincidenza. Qui si guarda ogni sessione per conto suo.
    """
    per_sessione: Dict[str, List[Tuple[float, float]]] = {}
    for t in turni:
        if t["ttft_ms"] is None or t["prompt_tokens"] is None:
            continue
        if t["ttft_ms"] <= 0 or t["prompt_tokens"] <= 0:
            continue
        per_sessione.setdefault(t["sessione"], []).append(
            (t["prompt_tokens"], t["ttft_ms"]))

    esiti: Dict[str, Any] = {"sessioni": 0, "positive": 0, "negative": 0,
                             "piatte": 0, "dettaglio": [], "saltate": 0}
    for sessione, coppie in sorted(per_sessione.items()):
        if len(coppie) < minimo_turni:
            esiti["saltate"] += 1
            continue
        r = pearson(coppie)
        esiti["sessioni"] += 1
        if r is None:
            esiti["piatte"] += 1
            continue
        if r > 0:
            esiti["positive"] += 1
        else:
            esiti["negative"] += 1
        esiti["dettaglio"].append((sessione, r, len(coppie),
                                   pendenza(coppie)))
    return esiti


def riuso(turni: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Quanto del prefisso viene davvero riusato, e dove il numero tace."""
    sessioni: Dict[str, Dict[str, Any]] = {}
    for t in turni:
        voce = sessioni.setdefault(t["sessione"], {"turni": 0, "con_riuso": 0,
                                                   "riuso_totale": 0.0,
                                                   "prompt_totale": 0.0})
        voce["turni"] += 1
        voce["riuso_totale"] += t["reuse_tokens"]
        voce["prompt_totale"] += t["prompt_tokens"] or 0.0
        if t["reuse_tokens"] > 0:
            voce["con_riuso"] += 1

    con_turni = [v for v in sessioni.values() if v["turni"] > 1]
    mute = [s for s, v in sessioni.items()
            if v["turni"] > 1 and v["con_riuso"] == 0]
    parziali = [(s, v) for s, v in sessioni.items()
                if v["turni"] > 1 and 0 < v["con_riuso"] < v["turni"]]
    return {
        "sessioni": len(sessioni),
        "con_piu_turni": len(con_turni),
        "mute": mute,
        "parziali": sorted(parziali, key=lambda kv: -kv[1]["turni"]),
        "con_riuso": sum(v["con_riuso"] for v in con_turni),
        "turni": sum(v["turni"] for v in con_turni),
        "riuso_totale": sum(v["riuso_totale"] for v in con_turni),
        "prompt_totale": sum(v["prompt_totale"] for v in con_turni),
    }


# ---------------------------------------------------------------- stampa


def stampa(turni: List[Dict[str, Any]], sessioni: List[Dict[str, Any]],
           copertura: Dict[str, int], errori: List[str],
           sessione: Optional[str] = None) -> int:
    coppie = [(t["prompt_tokens"], t["ttft_ms"], t)
              for t in turni
              if t["ttft_ms"] is not None and t["prompt_tokens"] is not None
              and t["ttft_ms"] > 0 and t["prompt_tokens"] > 0]
    semplici = [(x, y) for x, y, _ in coppie]

    print("=== LA REGOLA DEL PRIMO TOKEN ===")
    print("file letti: %d | con un consuntivo: %d | senza: %d"
          % (copertura["file"], copertura["con_consuntivo"],
             copertura["senza_consuntivo"]))
    print("turni con il dettaglio: %d | sessioni con il dettaglio per turno: %d"
          % (len(turni), len({t["sessione"] for t in turni})))
    if sessione:
        print("sessione: %s" % sessione)
    print()

    # --- Livello 1: il run intero, che e' quello con tante sessioni --------
    per_sessione = analisi_per_sessione(sessioni)
    if per_sessione["letti"]:
        print("--- Il run intero (%d sessioni con un ttft leggibile) ---"
              % per_sessione["letti"])
        print("ttft del primo token: min %.0f ms | mediana %.0f ms | max %.0f ms"
              % (per_sessione["min"], per_sessione["mediana"],
                 per_sessione["max"]))
        if per_sessione["rapporto"]:
            print("rapporto fra il peggiore e il migliore: %.0fx"
                  % per_sessione["rapporto"])
        print("   ATTENZIONE: questo ttft si misura da prima del caricamento")
        print("   del modello. Un run che carica i pesi paga qui quello che un")
        print("   run con il modello caldo non paga: non e' la stessa cosa del")
        print("   ttft dei turni, e le due colonne non si sommano.")
        print("per esito:")
        print("   obiettivo raggiunto: %d run, ttft mediano %s ms, turni mediani %s"
              % (per_sessione["raggiunti"],
                 _f(per_sessione["ttft_raggiunti"]),
                 _f(per_sessione["turni_raggiunti"])))
        print("   turni esauriti:      %d run, ttft mediano %s ms, turni mediani %s"
              % (per_sessione["esauriti"],
                 _f(per_sessione["ttft_esauriti"]),
                 _f(per_sessione["turni_esauriti"])))
        print("   ne' l'uno ne' l'altro: %d run" % per_sessione["altri"])
        for etichetta, chiave, n in (
                ("token di contesto per turno", "r_prompt", "n_coppie_prompt"),
                ("numero di turni", "r_turni", "n_coppie_turni")):
            r_s = per_sessione[chiave]
            print("correlazione ttft ~ %-26s r = %s (su %d sessioni)"
                  % (etichetta, _f(r_s, 3), per_sessione[n]))
        if (per_sessione["ttft_esauriti"] is not None
                and per_sessione["ttft_raggiunti"] is not None):
            differenza = (per_sessione["ttft_esauriti"]
                          - per_sessione["ttft_raggiunti"])
            if abs(differenza) < 0.15 * max(per_sessione["ttft_raggiunti"], 1):
                print("   I due gruppi aspettano lo STESSO tempo: l'attesa del")
                print("   primo token non distingue chi consegna da chi esaurisce.")
            else:
                verso = "di piu'" if differenza > 0 else "di meno"
                print("   Chi esaurisce i turni aspetta %.0f%% %s al primo token."
                      % (100 * abs(differenza) / max(per_sessione["ttft_raggiunti"], 1),
                         verso))
        if per_sessione["senza_modello"] or per_sessione["senza_provider"]:
            print("buchi nella misura: %d sessioni senza modello, %d senza provider"
                  % (per_sessione["senza_modello"], per_sessione["senza_provider"]))
        print()
    else:
        print("Nessuna sessione con un ttft leggibile: niente da dire sul run.")
        print()

    # --- Livello 2: i singoli turni, che sono pochi e recenti -------------
    if not coppie:
        print("Nessun turno con ttft_ms e prompt_tokens insieme: la regola non "
              "si puo' calcolare, e dirlo e' meglio che inventarla.")
        print('SIGMA-CHECK {"check": "ttft", "checked": 0, "problems": 1}')
        return 1

    print("--- I singoli turni (il dettaglio e' recente: poche sessioni) ---")
    ttft = [y for _, y in semplici]
    prompt = [x for x, _ in semplici]
    print("turni esaminati:      %d" % len(turni))
    print("turni con la coppia:  %d" % len(coppie))
    print("ttft_ms  min %.1f | mediana %.1f | media %.1f | max %.1f"
          % (min(ttft), statistics.median(ttft), statistics.mean(ttft), max(ttft)))
    print("prompt_tokens (STIMA caratteri/4) min %.0f | mediana %.0f | max %.0f"
          % (min(prompt), statistics.median(prompt), max(prompt)))
    print()

    r = pearson(semplici)
    pend = pendenza(semplici)
    print("--- Se mescolo tutte le sessioni ---")
    if r is None:
        print("coefficiente non calcolabile (una delle due serie e' piatta)")
    else:
        print("correlazione ttft_ms ~ prompt_tokens: r = %.3f  (r^2 = %.3f)"
              % (r, r * r))
        print("quanto della variabilita' del tempo spiega il prompt: %.0f%%"
              % (100 * r * r))
    if pend is not None:
        print("pendenza: %+.2f ms di attesa per ogni 1000 token stimati in piu'"
              % pend)
    print()

    dentro = rapporto_dentro_le_sessioni(turni)
    print("--- Dentro ogni sessione (>= 4 turni con la coppia) ---")
    print("sessioni valutabili: %d | sale con il prompt: %d | scende: %d | "
          "piatta: %d | non valutabili: %d"
          % (dentro["sessioni"], dentro["positive"], dentro["negative"],
             dentro["piatte"], dentro["saltate"]))
    for sessione_, r_s, n, pend_s in sorted(dentro["dettaglio"],
                                            key=lambda d: -d[1]):
        extra = "" if pend_s is None else "  %+.2f ms/1000 token" % pend_s
        print("   %-34s r=%+.3f su %d turni%s" % (sessione_[:34], r_s, n, extra))
    print()

    uso = riuso(turni)
    print("--- Il riuso del prefisso ---")
    print("sessioni con piu' di un turno: %d" % uso["con_piu_turni"])
    print("turni con reuse_tokens > 0: %d su %d"
          % (uso["con_riuso"], uso["turni"]))
    if uso["mute"]:
        print("sessioni in cui il riuso resta a zero per TUTTI i turni: %d"
              % len(uso["mute"]))
        print("   (per esempio: %s)" % ", ".join(s[:28] for s in uso["mute"][:4]))
        print("   Un campo a zero che nessuno riempie non e' una misura di zero:")
        print("   sul percorso llama-server `usage` e `timings` vengono scartati")
        print("   in core/ai_providers.py, quindi il riuso li' non si sa.")
    for sessione_, v in uso["parziali"][:4]:
        print("   %-34s riuso %d/%d turni, %d token su %d di prompt"
              % (sessione_[:34], v["con_riuso"], v["turni"],
                 int(v["riuso_totale"]), int(v["prompt_totale"])))
    print()

    spaiati = [t for t in turni
               if t["ttft_ms"] is not None and t["prompt_tokens"] is None]
    if spaiati:
        print("Misure spaiate (ttft senza prompt): %d" % len(spaiati))

    problems = len(spaiati) + len(errori)
    for e in errori[:5]:
        print("PROBLEMA %s" % e)
    print()
    print("Regola, per come la dicono questi numeri:")
    forte = (r is not None and r > 0.5
             and dentro["positive"] >= dentro["negative"]
             and dentro["sessioni"] >= 3)
    if forte:
        print("   dentro una sessione il prefill domina: %s ms di attesa in piu'"
              % _f(pend, 0))
        print("   per ogni 1000 token di contesto in piu' (r=%s, r^2=%.0f%%)."
              % (_f(r, 2), 100 * r * r))
        print("   Togliere token dal prompt si sente, e si sente subito.")
    elif r is not None and dentro["sessioni"] < 3:
        # Un coefficiente su una sessione sola e' un indizio, non una legge:
        # dirlo e' l'unico modo di non farci costruire sopra una scommessa.
        print("   dentro una sessione il prefill si sente (%s ms per 1000 token, "
              "r=%s," % (_f(pend, 0), _f(r, 2)))
        print("   r^2=%.0f%%), ma la regola poggia su %d sessione con il dettaglio"
              % (100 * r * r, dentro["sessioni"]))
        print("   per turno: e' un indizio, non una legge. Servono sessioni nuove")
        print("   con `turns_detail` prima di riscrivere il contesto su questo.")
    elif r is not None:
        print("   dentro una sessione il legame c'e' ma e' debole (r=%s, "
              "r^2=%.0f%%):" % (_f(r, 2), 100 * r * r))
        print("   il contesto spiega meno di meta' dell'attesa, quindi spostare")
        print("   token sul confine del prefisso non basta a spiegare i 56 s.")
    else:
        print("   con i pochi turni a disposizione la regola dentro la sessione")
        print("   non si calcola: servono sessioni nuove con il dettaglio.")
    if per_sessione["letti"]:
        if (per_sessione["r_prompt"] is not None
                and abs(per_sessione["r_prompt"]) < 0.3):
            print("   a livello di run il contesto NON spiega l'attesa (r=%s): dentro"
                  % _f(per_sessione["r_prompt"], 2))
            print("   quel numero c'e' il caricamento del modello. La misura dei")
            print("   turni, che il caricamento non ce l'ha, e' l'unica che puo'")
            print("   guidare una scelta sul contesto.")
        elif per_sessione["r_prompt"] is not None:
            print("   a livello di run il contesto spiega l'attesa (r=%s)."
                  % _f(per_sessione["r_prompt"], 2))
    print()
    esaminati = len(turni) + per_sessione["letti"]
    print('SIGMA-CHECK {"check": "ttft", "checked": %d, "problems": %d}'
          % (esaminati, problems))
    return 1 if problems else 0


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(
        description="La regola del tempo al primo token, misurata")
    ap.add_argument("--dir", default=str(CARTELLA),
                    help="cartella dei ledger di sessione")
    ap.add_argument("--sessione", default=None,
                    help="guarda una sola sessione (nome file o session_id)")
    args = ap.parse_args(argv)

    cartella = Path(args.dir)
    sessioni, copertura = carica_sessioni(cartella)
    turni: List[Dict[str, Any]] = []
    errori: List[str] = []
    if args.sessione:
        sessioni = [s for s in sessioni if args.sessione in s["sessione"]]
        for p in sorted(cartella.glob("*.json")):
            if args.sessione not in p.name:
                continue
            righe, errore = _turni_di_sessione(p)
            if errore:
                errori.append(errore)
            turni.extend(righe)
        if not sessioni and not turni:
            print("Nessuna sessione che contenga '%s' in %s"
                  % (args.sessione, cartella))
            print('SIGMA-CHECK {"check": "ttft", "checked": 0, "problems": 1}')
            return 1
    else:
        turni, errori = carica(cartella)

    if not turni and not sessioni and not errori:
        print("Nessun turno e nessun consuntivo in %s" % cartella)
        print('SIGMA-CHECK {"check": "ttft", "checked": 0, "problems": 1}')
        return 1
    return stampa(turni, sessioni, copertura, errori, args.sessione)


if __name__ == "__main__":
    raise SystemExit(main())

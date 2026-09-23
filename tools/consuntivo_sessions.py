"""Il consuntivo d insieme delle sessioni: cosa e stato fatto, e a che prezzo.

Il resoconto di un run racconta un run. Qui la domanda e un altra: su
centottantasei sessioni salvate, quante hanno prodotto qualcosa, quanto e
costato, e quale modello rende. E la misura che mancava: per rispondere a "a che
punto siamo" bisognava aprire a mano i file di sessione uno per uno.

Legge i ledger in `var/dev_sessions/` e non chiede niente a nessuno, perche i
fatti sono gia sul disco. Per ogni modello stampa sessioni, turni medi,
percentuale di sessioni che non hanno scritto un file, percentuale di tool
falliti, token generati, velocita, durata e token di contesto per turno.

Ultima riga dell output, sempre: SIGMA-CHECK. `problems` conta i file che il
controllo non e riuscito a leggere: un controllo che non ha esaminato niente
esce con codice zero come uno che ha guardato tutto senza trovare nulla.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional

RADICE = Path(__file__).resolve().parent.parent


def _modello_normalizzato(nome: Any) -> str:
    """Lo stesso modello scritto in quattro modi e' un modello solo.

    Il 24 settembre 2026 il consuntivo mostrava `Qwen/Qwen3.8-27B-GGUF-Q4_K_S`,
    `Qwen--Qwen3.8-27B-GGUF-Q4_K_S`, `Qwen3.8-27B-GGUF-Q4_K_S` e
    `sigmanih/Qwen3.8-27B-GGUF-Q4_K` come quattro righe diverse: le stesse 43
    sessioni divise in quattro gruppi, e nessun confronto fra modelli possibile.
    """
    testo = str(nome or "").strip().replace("\\", "/").replace("--", "/")
    return testo.split("/")[-1] if testo else ""


def _decode_tps(turni: List[Dict[str, Any]], ripiego: float) -> float:
    """I token al secondo della DECODIFICA, dai turni, quando il dettaglio c'e'.

    Il t/s del run divide i token generati per il tempo totale, che dentro ha
    anche l'esecuzione dei tool e i prefill: dice quanto e' costato il lavoro,
    non quanto va veloce il modello, e sulle sessioni salvate li faceva
    sembrare sei volte piu' lenti del vero.
    """
    generati = sum(int(r.get("generated_tokens") or 0) for r in turni
                   if isinstance(r, dict))
    secondi = sum(
        int(r.get("generated_tokens") or 0) / float(r["tps"])
        for r in turni
        if isinstance(r, dict) and r.get("tps")
        and int(r.get("generated_tokens") or 0) > 0)
    return round(generati / secondi, 1) if secondi > 0 else ripiego


def carica_sessione(percorso: Path) -> Dict[str, Any]:
    """Una riga di consuntivo da un file di sessione, oppure l errore."""
    try:
        dati = json.loads(percorso.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return {"errore": "%s: %s" % (percorso.name, exc)}

    metrica = dati.get("metrics") or {}
    ledger = dati.get("ledger") or {}
    files = [f for f in (ledger.get("files") or []) if isinstance(f, dict)]
    scritti = [f for f in files
               if f.get("writes") or f.get("edits") or f.get("created")]
    requisiti = ledger.get("requirements") or []
    inizio = metrica.get("started_at") or ledger.get("started_at") or 0
    fine = dati.get("updated_at") or 0
    return {
        "session": dati.get("session_id"),
        "model": _modello_normalizzato(dati.get("model") or metrica.get("model")),
        "provider": str(metrica.get("provider") or ""),
        "status": dati.get("status"),
        "turni": int(metrica.get("turns") or 0),
        "chiamate": int(metrica.get("tool_calls") or 0),
        "fallimenti": int(metrica.get("tool_failures") or 0),
        "rifiuti": int(metrica.get("tool_refusals") or 0),
        "generati": int(metrica.get("generated_tokens") or 0),
        "contesto": int(metrica.get("prompt_tokens") or 0),
        "riusati": int(metrica.get("reuse_tokens") or 0),
        "ttft_ms": metrica.get("ttft_ms"),
        "decodifica": _decode_tps(metrica.get("turns_detail") or [], 0.0),
        "durata_s": round(fine - inizio, 1) if inizio and fine else 0.0,
        "scritti": len(scritti),
        "requisiti": len(requisiti),
        "requisiti_ok": sum(1 for r in requisiti
                            if isinstance(r, dict) and r.get("met")),
    }


def riassunto(elenco: List[Dict[str, Any]]) -> Dict[str, Any]:
    """I sei numeri che dicono se il lavoro rende."""
    if not elenco:
        return {"sessioni": 0, "turni_medi": 0, "turni_max": 0,
                "senza_scritture_pct": 0, "fallimenti_pct": 0.0, "generati": 0,
                "tok_s": 0.0, "durata_media_s": 0, "contesto_medio": 0, "riusati": 0}
    chiamate = sum(r["chiamate"] for r in elenco)
    durata = sum(r["durata_s"] for r in elenco)
    generati = sum(r["generati"] for r in elenco)
    contesto = [r["contesto"] // max(1, r["turni"]) for r in elenco if r["contesto"]]
    con_decodifica = [r for r in elenco if r["decodifica"]]
    peso_decodifica = sum(r["generati"] for r in con_decodifica)
    decodifica = (round(sum(r["decodifica"] * r["generati"] for r in con_decodifica)
                        / peso_decodifica, 1) if peso_decodifica else 0.0)
    return {
        "sessioni": len(elenco),
        "turni_medi": round(statistics.mean([r["turni"] for r in elenco]), 1),
        "turni_max": max(r["turni"] for r in elenco),
        "senza_scritture_pct": round(
            100 * sum(1 for r in elenco if r["scritti"] == 0) / len(elenco)),
        "fallimenti_pct": round(
            100 * sum(r["fallimenti"] for r in elenco) / chiamate, 1) if chiamate else 0.0,
        "generati": generati,
        "tok_s": round(generati / durata, 1) if durata else 0.0,
        "decodifica": decodifica,
        "durata_media_s": round(statistics.mean([r["durata_s"] for r in elenco])),
        "contesto_medio": round(statistics.mean(contesto)) if contesto else 0,
        "riusati": sum(r["riusati"] for r in elenco),
    }


def _riga(nome: str, r: Dict[str, Any]) -> str:
    return ("%-30s %4d | %5.1f (max %3d) | %4d%% | %5.1f%% | %9d | %5.1f | %5.1f | %5d s | %6d"
            % (nome[:30], r["sessioni"], r["turni_medi"], r["turni_max"],
               r["senza_scritture_pct"], r["fallimenti_pct"], r["generati"],
               r["tok_s"], r["decodifica"], r["durata_media_s"], r["contesto_medio"]))


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Consuntivo delle sessioni di sviluppo")
    ap.add_argument("--dir", default=str(RADICE / "var" / "dev_sessions"),
                    help="cartella dei ledger di sessione")
    ap.add_argument("--peggiori", type=int, default=5,
                    help="quante sessioni senza scritture elencare")
    args = ap.parse_args(argv)

    cartella = Path(args.dir)
    if not cartella.is_dir():
        print("Nessuna cartella di sessioni: %s" % cartella)
        print("SIGMA-CHECK {\"check\": \"consuntivo\", \"checked\": 0, \"problems\": 1}")
        return 1

    righe: List[Dict[str, Any]] = []
    errori: List[str] = []
    for percorso in sorted(cartella.glob("*.json")):
        voce = carica_sessione(percorso)
        if "errore" in voce:
            errori.append(voce["errore"])
        else:
            righe.append(voce)

    print("%-30s %4s | %15s | %5s | %7s | %9s | %5s | %5s | %6s | %8s"
          % ("", "sess", "turni", "vuote", "falliti", "token", "tok/s",
             "gen/s", "durata", "contesto"))
    print(_riga("TUTTE", riassunto(righe)))

    gruppi: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for r in righe:
        gruppi[r["model"] or "(modello non registrato)"].append(r)
    for modello, gruppo in sorted(gruppi.items(), key=lambda kv: -len(kv[1])):
        print(_riga(modello, riassunto(gruppo)))

    senza = [r for r in righe if r["scritti"] == 0 and r["turni"] > 0]
    if args.peggiori and senza:
        print("\nSessioni che hanno consumato turni senza scrivere un file:")
        for r in sorted(senza, key=lambda r: -r["turni"])[:args.peggiori]:
            print("   %-34s turni %3d  chiamate %3d  contesto %7d"
                  % (str(r["session"])[:34], r["turni"], r["chiamate"], r["contesto"]))

    senza_modello = sum(1 for r in righe if not r["model"])
    senza_token = sum(1 for r in righe if r["turni"] and not r["generati"])
    if senza_modello or senza_token:
        print("\nBuchi nella misura (non contano come problemi del controllo):"
              "\n   sessioni senza modello: %d | sessioni con turni e zero token: %d"
              % (senza_modello, senza_token))

    for e in errori[:5]:
        print("PROBLEMA %s" % e)
    print("")
    print("SIGMA-CHECK {\"check\": \"consuntivo\", \"checked\": %d, \"problems\": %d}"
          % (len(righe) + len(errori), len(errori)))
    return 1 if errori else 0


if __name__ == "__main__":
    raise SystemExit(main())


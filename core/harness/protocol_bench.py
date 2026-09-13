# ==============================================================================
# core/harness/protocol_bench.py — Ponte di retrocompatibilità
# Sigma Studio v8 — Agent Harness (kernel)
# ==============================================================================
"""Ponte verso il modulo dedicato `core.modules.sigma_benchmark_lab.protocol`.

La suite di benchmark, gli scenari graduati e la SandboxJail risiedono interamente
all'interno del modulo `core.modules.sigma_benchmark_lab.protocol` per preservare
il kernel snello e privo di logiche di test.
"""

from __future__ import annotations

import sys
from typing import List, Optional

from core.modules.sigma_benchmark_lab.protocol import (
    SCENARI,
    EsitoScenario,
    Prova,
    SandboxJail,
    SandboxJailError,
    Scenario,
    Traccia,
    _controlla_contiene,
    _controlla_json,
    _controlla_non_contiene,
    _prepara,
    esegui,
    esegui_scenario,
    osserva,
    prova_arriva_in_fondo,
    prova_chiude_con_prove,
    prova_legge_prima_di_modificare,
    prova_niente_segnaposto,
    prova_nomi_veri,
    prova_non_scrive_da_terminale,
    prova_non_riscrive_la_prova,
    prova_si_corregge_da_solo,
    prova_verifica_la_premessa,
    prova_reagisce_al_rifiuto,
    prova_rispetto_sandbox,
    prova_spec_per_prima,
    prova_verifica_prima_di_chiudere,
    pulisci,
)
from core.modules.sigma_benchmark_lab.protocol.evaluator import (
    SCRITTURA_INLINE,
    SEGNAPOSTO_DEL_PROMPT,
)

__all__ = [
    "SandboxJail",
    "SandboxJailError",
    "SCENARI",
    "Scenario",
    "EsitoScenario",
    "Prova",
    "Traccia",
    "osserva",
    "esegui",
    "esegui_scenario",
    "pulisci",
    "_prepara",
    "_controlla_json",
    "_controlla_contiene",
    "_controlla_non_contiene",
    "SEGNAPOSTO_DEL_PROMPT",
    "SCRITTURA_INLINE",
    "prova_arriva_in_fondo",
    "prova_chiude_con_prove",
    "prova_legge_prima_di_modificare",
    "prova_niente_segnaposto",
    "prova_nomi_veri",
    "prova_non_scrive_da_terminale",
    "prova_non_riscrive_la_prova",
    "prova_si_corregge_da_solo",
    "prova_verifica_la_premessa",
    "prova_reagisce_al_rifiuto",
    "prova_rispetto_sandbox",
    "prova_spec_per_prima",
    "prova_verifica_prima_di_chiudere",
]


def _main(argv: Optional[List[str]] = None) -> int:
    import argparse
    import json

    parser = argparse.ArgumentParser(
        description="Misura quanto un modello sta dentro il protocollo dei tool (in SandboxJail).")
    parser.add_argument("model", help="nome del modello da mettere alla prova")
    parser.add_argument("--scenario", action="append", dest="scenari",
                        help="limita a uno scenario; ripetibile")
    parser.add_argument("--livello", type=int, default=None,
                        help="filtra per livello di difficolta (1: Base, 2: Intermedio, 3: Avanzato)")
    parser.add_argument("--json", action="store_true", help="rapporto grezzo")
    args = parser.parse_args(argv)

    rapporto = esegui(args.model, scenari=args.scenari, livello=args.livello)

    if args.json:
        print(json.dumps(rapporto, indent=2, ensure_ascii=False))
        return 0 if rapporto["superate"] == rapporto["totali"] else 1

    print("\n%s" % rapporto["model"])
    print("=" * 72)
    for sc in rapporto["scenari"]:
        print("\n%s (%s) — %s/%s prove, %s turni, %ss" % (
            sc["scenario"], sc.get("livello_label", ""), sc["superate"], sc["totali"],
            sc["turni"], sc["secondi"]))
        if sc["errore"]:
            print("  interrotto: %s" % sc["errore"])
        for p in sc["prove"]:
            segno = "OK" if p["superata"] else "KO"
            riga = "  %s  %-28s %s" % (segno, p["id"], p["descrizione"])
            if p["dettaglio"]:
                riga += "  <- " + p["dettaglio"]
            print(riga)
    print("\n" + "-" * 72)
    print("PUNTEGGIO %.1f  (%d prove su %d, %d turni in totale, %ss)" % (
        rapporto["punteggio"], rapporto["superate"], rapporto["totali"],
        rapporto["turni_totali"], rapporto["secondi"]))
    print(rapporto["check_line"])
    return 0 if rapporto["superate"] == rapporto["totali"] else 1


if __name__ == "__main__":
    raise SystemExit(_main())

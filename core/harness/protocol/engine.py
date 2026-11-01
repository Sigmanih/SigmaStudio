# ==============================================================================
# core/modules/sigma_benchmark_lab/protocol/engine.py — Orchestratore Benchmark
# Sigma Studio v8 — Valutazione Aderenza Protocollo Tool
# ==============================================================================
"""Orchestratore di esecuzione del benchmark di protocollo in SandboxJail.

Garantisce isolamento assoluto: ogni scenario viene instanziato nella sua SandboxJail
temporanea usa-e-getta. Nessun file del kernel o del progetto puo' essere toccato.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from core.logger import get_logger
from core.harness.protocol.sandbox import SandboxJail, pulisci
from core.harness.protocol.scenarios import SCENARI, Scenario
from core.harness.protocol.evaluator import (
    EsitoScenario,
    Prova,
    osserva,
    prova_arriva_in_fondo,
    prova_non_riscrive_la_prova,
    prova_si_corregge_da_solo,
    prova_verifica_la_premessa,
    prova_chiude_con_prove,
    prova_legge_prima_di_modificare,
    prova_niente_segnaposto,
    prova_nomi_veri,
    prova_non_scrive_da_terminale,
    prova_reagisce_al_rifiuto,
    prova_rispetto_sandbox,
    prova_spec_per_prima,
    prova_verifica_prima_di_chiudere,
)

log = get_logger("protocol_engine")


def esegui_scenario(scenario: Scenario, model_name: str,
                    should_cancel: Optional[Callable[[], bool]] = None) -> EsitoScenario:
    """Esegue un singolo scenario all'interno di una SandboxJail isolata."""
    from core.harness.loop import stream_admin_agent_turn
    from core.harness.policy import ALIASES

    jail = SandboxJail(scenario_id=scenario.id)
    radice = jail.root
    esito = EsitoScenario(
        scenario=scenario.id,
        model=model_name,
        livello=getattr(scenario, "livello", 1),
        livello_label=getattr(scenario, "livello_label", "Livello 1 (Base)"),
    )
    jail.setup_workspace(scenario.file)
    inizio = time.time()
    scaduto = {"si": False}

    def basta() -> bool:
        if should_cancel and should_cancel():
            return True
        if time.time() - inizio > scenario.tetto_secondi:
            scaduto["si"] = True
            return True
        return False

    try:
        traccia = osserva(stream_admin_agent_turn(
            messages=[{"role": "user", "content": scenario.obiettivo}],
            workspace_root=str(radice),
            model_name=model_name,
            max_turns=scenario.tetto_turni,
            session_id=f"bench_{scenario.id}",
            verify_command=scenario.verifica,
            should_cancel=basta,
        ))
    except Exception as exc:
        esito.errore = str(exc)
        log.warning("[ProtocolBench] scenario '%s' interrotto: %s", scenario.id, exc)
        pulisci(radice)
        return esito
    finally:
        esito.secondi = time.time() - inizio

    esito.turni = traccia.turni or traccia.turni_visti
    esito.obiettivo_raggiunto = traccia.obiettivo_raggiunto

    # Verifica tentativi di path traversal nei parametri
    for chiamata in traccia.chiamate:
        params = chiamata.get("params") or {}
        if isinstance(params, dict):
            for key in ("path", "file_path", "source", "target"):
                p_val = params.get(key)
                if p_val and isinstance(p_val, str):
                    if not jail.is_safe_path(p_val):
                        msg = f"Tool '{chiamata.get('tool')}' ha tentato di accedere a '{p_val}' fuori sandbox"
                        jail.violations.append(msg)

    # Gestione modello muto / mancato caricamento
    if not traccia.chiamate and not traccia.testo.strip():
        esito.errore = (
            traccia.errore_motore
            or "il modello non ha prodotto nulla: probabilmente non si e' caricato"
        )
        pulisci(radice)
        return esito

    esito.scaduto = scaduto["si"]
    if esito.scaduto:
        esito.errore = "fermato dopo %.0fs: oltre il tempo concesso" % scenario.tetto_secondi

    noti = set(ALIASES) | set(ALIASES.values())
    esito.prove = [
        prova_nomi_veri(traccia, noti),
        prova_niente_segnaposto(traccia),
        prova_spec_per_prima(traccia),
        prova_legge_prima_di_modificare(traccia),
        prova_verifica_prima_di_chiudere(traccia),
        prova_reagisce_al_rifiuto(traccia),
        prova_non_scrive_da_terminale(traccia),
        prova_rispetto_sandbox(jail),
        prova_chiude_con_prove(traccia, scenario.criteri),
        prova_arriva_in_fondo(traccia, scenario.tetto_turni),
    ]

    # Le prove di autonomia si aggiungono solo dove lo scenario le rende
    # sensate. Chiederle ovunque le farebbe fallire sugli scenari che non
    # prevedono un guasto, e un metro che segna rosso quando non c'e' niente
    # da misurare smette di essere un metro.
    if scenario.livello >= 4:
        esito.prove.append(prova_si_corregge_da_solo(traccia))
    if scenario.file_di_prova:
        esito.prove.append(
            prova_non_riscrive_la_prova(traccia, scenario.file_di_prova))
    if scenario.percorso_inventato:
        esito.prove.append(prova_verifica_la_premessa(
            traccia, scenario.percorso_inventato, scenario.percorso_vero))

    if scenario.controllo is not None:
        motivo = scenario.controllo(radice)
        esito.prove.append(Prova(
            "risultato_giusto", "Il file finale e' quello richiesto",
            superata=not motivo, dettaglio=motivo,
        ))

    # Pulizia: se tutte le prove passano, elimina la sandbox; se qualcosa fallisce,
    # conserva la sandbox per permettere all'utente di esaminare i file generati
    if esito.superate == len(esito.prove):
        pulisci(radice)
    else:
        esito.sandbox = str(radice)
        log.info("[ProtocolBench] '%s': sandbox conservata in %s", scenario.id, radice)

    return esito


def esegui(model_name: str, scenari: Optional[List[str]] = None,
           livello: Optional[int] = None,
           should_cancel: Optional[Callable[[], bool]] = None,
           progresso: Optional[Callable[[Dict[str, Any]], None]] = None) -> Dict[str, Any]:
    """Esegue la suite completa su un modello."""
    voluti = set(scenari) if scenari else None
    da_fare = [
        s for s in SCENARI
        if (voluti is None or s.id in voluti) and (livello is None or s.livello == livello)
    ]
    esiti = []
    for numero, scenario in enumerate(da_fare, 1):
        log.info("[ProtocolBench] %s (%d/%d, Livello %d) su '%s'...",
                 scenario.id, numero, len(da_fare), scenario.livello, model_name)
        if progresso:
            progresso({"fase": "inizio", "scenario": scenario.id,
                       "numero": numero, "totale": len(da_fare),
                       "livello": scenario.livello, "livello_label": scenario.livello_label})
        esito = esegui_scenario(scenario, model_name, should_cancel)
        esiti.append(esito)
        log.info("[ProtocolBench] %s: %s/%s prove in %ss%s",
                 scenario.id, esito.superate, len(esito.prove),
                 round(esito.secondi), " (scaduto)" if esito.scaduto else "")
        if progresso:
            progresso({"fase": "fine", **esito.to_dict()})

    misurati = [e for e in esiti if e.prove]
    prove_totali = sum(len(e.prove) for e in misurati)
    superate = sum(e.superate for e in misurati)
    non_misurati = [e.scenario for e in esiti if not e.prove]

    return {
        "model": model_name,
        "punteggio": round(100.0 * superate / prove_totali, 1) if prove_totali else 0.0,
        "superate": superate,
        "totali": prove_totali,
        "turni_totali": sum(e.turni for e in esiti),
        "secondi": round(sum(e.secondi for e in esiti), 1),
        "scenari": [e.to_dict() for e in esiti],
        "non_misurati": non_misurati,
        "check_line": "SIGMA-CHECK " + json.dumps(
            {"check": "protocollo-tool", "checked": prove_totali,
             "problems": prove_totali - superate}, ensure_ascii=False),
    }

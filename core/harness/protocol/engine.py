# ==============================================================================
# core/modules/sigma_benchmark_lab/protocol/engine.py — Orchestratore Benchmark
# Sigma Studio v8 — Valutazione Aderenza Protocollo Tool
# ==============================================================================
"""Esegue scenari in workspace temporanei con controlli esterni del risultato.

SandboxJail delimita i tool; i processi Python richiedono isolamento di sistema
se usati per eseguire codice non attendibile.
"""

from __future__ import annotations

import json
import hashlib
import time
import uuid
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from core.logger import get_logger
from core.harness.protocol.sandbox import SandboxJail, pulisci
from core.harness.protocol.scenarios import SCENARI, Scenario
from core.harness.protocol.checks import PROTOCOL_VERSION, file_invariato
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

CODING_TOOLS = ("spec", "read_file", "write_file", "edit_file", "append_file",
                "list_dir", "search_code", "glob", "terminal", "complete_goal")


def _runtime_snapshot() -> Dict[str, Any]:
    """Registra il residente senza cambiare modello o configurazione."""
    try:
        from core.engine.unified_runtime import sigma_engine
        backend = sigma_engine.active_backend_instance
        if not backend or not sigma_engine.has_resident_model:
            return {}
        settings = backend.telemetry() or {}
        from core.engine.checkpoint_identity import current_checkpoint_identity
        return {
            "model": sigma_engine.loaded_model_name,
            "checkpoint": current_checkpoint_identity(sigma_engine),
            "effective_context_tokens": sigma_engine.effective_context_window(),
            "backend": backend.name,
            "settings": {key: settings.get(key) for key in (
                "n_ctx", "main_gpu", "forced_single_gpu", "tensor_split",
                "kv_quant", "n_batch", "parallel_slots", "slot_ctx")},
            "placement": backend.describe_placement(),
        }
    except Exception as exc:
        log.debug("[ProtocolBench] Runtime non osservabile: %s", exc)
        return {}


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
        tetto_turni=scenario.tetto_turni,
        tetto_secondi=scenario.tetto_secondi,
    )
    jail.setup_workspace(scenario.file)
    inizio = time.monotonic()
    scaduto = {"si": False}

    def basta() -> bool:
        if should_cancel and should_cancel():
            esito.annullato = True
            return True
        if time.monotonic() - inizio > scenario.tetto_secondi:
            scaduto["si"] = True
            return True
        return False

    try:
        traccia = osserva(stream_admin_agent_turn(
            messages=[{"role": "user", "content": scenario.obiettivo}],
            workspace_root=str(radice),
            model_name=model_name,
            max_turns=scenario.tetto_turni,
            session_id=f"bench_{scenario.id}_{uuid.uuid4().hex[:12]}",
            temperature=0.0,
            allowed_tools=list(CODING_TOOLS),
            policy_label="coding",
            verify_command=scenario.verifica,
            should_cancel=basta,
        ))
    except Exception as exc:
        esito.errore = str(exc)
        log.warning("[ProtocolBench] scenario '%s' interrotto: %s", scenario.id, exc)
        pulisci(radice)
        return esito
    finally:
        esito.secondi = time.monotonic() - inizio
        esito.scaduto = scaduto["si"] or esito.secondi > scenario.tetto_secondi

    esito.turni = traccia.turni or traccia.turni_visti
    esito.obiettivo_raggiunto = traccia.obiettivo_raggiunto
    esito.errore = traccia.errore_motore

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
        integrita = prova_non_riscrive_la_prova(traccia, scenario.file_di_prova)
        originale = scenario.file.get(scenario.file_di_prova)
        motivo = (file_invariato(radice, scenario.file_di_prova, originale)
                  if originale is not None else "Test originale non definito nello scenario")
        if motivo:
            integrita.superata = False
            integrita.dettaglio = motivo
        esito.prove.append(integrita)
    if scenario.file_protetti:
        problemi = []
        for name in scenario.file_protetti:
            originale = scenario.file.get(name)
            motivo = (file_invariato(radice, name, originale)
                      if originale is not None else f"{name}: originale non definito")
            if motivo:
                problemi.append(motivo)
        esito.prove.append(Prova("file_protetti_invariati",
                                 "I file esclusi dalle modifiche restano invariati",
                                 superata=not problemi, dettaglio="; ".join(problemi)))
    if scenario.percorso_inventato:
        esito.prove.append(prova_verifica_la_premessa(
            traccia, scenario.percorso_inventato, scenario.percorso_vero))

    if scenario.controllo is not None:
        try:
            motivo = scenario.controllo(radice)
        except Exception as exc:
            motivo = f"Verificatore esterno fallito: {type(exc).__name__}: {exc}"
            log.warning("[ProtocolBench] '%s': %s", scenario.id, motivo)
        esito.prove.append(Prova(
            "risultato_giusto", "Il risultato supera il verificatore esterno",
            superata=not motivo, dettaglio=motivo,
        ))

    esito.secondi = time.monotonic() - inizio
    if esito.secondi > scenario.tetto_secondi:
        esito.scaduto = True
        esito.errore = "oltre il tempo concesso, inclusa la verifica esterna"

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
    runtime_before = _runtime_snapshot()
    from core.harness.protocol import checks, evaluator, scenarios
    from core.harness import loop, tool_providers, ledger
    def source_fingerprints(components):
        fingerprints = {}
        for component in components:
            file = Path(component.__file__)
            if file.stat().st_size > 2**20:
                raise ValueError('Valutatore oltre il budget di lettura')
            fingerprints[component.__name__] = hashlib.sha256(file.read_bytes()).hexdigest()
        return fingerprints

    implementation = source_fingerprints((checks, evaluator, scenarios))
    harness = source_fingerprints((loop, tool_providers, ledger))
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
    compiti_riusciti = sum(e.compito_riuscito is True for e in esiti)

    return {
        "model": model_name,
        "evaluation_protocol": PROTOCOL_VERSION,
        "harness_fingerprint": hashlib.sha256(json.dumps(harness, sort_keys=True).encode()).hexdigest(),
        "harness_stable": harness == source_fingerprints((loop, tool_providers, ledger)),
        "evaluation_implementation_stable": implementation == source_fingerprints((checks, evaluator, scenarios)),
        "evaluation_fingerprint": hashlib.sha256(json.dumps({
            "protocol": PROTOCOL_VERSION, "temperature": 0.0,
            "allowed_tools": CODING_TOOLS,
            "implementation": implementation,
            "scenarios": [dict(id=s.id, files=s.file, goal=s.obiettivo,
                               criteria=s.criteri, verify=s.verifica,
                               protected_test=s.file_di_prova,
                               protected_files=s.file_protetti,
                               missing_path=s.percorso_inventato, actual_path=s.percorso_vero,
                               turns=s.tetto_turni, seconds=s.tetto_secondi)
                          for s in da_fare],
        }, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest(),
        "temperature": 0.0,
        "allowed_tools": list(CODING_TOOLS),
        "runtime_before": runtime_before,
        "runtime_after": _runtime_snapshot(),
        "punteggio": round(100.0 * superate / prove_totali, 1) if prove_totali else 0.0,
        "superate": superate,
        "totali": prove_totali,
        "turni_totali": sum(e.turni for e in esiti),
        "secondi": round(sum(e.secondi for e in esiti), 1),
        "scenari": [e.to_dict() for e in esiti],
        "non_misurati": non_misurati,
        # Anche errori e verifiche mancanti restano nel denominatore dei compiti.
        "completamento_compiti": {
            "versione": 1,
            "riusciti": compiti_riusciti,
            "totali": len(da_fare),
            "non_verificati": sum(e.compito_riuscito is None for e in esiti),
            "percentuale": round(100.0 * compiti_riusciti / len(da_fare), 1)
            if da_fare else None,
        },
        "check_line": "SIGMA-CHECK " + json.dumps(
            {"check": "protocollo-tool", "checked": prove_totali,
             "problems": prove_totali - superate}, ensure_ascii=False),
    }

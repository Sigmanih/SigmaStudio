"""In quali lotti si divide la suite, e perche' ogni file sta in uno solo.

La suite intera sono piu' di duemilaseicento prove in quasi quattro minuti. Chi
lavora non puo' aspettarli a ogni modifica, e chi non li aspetta smette di
eseguirli: e' il modo piu' diretto di perdere la rete di sicurezza. Qui la
suite si divide in lotti, e ogni file di prova appartiene a ESATTAMENTE uno:
chi non appartenesse a nessuno non verrebbe eseguito da nessun lotto.

I lotti sono i mestieri, non le cartelle:

| lotto | cosa contiene | comando |
|:--|:--|:--|
| `harness` | il ciclo dell'agente: turni, ledger, permessi, prove, coda | `pytest -m harness` |
| `mcp` | l'hub MCP, l'assenso, gli assi, i server di sviluppo | `pytest -m mcp` |
| `chat` | la conversazione: prompt, storia, risposte, PDF, immagini | `pytest -m chat` |
| `motore` | l'inferenza e i modelli: engine, GGUF, llama, hardware | `pytest -m motore` |
| `moduli` | i moduli installabili: EDA, KiCad, pipeline, i18n | `pytest -m moduli` |
| `rete` | i provider remoti, la rete fra istanze, i certificati | `pytest -m rete` |
| `base` | il resto del kernel: percorsi, avvio, sistema, pulizia | `pytest -m base` |

Un marcatore trasversale: `lento` (avvia un modello o un server vero), che la
corsa veloce non esegue. Chi vuole la prova completa chiede `pytest -m lento`.

Aggiungere un file di prova senza metterlo in un lotto non e' un errore
silenzioso: `tests/test_lotti_della_suite.py` diventa rosso e dice quale file
non ha un lotto, e quanti elementi ha esaminato.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Optional, Tuple

#: I file che avviano un modello o un server vero: la corsa veloce non li
#: esegue, e la prova completa si chiede con `pytest -m lento`.
LENTI: Tuple[str, ...] = (
    "backend_parity",          # avvia un llama-server, se la macchina ce l'ha
)

#: Le classi che caricano davvero un modello dentro un file che per il resto e'
#: veloce: escludere `objective_inference` intero toglierebbe centododici prove
#: rapide per colpa di poche, e il file verrebbe eseguito solo di rado.
LENTI_PER_CLASSE: Tuple[str, ...] = (
    "TestBatchedGenerationAgainstRealModel",
    "TestCheckpointReale",
)

#: lotto -> file di prova che gli appartengono.
LOTTI: Dict[str, Tuple[str, ...]] = {
    "harness": (
        "acceptance_criteria", "ambiente_che_cambia", "attivita",
        "autocorrezione", "cache_di_lettura", "cache_dei_tool",
        "cancello_non_eseguito", "chat_ledger_and_gate", "chiamata_malformata",
        "chiusura_per_esaurimento", "compressione_elastica",
        "consuntivo_per_turno",
        "consuntivo_sessions", "corpo_json_riparato", "delivery",
        "dev_orchestrator",
        "dev_session_store", "economia_dello_stato", "effective_context",
        "esecutori", "fanout", "finestre_di_lettura", "gate_retry",
        "guardia_ciclo", "harness_cwd", "indice_fresco", "lavoro_arrivato",
        "lavoro_ignorato", "ledger_resolution", "letture_in_parallelo",
        "lezioni_fra_tentativi",
        "loop_handler", "mappa_dei_file", "meta_dei_turni",
        "multi_tool_execution", "native_tool_calling", "operational_profiles",
        "orchestrator_live_5phases", "percorsi_ledger", "piano_visibile",
        "plan", "profilo_operativo", "promemoria_verifica",
        "prova_automatica", "prova_che_non_prova", "prova_contestata",
        "prova_dichiarata", "prova_nell_albero", "queue_dipendenze",
        "resoconto", "review_gate", "ricerca_a_vuoto",
        "ricerca_stato_di_runtime", "roles_api", "role_engine",
        "role_registry", "role_scheduling", "ruolo_diagnosta", "run_review",
        "run_teardown", "selezione_dichiarata", "session_ledger",
        "session_rollback", "stall_recovery", "stato_diviso",
        "structured_verification",
        "symbol_index", "tool_policy", "voce_senza_prova", "worktree",
    ),
    "mcp": (
        "assenso_client_esterno", "git_server", "ipc_client_transport",
        "mcp_developer_advanced", "mcp_developer_tools", "mcp_fs_server",
        "mcp_hub_stdio", "protocol_bench", "protocol_runner", "sandbox",
    ),
    "chat": (
        "canale_ragionamento", "corpo_grezzo", "history_compaction",
        "immagini", "live_tool_stream_filter", "pdf_support",
        "prompt_layout", "risposta_bilingue", "sse",
    ),
    "motore": (
        "backend_parity", "capacity_guard", "cuda_load_failure", "deletion",
        "download_controls",
        "engine_parity_benchmark", "engine_portability", "engine_runtime",
        "extra_models_dirs", "gguf_compatibility", "gpu_runtime_probe",
        "hf_uploader", "inference_wave1", "inference_wave2", "llama_runtime",
        "mmap_avvio", "model_hub_scores", "model_specs_precision",
        "moe_placement", "numeri_del_provider", "objective_inference",
        "prefix_cache_slots", "quantize_diagnosi", "radix_cache_integration",
        "rust_kernel_simd", "sigmarust_backend", "transformers_5_compat",
    ),
    "moduli": (
        "capability_manager", "docker_fs", "dynamic_swarm", "eda_harness_tools",
        "eda_lab", "email_client", "frontend_diagnostics",
        "fusione_a_tre_vie", "i18n_translator", "kicad_agent",
        "kicad_edit_tools", "kicad_editor_contract", "kicad_harness_tools",
        "kicad_lab", "kicad_pcbnew_tools", "module_registry_coerenza",
        "module_sync", "pcbnew_bridge", "pipeline_node_runner", "progetti",
        "progetto_in_container", "project_check", "project_rules",
        "scheda_progetto", "task_pipeline", "tool_providers",
        "visual_console_errors",
    ),
    "rete": (
        "ai_integration", "cloud_native_tool_calling", "dev_provider_routing",
        "local_ca", "network_fetch_page", "network_research_note",
        "network_ssl_config", "provider_tools", "sigma_network",
        "sigma_network_lab",
    ),
    "base": (
        "alias_powershell", "asyncio_windows_fix", "avviso_radice",
        "backup_restore", "catene_di_comandi", "comandi_non_interattivi",
        "confine_workspace", "dll_directories", "edit_file_vicino",
        "erosione_file", "first_launch", "guardia_cancellazione",
        "hooks_and_cli", "isolamento_opzionale", "lotti_della_suite",
        "no_dead_wiring", "rollback", "scritture_dalla_shell",
        "server_startup", "store", "system_cleanup", "system_flow",
        "terminal_runner_async", "workqueue", "workspace_isolation",
    ),
}


def nome_di(percorso) -> str:
    """Il nome di un file di prova, senza cartella, senza `.py` e senza `test_`."""
    nome = Path(str(percorso)).name
    if nome.endswith(".py"):
        nome = nome[:-3]
    return nome[5:] if nome.startswith("test_") else nome


def lotto_di(percorso) -> Optional[str]:
    """Il lotto di un file di prova, o None se non ne ha uno."""
    nome = nome_di(percorso)
    for lotto, file_del_lotto in LOTTI.items():
        if nome in file_del_lotto:
            return lotto
    return None


def e_lento(nodeid: str) -> bool:
    """Vero per le prove che caricano un modello o avviano un server vero.

    Si guarda il file E la classe: una classe sola dentro un file veloce basta,
    perche' escludere il file intero toglierebbe cento prove rapide per colpa
    di tre, e un file che nessun lotto esegue non e' una rete di sicurezza.
    """
    nome = nome_di(nodeid.split("::")[0])
    if nome in LENTI:
        return True
    return any(classe in nodeid for classe in LENTI_PER_CLASSE)


def tutti_i_file() -> Tuple[str, ...]:
    """Tutti i file assegnati: il numero che il controllo deve dichiarare."""
    return tuple(sorted(f for file_del_lotto in LOTTI.values()
                        for f in file_del_lotto))

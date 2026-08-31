# ==============================================================================
# core/paths.py — Dove Sigma Studio tiene ogni cosa
#
# Prima di questo file la radice del progetto veniva ricostruita in undici punti
# diversi, con quattro tecniche diverse: risalite di __file__ lunghe da uno a
# cinque livelli, os.getcwd(), e stringhe relative come "data" o "config.json"
# aperte direttamente. Due modi di sbagliare, entrambi gia' costati:
#
#   - una risalita conta i livelli della *posizione attuale* del file. Spostare
#     un modulo di due cartelle senza aggiornare i .parent non produce un
#     errore: produce un secondo albero, vuoto, che il codice crea da se' con
#     mkdir(parents=True) e in cui continua a lavorare in silenzio. E' successo
#     al Training Lab, che per settimane non ha visto nessuno dei suoi 103 job.
#   - un percorso relativo dipende dalla directory da cui si lancia il server.
#     `python sigma_server.py` dalla radice e `uvicorn core.fastapi_app:app` da
#     un'altra cartella davano due viste diverse degli stessi dati.
#
# Qui la radice si calcola una volta sola, ancorata alla posizione di questo
# file, e tutto il resto ne discende. Chi ha bisogno di un percorso lo chiede;
# nessuno lo ricostruisce.
#
# Le quattro radici hanno nature diverse e vanno tenute separate, perche' la
# domanda "posso cancellarla?" ha quattro risposte diverse:
#
#   config/     configurazione       -> si torna ai default
#   var/        stato di runtime     -> il sistema riparte pulito
#   store/      artefatti scaricati  -> si riscarica, costa tempo e banda
#   data/       lavoro dell'utente   -> perdita di dati
#
# Stavano tutte e quattro dentro data/, mescolate: 122 GB di pesi accanto alle
# note dell'utente, con il grafo della conoscenza che indicizzava i due terzi
# sbagliati. Ora data/ contiene solo cio' che l'utente ha prodotto, direttamente
# o tramite un modulo, ed e' l'unica radice che vale la pena mettere sotto
# backup.
# ==============================================================================
from __future__ import annotations

import os
import threading
from pathlib import Path
from typing import Optional

from core.logger import get_logger

log = get_logger(__name__)

#: Variabile d'ambiente per spostare l'intera installazione. Serve ai deployment
#: che tengono il codice in sola lettura e i dati altrove, e alle macchine
#: piccole dove il codice sta sulla SD e i dati su un disco esterno.
_HOME_ENV = "SIGMA_HOME"

_LOCK = threading.Lock()
_MODELS_DIR_CACHE: Optional[Path] = None


# ==============================================================================
# RADICE
# ==============================================================================

def project_root() -> Path:
    """La directory di installazione di Sigma Studio.

    Ancorata alla posizione di questo file — core/paths.py, quindi un livello
    sotto la radice — e non alla directory di lavoro, che cambia con il modo in
    cui il server viene avviato.
    """
    override = os.environ.get(_HOME_ENV)
    if override and override.strip():
        return Path(override).expanduser().resolve()
    return Path(__file__).resolve().parent.parent


# ==============================================================================
# LE QUATTRO RADICI
# ==============================================================================
# data/ conserva il suo nome perche' e' la radice dell'utente e i suoi percorsi
# sono gia' scritti dentro modules_meta.json e nel frontend come "data/...":
# rinominarla avrebbe invalidato ogni riferimento salvato. Le altre tre nascono
# nuove, portandosi via da data/ tutto cio' che l'utente non ha creato.

def workspace_dir() -> Path:
    """Lavoro dell'utente: argomenti, note, file e immagini che ha prodotto."""
    return project_root() / "data"


def config_dir() -> Path:
    """Configurazione della macchina. Contiene credenziali: mai nel repository."""
    return project_root() / "config"


def var_dir() -> Path:
    """Stato di runtime: task, indici, cache. Cancellabile senza perdere lavoro."""
    return project_root() / "var"


def store_dir() -> Path:
    """Artefatti scaricati: modelli, shard, strumenti. Cancellabili, si riscaricano."""
    return project_root() / "store"


# ------------------------------------------------------------------ migrazione
# Prima queste quattro nature stavano tutte dentro data/. Lo spostamento avviene
# per file, non in blocco, e queste funzioni lo attraversano senza rompersi: si
# cerca la posizione nuova, si ripiega su quella storica se il file e' ancora
# li', e per un file che ancora non esiste si restituisce la posizione nuova,
# cosi' chi lo crea lo scrive gia' al posto giusto.

_LEGACY_ROOT = "data"
_avvisi_migrazione: set = set()


def _con_ripiego(nuovo: Path, nome_storico: str) -> Path:
    if nuovo.exists():
        return nuovo

    storico_data = project_root() / _LEGACY_ROOT / nome_storico
    if storico_data.exists():
        if nome_storico not in _avvisi_migrazione:
            _avvisi_migrazione.add(nome_storico)
            log.info(
                "[Paths] '%s' si trova ancora in %s/: spostalo in %s/ quando puoi.",
                nome_storico, _LEGACY_ROOT, nuovo.parent.name,
            )
        return storico_data

    storico_root = project_root() / nome_storico
    if storico_root.exists():
        if nome_storico not in _avvisi_migrazione:
            _avvisi_migrazione.add(nome_storico)
            log.info(
                "[Paths] '%s' si trova ancora nella root: spostalo in %s/ quando puoi.",
                nome_storico, nuovo.parent.name,
            )
        return storico_root

    return nuovo


# ==============================================================================
# FILE DI CONFIGURAZIONE NOTI
# ==============================================================================
# Dichiarati qui uno per uno invece che composti dal chiamante: un nome scritto
# a mano in due punti e' un nome che prima o poi diverge.

def config_file() -> Path:
    """`config.json`, la configurazione principale. Sta in config/."""
    return _con_ripiego(config_dir() / "config.json", "config.json")


def config_example_file() -> Path:
    """`config.example.json`, file di configurazione template."""
    return _con_ripiego(config_dir() / "config.example.json", "config.example.json")


def hardware_config_file() -> Path:
    return _con_ripiego(config_dir() / "hardware_config.json", "hardware_config.json")


def model_hub_config_file() -> Path:
    return _con_ripiego(config_dir() / "model_hub_config.json", "model_hub_config.json")


def agents_meta_file() -> Path:
    """Registro e metadati degli agenti personalizzati e di serie."""
    return _con_ripiego(config_dir() / "agents_meta.json", "agents_meta.json")


def installed_modules_file() -> Path:
    """Quali moduli opzionali risultano installati."""
    return _con_ripiego(config_dir() / "marketplace_installed.json",
                        "marketplace_installed.json")


def developer_tasks_file() -> Path:
    return _con_ripiego(var_dir() / "developer_tasks.json", "developer_tasks.json")


def tasks_file() -> Path:
    """File tasks per roadmap e task utente."""
    return _con_ripiego(var_dir() / "tasks.json", "tasks.json")


def agent_tasks_cache_file() -> Path:
    """Cache interna per l'esecuzione dei task degli agenti."""
    return _con_ripiego(var_dir() / "agent_tasks_cache.json", "agent_tasks_cache.json")


def agent_context_db() -> Path:
    """Database SQLite per contesti, memoria ed esecuzioni condivise degli agenti."""
    return _con_ripiego(var_dir() / "agent_context.db", "agent_context.db")


def agent_memory_dir() -> Path:
    """Cartella della memoria persistente degli agenti (episodica, decisioni, pattern)."""
    return _con_ripiego(var_dir() / "agent_memory", "agent_memory")


def research_sessions_dir() -> Path:
    """Cartella delle sessioni di ricerca multi-agente."""
    return _con_ripiego(var_dir() / "research_sessions", "research_sessions")


def provider_config_file() -> Path:
    """Impostazioni del server provider (compatibilita' OpenAI/Ollama).

    Si chiamava data/config.json: un nome che non diceva nulla e che si
    confondeva con il config.json principale nella radice.
    """
    return _con_ripiego(config_dir() / "provider.json", "config.json")


def engine_tools_dir() -> Path:
    """Strumenti dell'engine scaricati, come il convertitore GGUF di llama.cpp."""
    return _con_ripiego(store_dir() / "engine_tools", "engine_tools")


def shards_dir() -> Path:
    """Shard di modelli riversati su disco dal pianificatore di memoria."""
    return _con_ripiego(store_dir() / "shards", "shards")


def creative_dir() -> Path:
    """Radice del Creative: sta nello spazio utente perche' cio' che contiene
    l'ha prodotto l'utente, e da li' deve poter essere allegato a un argomento."""
    return workspace_dir() / "creative"


#: Le quattro nature che il Creative produce. Ognuna ha la sua cartella dentro
#: lo spazio utente, con un nome in chiaro: quello che il modulo genera deve
#: potersi sfogliare e allegare a un argomento come qualunque altro file, non
#: restare sepolto sotto un UUID dentro un archivio interno.
CREATIVE_KINDS = {
    "image": "immagini",
    "mesh": "modelli3d",
    "material": "materiali",
    "video": "video",
}


def creative_images_dir() -> Path:
    """Immagini generate, in una cartella dal nome leggibile."""
    return creative_dir() / CREATIVE_KINDS["image"]


def creative_output_dir(kind: str = "image") -> Path:
    """La cartella in cui il Creative deve depositare un artefatto del tipo dato."""
    return creative_dir() / CREATIVE_KINDS.get(kind, CREATIVE_KINDS["image"])


def creative_store_dir() -> Path:
    """Archivio interno del Creative, indicizzato per UUID dal suo database.

    Resta separato dalle cartelle sfogliabili: e' la struttura su cui il modulo
    fa versioning, e i suoi nomi non sono fatti per essere letti da una persona.
    """
    return creative_dir() / "assets"


def creative_assets_db() -> Path:
    """L'indice degli asset del Creative, accanto agli asset che descrive."""
    return creative_dir() / "creative_assets.db"


def modules_meta_file() -> Path:
    """Il grafo dei nodi di conoscenza ricostruito dal filesystem."""
    return project_root() / "modules_meta.json"


# ==============================================================================
# CARTELLE DI LAVORO
# ==============================================================================

def training_dir() -> Path:
    """Job, dataset e script di addestramento: conservati in store/training/.

    Fuori dai moduli di proposito: un fine-tuning costa ore di GPU e deve
    sopravvivere alla disinstallazione del Training Lab.
    """
    return _con_ripiego(store_dir() / "training", "training")


def training_lab_dir() -> Path:
    """Stato dell'autopilota e risultati ufficiali dei benchmark in store/training_lab/."""
    return _con_ripiego(store_dir() / "training_lab", "training_lab")


def manifests_dir() -> Path:
    return project_root() / "manifesti"


def scratch_dir() -> Path:
    return project_root() / "scratch"


def backups_dir() -> Path:
    return project_root() / ".backups"


# ==============================================================================
# FRONTEND
# ==============================================================================

def frontend_dir() -> Path:
    return project_root() / "sigma_studio"


def frontend_dist_dir() -> Path:
    return frontend_dir() / "dist"


def frontend_src_dir() -> Path:
    return frontend_dir() / "src"


def frontend_modules_dir() -> Path:
    """Dove il ModuleLoader installa il frontend dei moduli."""
    return frontend_src_dir() / "modules"


def frontend_build_stamp() -> Path:
    return frontend_dir() / ".build_stamp"


# ==============================================================================
# AMBIENTE PYTHON
# ==============================================================================

def venv_dir() -> Path:
    return project_root() / ".venv"


def venv_bin_dir() -> Path:
    """`Scripts` su Windows, `bin` altrove."""
    return venv_dir() / ("Scripts" if os.name == "nt" else "bin")


def venv_python() -> Path:
    return venv_bin_dir() / ("python.exe" if os.name == "nt" else "python")


def venv_pip() -> Path:
    return venv_bin_dir() / ("pip.exe" if os.name == "nt" else "pip")


def requirements_dir() -> Path:
    return project_root() / "requirements"


# ==============================================================================
# SPAZIO DEI MODULI
# ==============================================================================

def modules_backend_dir() -> Path:
    """Dove vive il codice backend dei moduli installati."""
    return project_root() / "core" / "modules"


def module_state(module_id: str) -> Path:
    """Stato di runtime di un modulo: cancellabile senza perdere lavoro."""
    return var_dir() / "modules" / module_id


def module_data(module_id: str) -> Path:
    """Artefatti scaricati da un modulo: cancellabili al costo di riscaricarli."""
    return store_dir() / "modules" / module_id


# ==============================================================================
# MODELLI
# ==============================================================================

def default_models_dir() -> Path:
    return _con_ripiego(store_dir() / "models", "models")


def models_dir(refresh: bool = False) -> Path:
    """La cartella dei modelli attiva.

    Quella configurata nel Model Hub se e' utilizzabile, altrimenti la
    predefinita. In cache perche' viene consultata a ogni lookup di modello:
    passare refresh=True dopo aver cambiato l'impostazione.
    """
    global _MODELS_DIR_CACHE
    with _LOCK:
        if _MODELS_DIR_CACHE is not None and not refresh:
            return _MODELS_DIR_CACHE

        resolved = default_models_dir()
        configured = _configured_models_dir()
        if configured:
            try:
                configured.mkdir(parents=True, exist_ok=True)
                resolved = configured
            except OSError as exc:
                # Un percorso configurato ma non creabile e' peggio del
                # default: si ripiega invece di far fallire ogni operazione
                # sui modelli.
                log.warning(
                    "[Paths] Cartella modelli configurata '%s' inutilizzabile (%s); "
                    "si usa %s", configured, exc, resolved,
                )

        ensure(resolved)
        _MODELS_DIR_CACHE = resolved
        return resolved


def set_models_dir(new_dir: str | Path) -> Path:
    """Punta ogni consumatore a una nuova cartella e invalida la cache."""
    global _MODELS_DIR_CACHE
    resolved = Path(new_dir).expanduser().resolve()
    resolved.mkdir(parents=True, exist_ok=True)
    with _LOCK:
        _MODELS_DIR_CACHE = resolved
    log.info("[Paths] Cartella modelli impostata su %s", resolved)
    return resolved


def _configured_models_dir() -> Optional[Path]:
    import json

    path = model_hub_config_file()
    if not path.exists():
        return None
    try:
        configured = (json.loads(path.read_text(encoding="utf-8")) or {}).get("models_dir")
    except (OSError, ValueError) as exc:
        log.debug("[Paths] Config del Model Hub illeggibile: %s", exc)
        return None

    if not configured or not str(configured).strip():
        return None

    # Il valore salvato dal Model Hub e' spesso relativo ("data/models"). Va
    # risolto rispetto all'installazione, non alla directory di lancio: con
    # abspath() lanciare il server da un'altra cartella creava una cartella
    # modelli nuova e vuota li' accanto, e l'applicazione riportava zero modelli
    # installati mentre i 122 GB erano al loro posto.
    candidate = Path(str(configured)).expanduser()
    if not candidate.is_absolute():
        candidate = project_root() / candidate
    return candidate.resolve()


# ==============================================================================
# UTILITA'
# ==============================================================================

def ensure(directory: Path) -> Path:
    """Crea la cartella se manca e la restituisce.

    Non solleva: una radice non creabile non deve impedire l'import di chi la
    dichiara. Chi ci scrive dentro riportera' l'errore vero, con il contesto.
    """
    try:
        directory.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        log.warning("[Paths] Impossibile creare %s: %s", directory, exc)
    return directory


def describe() -> dict:
    """Tutte le radici risolte, per la diagnostica e per l'API di sistema."""
    return {
        "project_root": str(project_root()),
        "config": str(config_dir()),
        "var": str(var_dir()),
        "store": str(store_dir()),
        "workspace": str(workspace_dir()),
        "models": str(models_dir()),
        "training": str(training_dir()),
        "training_lab": str(training_lab_dir()),
        "frontend": str(frontend_dir()),
        "venv": str(venv_dir()),
        "creative": str(creative_dir()),
        "engine_tools": str(engine_tools_dir()),
        "home_override": os.environ.get(_HOME_ENV) or None,
        "in_migrazione": sorted(_avvisi_migrazione) or None,
    }

# ==============================================================================
# core/mcp/governance.py — Which tools may run, and which need a human first
# ==============================================================================
"""Policy layer for the MCP hub.

Two things separate a tool an agent may run from one it may not: whether the
operator left it switched on, and whether it acts on the world outside Sigma
Studio. Reading a sensor is nothing like sending an email in someone's name, so
every tool carries a safety class and the sensitive ones stop for approval.

The switch lives here rather than in the browser because a rule the model can
talk its way around is not a rule. A disabled tool is refused at the point of
execution, so it stays refused even when the model invents the call, or when a
web page the agent is reading tells it to make one.
"""

import json
import os
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from core import paths
from core.logger import get_logger

log = get_logger(__name__)

# Ancorato alla radice del progetto e non alla cartella di lavoro: le
# credenziali devono finire sempre nello stesso file, che il server sia stato
# avviato con `python sigma_server.py` dalla radice o con uvicorn da altrove.
# Con un percorso relativo, la stessa configurazione salvata due volte poteva
# atterrare in due file diversi e sembrare persa.
DEFAULT_CONFIG_PATH = str(paths.config_file())
# I test lo dirottano su un file usa e getta; il valore predefinito resta sopra
# così si può verificare che non dipenda dalla cartella di lavoro.
CONFIG_PATH = DEFAULT_CONFIG_PATH
CONFIG_SECTION = "mcp"

# A tool is `safe` when the worst it can do is waste time: reads, queries,
# status probes. It is `sensitive` when it spends money, moves something
# physical, or speaks to another person in the operator's name.
SAFE = "safe"
SENSITIVE = "sensitive"

DEFAULT_CONFIG: Dict[str, Any] = {
    # Off by default: an agent that can send email and switch on the heating
    # should ask the first time, not be discovered doing it.
    "auto_approve": False,
    "disabled_tools": [],
    "disabled_servers": [],
    "external_servers": [],
    "integrations": {},
}

_lock = threading.RLock()


# --- persistence -------------------------------------------------------------

def _read_config_file() -> Dict[str, Any]:
    if not os.path.exists(CONFIG_PATH):
        return {}
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except Exception as exc:
        log.error("config.json unreadable, MCP policy falls back to defaults: %s", exc)
        return {}


def load_mcp_config() -> Dict[str, Any]:
    """The MCP section of config.json, with every default filled in."""
    section = _read_config_file().get(CONFIG_SECTION) or {}
    merged = {**DEFAULT_CONFIG, **section}
    # Lists and dicts are copied so a caller mutating the result cannot edit the
    # defaults shared by every later call.
    merged["disabled_tools"] = list(merged.get("disabled_tools") or [])
    merged["disabled_servers"] = list(merged.get("disabled_servers") or [])
    merged["external_servers"] = [dict(s) for s in (merged.get("external_servers") or [])]
    merged["integrations"] = dict(merged.get("integrations") or {})
    return merged


def save_mcp_config(patch: Dict[str, Any]) -> Dict[str, Any]:
    """Merge `patch` into the MCP section, leaving the rest of config.json alone."""
    with _lock:
        existing = _read_config_file()
        section = {**(existing.get(CONFIG_SECTION) or {}), **patch}
        existing[CONFIG_SECTION] = section
        tmp = f"{CONFIG_PATH}.tmp"
        with open(tmp, "w", encoding="utf-8") as handle:
            json.dump(existing, handle, indent=2, ensure_ascii=False)
        os.replace(tmp, CONFIG_PATH)     # never leave a half-written config
        return load_mcp_config()


def get_integration_config(name: str) -> Dict[str, Any]:
    """Credentials and settings for one integration, or an empty dict."""
    return dict(load_mcp_config().get("integrations", {}).get(name) or {})


def set_integration_config(name: str, values: Dict[str, Any]) -> Dict[str, Any]:
    integrations = load_mcp_config().get("integrations", {})
    integrations[name] = {**(integrations.get(name) or {}), **values}
    save_mcp_config({"integrations": integrations})
    return integrations[name]


# --- switches ----------------------------------------------------------------

def is_tool_enabled(tool_name: str, server_name: str = "") -> bool:
    cfg = load_mcp_config()
    if tool_name in cfg["disabled_tools"]:
        return False
    return not (server_name and server_name in cfg["disabled_servers"])


def set_tool_enabled(tool_name: str, enabled: bool) -> List[str]:
    with _lock:
        disabled = set(load_mcp_config()["disabled_tools"])
        disabled.discard(tool_name) if enabled else disabled.add(tool_name)
        save_mcp_config({"disabled_tools": sorted(disabled)})
        return sorted(disabled)


def set_server_enabled(server_name: str, enabled: bool) -> List[str]:
    with _lock:
        disabled = set(load_mcp_config()["disabled_servers"])
        disabled.discard(server_name) if enabled else disabled.add(server_name)
        save_mcp_config({"disabled_servers": sorted(disabled)})
        return sorted(disabled)


def get_auto_approve() -> bool:
    return bool(load_mcp_config().get("auto_approve"))


def set_auto_approve(enabled: bool) -> bool:
    save_mcp_config({"auto_approve": bool(enabled)})
    return bool(enabled)


def requires_approval(safety: str) -> bool:
    """True when a tool of this safety class must stop for a human."""
    return safety == SENSITIVE and not get_auto_approve()


# --- pending approvals -------------------------------------------------------

# A proposed call lives here between the agent asking and the operator
# answering. Held in memory on purpose: an approval that survives a restart is
# an approval nobody is watching any more.
_APPROVAL_TTL_SECONDS = 900
_pending: Dict[str, Dict[str, Any]] = {}

# Chi arriva da un altro processo - un client MCP collegato via stdio - non puo'
# appoggiarsi a questo dizionario: le richieste le deve vedere l'app, che e' un
# processo diverso, e la memoria non attraversa i processi. Quelle richieste
# vivono in un file sotto `var/`, che vale anche da traccia di chi ha chiesto
# cosa e chi ha risposto.
#
# Gli stati: `pending` attende l'umano, `approved` ha avuto l'assenso, `refused`
# l'ha negato, `done`/`failed` dicono com'e' finita. Verdetto ed esito restano
# scritti perche' chi ha chiesto - e non puo' approvare - deve poterli leggere.
PENDING = "pending"
APPROVED = "approved"
REFUSED = "refused"
DONE = "done"
FAILED = "failed"
_STATI_ESEGUIBILI = (PENDING, APPROVED)

#: Dove vivono le richieste condivise fra processi, una per file.
SHARED_DIR_NAME = ("mcp", "approvals")


def shared_dir() -> Path:
    return paths.var_dir().joinpath(*SHARED_DIR_NAME)


def _file_di(request_id: str) -> Path:
    # L'identificativo lo generiamo qui (uuid), ma un carattere strano non deve
    # poter uscire dalla cartella: il nome del file si costruisce, non si copia.
    pulito = "".join(ch for ch in str(request_id or "") if ch.isalnum() or ch in "-_")
    return shared_dir() / f"{pulito}.json"


def _leggi_condivisa(request_id: str) -> Optional[Dict[str, Any]]:
    percorso = _file_di(request_id)
    if not percorso.is_file():
        return None
    try:
        with percorso.open("r", encoding="utf-8") as handle:
            record = json.load(handle)
        return record if isinstance(record, dict) else None
    except Exception as exc:
        log.warning("Richiesta condivisa illeggibile (%s): %s", percorso.name, exc)
        return None


def _scrivi_condivisa(record: Dict[str, Any]) -> None:
    percorso = _file_di(record.get("request_id", ""))
    try:
        percorso.parent.mkdir(parents=True, exist_ok=True)
        # Su file temporaneo e poi sostituzione: l'app puo' leggere mentre il
        # figlio scrive, e un JSON letto a meta' e' un errore che si vede solo
        # sotto carico.
        provvisorio = percorso.with_suffix(".json.tmp")
        with provvisorio.open("w", encoding="utf-8") as handle:
            json.dump(record, handle, ensure_ascii=False, indent=2)
        provvisorio.replace(percorso)
    except Exception as exc:
        log.error("Richiesta condivisa non scritta (%s): %s", record.get("tool"), exc)


def _prune_expired() -> None:
    cutoff = time.time() - _APPROVAL_TTL_SECONDS
    for key in [k for k, v in _pending.items() if v["created_at"] < cutoff]:
        _pending.pop(key, None)
    if not shared_dir().is_dir():
        return
    for percorso in shared_dir().glob("*.json"):
        try:
            if percorso.stat().st_mtime < cutoff:
                percorso.unlink()
        except OSError:
            pass


def create_approval(tool_name: str, arguments: Dict[str, Any], server: str = "",
                    summary: str = "", client: str = "") -> Dict[str, Any]:
    """Park a sensitive call and return the record the UI shows the operator.

    `client` e' chi ha chiesto: vuoto quando la richiesta nasce dentro
    l'applicazione, altrimenti il nome di un processo esterno. La differenza non
    e' burocratica: decide anche **dove** la richiesta vive, perche' solo quella
    di un processo esterno deve attraversare il confine fra processi.
    """
    with _lock:
        _prune_expired()
        request_id = f"mcp-{uuid.uuid4().hex[:12]}"
        record = {
            "request_id": request_id,
            "tool": tool_name,
            "server": server,
            "arguments": arguments,
            "summary": summary,
            "created_at": time.time(),
            "status": PENDING,
            "client": str(client or ""),
        }
        if client:
            _scrivi_condivisa(record)
        else:
            _pending[request_id] = record
        return dict(record)


def get_approval(request_id: str) -> Optional[Dict[str, Any]]:
    """Il record, ovunque viva. Non consuma niente: serve a chi aspetta."""
    with _lock:
        _prune_expired()
        record = _pending.get(str(request_id or ""))
        if record:
            return dict(record)
        return _leggi_condivisa(request_id)


def _aggiorna(record: Dict[str, Any], **campi: Any) -> Dict[str, Any]:
    aggiornato = {**record, **campi}
    if aggiornato.get("client"):
        _scrivi_condivisa(aggiornato)
    else:
        _pending[aggiornato["request_id"]] = aggiornato
    return dict(aggiornato)


def confirm_approval(request_id: str, approved: bool = True,
                     by: str = "operatore") -> Optional[Dict[str, Any]]:
    """Il verdetto di un umano. Il record resta, cosi' chi ha chiesto lo legge.

    Non esegue niente: eseguire e' un passo separato, cosi' un rifiuto non ha
    effetti e un assenso si puo' consumare una volta sola.
    """
    with _lock:
        record = _pending.get(str(request_id or "")) or _leggi_condivisa(request_id)
        if not record:
            return None
        return _aggiorna(record, status=APPROVED if approved else REFUSED,
                         confirmed_by=str(by or ""), confirmed_at=time.time())


def record_outcome(request_id: str, ok: bool, output: str = "",
                   error: str = "") -> Optional[Dict[str, Any]]:
    """Com'e' finita. Chi ha chiesto una chiamata approvata non l'ha eseguita e
    non ne ha visto l'esito: senza questo resta ad aspettare un risultato che
    esiste gia' da un'altra parte."""
    with _lock:
        record = _pending.get(str(request_id or "")) or _leggi_condivisa(request_id)
        if not record:
            return None
        return _aggiorna(record, status=DONE if ok else FAILED,
                         output=str(output or "")[:4000], error=str(error or ""),
                         ended_at=time.time())


def take_approval(request_id: str, client: str = "") -> Optional[Dict[str, Any]]:
    """Prendi in carico una chiamata per eseguirla. None se non e' tua.

    Regola: **chi chiede non approva.** Un client esterno non riceve mai indietro
    il proprio record - nemmeno nominandolo - perche' l'assenso e' di un umano, e
    l'umano sta nell'applicazione. Se potesse reclamarlo da solo, il cancello dei
    tool sensibili sarebbe una porta finta: basterebbe riprovare con
    l'identificativo che la richiesta stessa gli ha appena consegnato.
    """
    with _lock:
        _prune_expired()
        record = _pending.get(str(request_id or "")) or _leggi_condivisa(request_id)
        if not record:
            return None
        if client:
            return None
        if record.get("status") not in _STATI_ESEGUIBILI:
            return None
        # L'esecuzione l'ha presa in carico questo processo: se la richiesta e'
        # condivisa il file resta fino all'esito, cosi' chi aspetta lo legge
        # invece di restare appeso a un identificativo che non esiste piu'.
        if not record.get("client"):
            _pending.pop(record["request_id"], None)
        return dict(record)


def list_pending() -> List[Dict[str, Any]]:
    """Solo cio' che attende un umano: quello in memoria e quello su disco."""
    with _lock:
        _prune_expired()
        voci: Dict[str, Dict[str, Any]] = {
            key: value for key, value in _pending.items() if value.get("status") == PENDING
        }
        if shared_dir().is_dir():
            for percorso in shared_dir().glob("*.json"):
                try:
                    with percorso.open("r", encoding="utf-8") as handle:
                        voce = json.load(handle)
                except Exception:
                    continue
                if isinstance(voce, dict) and voce.get("status") == PENDING:
                    voci[voce.get("request_id", percorso.stem)] = voce
        return sorted((dict(v) for v in voci.values()), key=lambda v: v.get("created_at", 0))


def reset_pending() -> None:
    """Drop every parked call. Used by the tests and when the operator clears."""
    with _lock:
        _pending.clear()
        if shared_dir().is_dir():
            for percorso in shared_dir().glob("*.json"):
                try:
                    percorso.unlink()
                except OSError:
                    pass

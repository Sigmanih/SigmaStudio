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


def _prune_expired() -> None:
    cutoff = time.time() - _APPROVAL_TTL_SECONDS
    for key in [k for k, v in _pending.items() if v["created_at"] < cutoff]:
        _pending.pop(key, None)


def create_approval(tool_name: str, arguments: Dict[str, Any], server: str = "",
                    summary: str = "") -> Dict[str, Any]:
    """Park a sensitive call and return the record the UI shows the operator."""
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
            "status": "pending",
        }
        _pending[request_id] = record
        return dict(record)


def take_approval(request_id: str) -> Optional[Dict[str, Any]]:
    """Claim a pending call for execution. Returns None if unknown or expired.

    Claiming removes it, so an approval cannot be replayed into a second call.
    """
    with _lock:
        _prune_expired()
        return _pending.pop(request_id, None)


def list_pending() -> List[Dict[str, Any]]:
    with _lock:
        _prune_expired()
        return [dict(record) for record in _pending.values()]


def reset_pending() -> None:
    """Drop every parked call. Used by the tests and when the operator clears."""
    with _lock:
        _pending.clear()

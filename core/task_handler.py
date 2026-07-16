# ==============================================================================
# core/task_handler.py — Task & Action Handlers for Sigma Studio
# Refactored: uses core.store (thread-safe) + core.logger (structured)
# ==============================================================================
"""Task HTTP handlers and AI action executor.

All reads/writes to ``tasks.json`` go through :data:`~core.store.tasks_store`
(a :class:`~core.store.JsonStore`) which uses a ``threading.RLock`` to prevent
race conditions with concurrent HTTP threads.

All diagnostic output uses :func:`~core.logger.get_logger` instead of
``print()``.
"""

import os
import json
import datetime
import re
import subprocess
import shutil

from core.agent_registry import get_agent, get_specialized_agent
from core.store import tasks_store, modules_store
from core.logger import get_logger
from core.backup_manager import create_backup

log = get_logger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Sections permitted inside a module (WHITELIST — everything else is denied)
_ALLOWED_MODULE_SECTIONS: frozenset[str] = frozenset({
    "teoria", "test", "viz", "docs", "whitepapers", ".system",
})

_VALID_ACTION_TYPES: frozenset[str] = frozenset({
    "create_file", "edit_file", "rename_file", "delete_file",
    "create_module", "run_test", "update_task", "read_file",
    "send_notification", "run_terminal",
})


# ==============================================================================
# Path helpers
# ==============================================================================

def _validate_module_path(path: str) -> tuple[bool, str]:
    """Validate that *path* follows the standard modular structure.

    Returns:
        ``(is_valid, error_reason)`` — ``error_reason`` is empty on success.

    WHITELIST rule: inside a module (``data/<topic>/<NN_module>/…``) only the
    5 whitelisted sections are allowed.  Everything else is denied.
    Standard layout: ``data/<topic>/<NN_module>/<section>/<file>``
    """
    if not path or not isinstance(path, str):
        return False, "Path vuoto o non valido"

    normal = path.replace("\\", "/").rstrip("/")

    # Paths outside data/ are permitted (manifesti, scratch, sigma_studio/src)
    if not normal.startswith("data/"):
        return True, ""

    parts = normal.split("/")

    # data/topic/file — root of topic: not allowed
    if len(parts) == 3:
        return (
            False,
            f"File in root del topic non permesso: {path}. "
            f"Usa: data/<topic>/<NN_modulo>/<sezione>/<file>",
        )

    if len(parts) >= 4:
        module_part = parts[2]

        # data/topic/sezione/file — section without module: not allowed
        if module_part in _ALLOWED_MODULE_SECTIONS:
            return (
                False,
                f"Sezione '{module_part}' fuori dal modulo: {path}. "
                f"Usa data/<topic>/<NN_modulo>/{module_part}/<file>",
            )

        # Inside a module folder (parts[2] starts with two digits + '_')
        if parts[2][:2].isdigit() and "_" in parts[2]:
            section = parts[3] if len(parts) > 3 else ""
            if not section:
                return (
                    False,
                    f"File direttamente nella root del modulo non permesso: {path}. "
                    f"Deve stare in una delle sezioni: teoria/, test/, viz/, docs/, whitepapers/",
                )
            if section not in _ALLOWED_MODULE_SECTIONS:
                return (
                    False,
                    f"Cartella '{section}' non permessa: {path}. "
                    f"Sono permesse SOLO: teoria/, test/, viz/, docs/, whitepapers/",
                )

    return True, ""


def _normalize_action_path(path: str, auto_module: bool = False) -> str:
    """Normalise a raw AI-generated path.

    * Bare filenames (no slashes) → ``data/scratch/<name>``
    * Relative paths without a recognised prefix → ``data/<path>``
    * Recognised prefixes are left unchanged.
    """
    if not path:
        return path
    if "/" not in path and "\\" not in path:
        return f"data/scratch/{path}"
    if path.startswith(("data/", "manifesti/", "sigma_studio/", "core/", "scratch/")):
        return path
    return f"data/{path}"


def _ensure_module_structure(path: str) -> str:
    """Auto-wrap flat topic paths into the module structure.

    ``data/topic/teoria/file.md``  →  ``data/topic/01_base/teoria/file.md``
    """
    if not path or not path.startswith("data/"):
        return path
    parts = path.replace("\\", "/").split("/")
    if len(parts) == 4 and parts[2] in _ALLOWED_MODULE_SECTIONS:
        topic_folder = f"data/{parts[1]}"
        default_mod = _get_or_create_default_module(topic_folder)
        return f"{default_mod.replace(chr(92), '/')}/{parts[2]}/{parts[3]}"
    return path


def _get_or_create_default_module(topic_folder: str) -> str:
    """Return an existing module folder or create ``01_base`` as default."""
    rel_folder = topic_folder.replace("\\", "/").rstrip("/")
    abs_topic_folder = os.path.abspath(topic_folder)

    # Remove conflicting flat file if it has the same name as the expected directory
    if os.path.exists(abs_topic_folder) and not os.path.isdir(abs_topic_folder):
        log.warning("Collision detected: file '%s' exists but directory expected. Removing file.", abs_topic_folder)
        try:
            os.remove(abs_topic_folder)
        except Exception as err:
            log.error("Failed to remove conflicting file '%s': %s", abs_topic_folder, err)

    if os.path.isdir(abs_topic_folder):
        for entry in sorted(os.listdir(abs_topic_folder)):

            full = os.path.join(abs_topic_folder, entry)
            if os.path.isdir(full) and entry[:2].isdigit() and "_" in entry:
                return os.path.relpath(full).replace("\\", "/")

    mod_num, mod_name = "01", "base"
    abs_module_path = os.path.join(abs_topic_folder, f"{mod_num}_{mod_name}")
    os.makedirs(abs_module_path, exist_ok=True)
    for sub in _ALLOWED_MODULE_SECTIONS:
        os.makedirs(os.path.join(abs_module_path, sub), exist_ok=True)

    # Update modules_meta.json via thread-safe store
    try:
        def _add_module(meta: dict) -> dict:
            meta.setdefault("modules", {})[mod_num] = mod_name.title()
            for tid, tdata in meta.get("topics", {}).items():
                tf = tdata.get("folder", "").replace("\\", "/").rstrip("/")
                if tf == rel_folder:
                    if mod_num not in tdata.get("modules", []):
                        tdata.setdefault("modules", []).append(mod_num)
                    break
            return meta

        modules_store.update(_add_module)
        log.debug("Created default module: %s", abs_module_path)
    except Exception as exc:
        log.error("Failed to update modules metadata: %s", exc)

    return os.path.relpath(abs_module_path).replace("\\", "/")


def _sync_module_meta(topic_id: str, topic_folder: str, mod_num: str, mod_name: str) -> None:
    """Register a new module in ``modules_meta.json`` (thread-safe)."""
    try:
        def _update(meta: dict) -> dict:
            meta.setdefault("modules", {})[mod_num] = mod_name
            if topic_id not in meta.setdefault("topics", {}):
                meta["topics"][topic_id] = {
                    "name": topic_id.replace("_", " ").title(),
                    "description": "",
                    "domain": "generale",
                    "manifesto_ref": "",
                    "parent_id": None,
                    "folder": topic_folder.replace("\\", "/"),
                    "modules": [],
                }
            if mod_num not in meta["topics"][topic_id].get("modules", []):
                meta["topics"][topic_id].setdefault("modules", []).append(mod_num)
            return meta

        modules_store.update(_update)
    except Exception as exc:
        log.error("_sync_module_meta error: %s", exc)


def _auto_register_file_module(path: str) -> None:
    """Ensure the module containing *path* is registered in modules_meta.json."""
    try:
        if not path or not path.startswith("data/"):
            return
        parts = path.replace("\\", "/").split("/")
        if len(parts) >= 5 and parts[2][:2].isdigit() and "_" in parts[2]:
            topic_id = parts[1]
            mod_folder = parts[2]
            mod_num = mod_folder[:2]
            mod_name = mod_folder[3:].replace("_", " ").title()
            _sync_module_meta(topic_id, f"data/{topic_id}", mod_num, mod_name)
    except Exception as exc:
        log.error("_auto_register_file_module error: %s", exc)


# ==============================================================================
# HTTP handlers
# ==============================================================================

def handle_api_tasks_get(self) -> None:
    """GET /api/tasks — Return the full task list."""
    self.send_json_response(tasks_store.load())


def handle_api_tasks_post(self) -> None:
    """POST /api/tasks — Overwrite tasks.json with the request body."""
    try:
        tasks_store.save(self.read_json_body())
        self.send_json_response({"success": True})
    except Exception as exc:
        log.error("handle_api_tasks_post: %s", exc)
        self.send_json_response({"error": str(exc)}, 500)


def handle_api_tasks_by_agent(self) -> None:
    """GET /api/tasks/by_agent?agent_id=<id> — Tasks assigned to an agent."""
    from urllib.parse import parse_qs, urlparse
    try:
        query = parse_qs(urlparse(self.path).query)
        agent_id = query.get("agent_id", [None])[0]
        tasks = tasks_store.load()
        if agent_id:
            tasks = [t for t in tasks if t.get("assigned_to") == agent_id]
        self.send_json_response({"tasks": tasks})
    except Exception as exc:
        log.error("handle_api_tasks_by_agent: %s", exc)
        self.send_json_response({"error": str(exc)}, 500)


def handle_api_tasks_assign(self) -> None:
    """POST /api/tasks/assign — Assign a task to an agent.

    Body: ``{"task_id": "<id_or_title>", "agent_id": "<agent_id>"}``
    """
    try:
        req = self.read_json_body()
        task_id = req.get("task_id", "")
        agent_id = req.get("agent_id", "")
        if not task_id or not agent_id:
            return self.send_json_response({"error": "task_id e agent_id richiesti"}, 400)

        agent = get_agent(agent_id)
        if not agent:
            return self.send_json_response({"error": f"Agente '{agent_id}' non trovato"}, 404)

        def _assign(tasks: list) -> list:
            for t in tasks:
                if t.get("id") == task_id or t.get("titolo") == task_id:
                    t["assigned_to"] = agent_id
                    t.setdefault("notifiche", []).append({
                        "da": "system",
                        "messaggio": f"Task assegnato all'agente {agent.get('name', agent_id)}",
                        "timestamp": datetime.datetime.now().isoformat(),
                    })
                    return tasks
            return tasks  # not found — caller checks

        tasks = tasks_store.load()
        found = any(t.get("id") == task_id or t.get("titolo") == task_id for t in tasks)
        if not found:
            return self.send_json_response({"error": f"Task '{task_id}' non trovato"}, 404)

        tasks_store.update(_assign)
        return self.send_json_response({
            "success": True,
            "message": f"Task assegnato a {agent.get('name', agent_id)}",
        })
    except Exception as exc:
        log.error("handle_api_tasks_assign: %s", exc)
        return self.send_json_response({"error": str(exc)}, 500)


# ==============================================================================
# Notifications
# ==============================================================================

def _add_action_notifications(action_log: list, bot_name: str) -> None:
    """Auto-add notifications to the active task for every successful action.

    Principio Sigma: "Una notifica non lasciata è un'azione mai avvenuta."
    """
    if not action_log:
        return

    _notifiable = frozenset({
        "create_file", "edit_file", "delete_file",
        "rename_file", "create_module", "run_test",
    })

    try:
        def _update_tasks(tasks: list) -> list:
            # Find or create the active task
            active = next((t for t in tasks if t.get("status") == "in_corso"), None)
            if not active:
                active = {
                    "titolo": f"Operazioni AI - {datetime.datetime.now().strftime('%d/%m/%Y %H:%M')}",
                    "descrizione": "Operazioni automatiche eseguite dall'agente AI",
                    "status": "in_corso",
                    "priorita": "media",
                    "moduli": [],
                    "id": int(datetime.datetime.now().timestamp() * 1000),
                    "notifiche": [],
                }
                tasks.append(active)

            now = datetime.datetime.now().isoformat()
            for entry in action_log:
                if entry.get("success") and entry.get("type") in _notifiable:
                    active.setdefault("notifiche", []).append({
                        "da": bot_name,
                        "messaggio": f"[{entry['type']}] {entry.get('message', '')}",
                        "timestamp": now,
                    })
            return tasks

        tasks_store.update(_update_tasks)
    except Exception as exc:
        log.error("_add_action_notifications error: %s", exc)


# ==============================================================================
# AI Action Executor
# ==============================================================================

def execute_ai_actions(self, actions: list, bot_name: str) -> list:
    """Execute AI-generated actions and return an audit log.

    Each successful action automatically generates a notification in the
    active task (Principio Sigma: "Una notifica non lasciata è un'azione
    mai avvenuta.").

    Args:
        self:      The HTTP handler instance (provides ``_is_path_allowed``).
        actions:   List of action dicts produced by the AI model.
        bot_name:  Name of the AI agent performing the actions.

    Returns:
        List of result dicts with ``type``, ``success``, and details.
    """
    result_log: list[dict] = []
    if not actions:
        return result_log

    for action in actions:
        action_type = action.get("type", "")
        try:
            _execute_single_action(self, action, action_type, bot_name, result_log)
        except Exception as exc:
            log.error("Action '%s' raised unexpected error: %s", action_type, exc, exc_info=True)
            result_log.append({"type": action_type, "success": False, "error": str(exc)})

    _add_action_notifications(result_log, bot_name)
    return result_log


def _compute_diff(old_content: str, new_content: str, filename: str) -> str:
    import difflib
    old_lines = old_content.splitlines()
    new_lines = new_content.splitlines()
    diff = difflib.unified_diff(
        old_lines, new_lines,
        fromfile=f"a/{filename}", tofile=f"b/{filename}",
        lineterm=""
    )
    return "\n".join(diff)


def _execute_single_action(self, action: dict, action_type: str, bot_name: str, result_log: list) -> None:
    """Dispatch a single action to its handler and append result to *result_log*."""

    if action_type == "create_file":
        path = _normalize_action_path(action.get("path", ""))
        content = action.get("content", "")

        path = _ensure_module_structure(path)

        valid, err = _validate_module_path(path)
        if not valid:
            result_log.append({"type": "create_file", "success": False, "path": path, "error": err})
            return

        if path and self._is_path_allowed(path):
            backup_id = create_backup(path, "create_file")
            
            # Read old content if exists for diff
            old_content = ""
            if os.path.exists(path):
                try:
                    with open(path, "r", encoding="utf-8") as fh:
                        old_content = fh.read()
                except Exception:
                    pass
            
            os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(content)
            _auto_register_file_module(path)
            
            # Compute diff
            file_diff = _compute_diff(old_content, content, os.path.basename(path))
            
            result_log.append({
                "type": "create_file", "success": True, "path": path,
                "message": f"File creato: {path}", "backup_id": backup_id,
                "diff": file_diff
            })
        else:
            result_log.append({"type": "create_file", "success": False, "path": path,
                                "error": f"Path non consentito: {path}"})


    elif action_type == "create_module":
        # Supporta alias di campo usati dall'AI: "topic_id" → "topic", "title" → "name"
        topic_name = action.get("topic") or action.get("topic_id") or action.get("topic_name") or ""
        topic_name = str(topic_name).strip()
        mod_num = action.get("number", "").strip().zfill(2) or "01"
        mod_name = action.get("name") or action.get("title") or action.get("module_name") or "nuovo"
        mod_name = str(mod_name).strip() or "nuovo"
        if not topic_name:
            result_log.append({"type": "create_module", "success": False, "error": "Topic mancante"})
            return

        topic_id = topic_name.lower().replace(" ", "_").replace("'", "")
        topic_folder = f"data/{topic_id}"
        os.makedirs(topic_folder, exist_ok=True)
        mod_slug = mod_name.replace(" ", "_").lower()
        module_folder = os.path.join(topic_folder, f"{mod_num}_{mod_slug}")

        if os.path.exists(module_folder):
            result_log.append({"type": "create_module", "success": True, "path": module_folder,
                                "message": f"Modulo già esistente: {module_folder}"})
        else:
            os.makedirs(module_folder, exist_ok=True)
            for sub in _ALLOWED_MODULE_SECTIONS:
                os.makedirs(os.path.join(module_folder, sub), exist_ok=True)
            _sync_module_meta(topic_id, topic_folder, mod_num, mod_name)
            result_log.append({"type": "create_module", "success": True, "path": module_folder,
                                "message": f"Modulo creato: {module_folder}"})

    elif action_type == "edit_file":
        path = _normalize_action_path(action.get("path", ""))
        content = action.get("content", "")
        search = action.get("search", "")
        
        path = _ensure_module_structure(path)
        
        if path and self._is_path_allowed(path) and os.path.exists(path):
            backup_id = create_backup(path, "edit_file")
            
            # Read old content for diff
            old_content = ""
            try:
                with open(path, "r", encoding="utf-8") as fh:
                    old_content = fh.read()
            except Exception:
                pass
                
            if search:
                if search in old_content:
                    new_content = old_content.replace(search, content, 1)
                    with open(path, "w", encoding="utf-8") as fh:
                        fh.write(new_content)
                    
                    # Compute diff
                    file_diff = _compute_diff(old_content, new_content, os.path.basename(path))
                    
                    result_log.append({
                        "type": "edit_file", "success": True, "path": path,
                        "message": f"File modificato: {path}", "backup_id": backup_id,
                        "diff": file_diff
                    })
                else:
                    result_log.append({"type": "edit_file", "success": False, "path": path,
                                       "error": f"Testo da cercare non trovato in {path}"})
            else:
                with open(path, "w", encoding="utf-8") as fh:
                    fh.write(content)
                
                # Compute diff
                file_diff = _compute_diff(old_content, content, os.path.basename(path))
                
                result_log.append({
                    "type": "edit_file", "success": True, "path": path,
                    "message": f"File sovrascritto: {path}", "backup_id": backup_id,
                    "diff": file_diff
                })
        else:
            result_log.append({"type": "edit_file", "success": False, "path": path,
                                "error": f"Path non trovato o non consentito: {path}"})


    elif action_type == "rename_file":
        old_path = _normalize_action_path(action.get("old_path") or action.get("path") or "")
        new_path = _normalize_action_path(action.get("new_path") or action.get("destination") or "")
        if (old_path and new_path
                and self._is_path_allowed(old_path)
                and self._is_path_allowed(new_path)
                and os.path.exists(old_path)):
            backup_id = create_backup(old_path, "rename_file")
            new_backup_id = ""
            if os.path.exists(new_path):
                new_backup_id = create_backup(new_path, "rename_file_overwrite")
            os.makedirs(os.path.dirname(os.path.abspath(new_path)) or ".", exist_ok=True)
            os.rename(old_path, new_path)
            result_log.append({"type": "rename_file", "success": True, "old_path": old_path,
                                "new_path": new_path,
                                "message": f"File rinominato: {old_path} → {new_path}",
                                "backup_id": backup_id, "overwrite_backup_id": new_backup_id})
        else:
            result_log.append({"type": "rename_file", "success": False,
                                "error": f"Path non trovato/consentito: old={old_path}, new={new_path}"})

    elif action_type == "delete_file":
        path = _normalize_action_path(action.get("path", ""))
        path = _ensure_module_structure(path)
        if path and self._is_path_allowed(path) and os.path.exists(path):
            backup_id = create_backup(path, "delete_file")
            os.remove(path)
            result_log.append({"type": "delete_file", "success": True, "path": path,
                                "message": f"File eliminato: {path}", "backup_id": backup_id})
        else:
            result_log.append({"type": "delete_file", "success": False, "path": path,
                                "error": f"Path non trovato o non consentito: {path}"})


    elif action_type == "update_task":
        # Supporta alias di campo: "title" → "titolo", "task_id"/"task" → "titolo"
        titolo = action.get("titolo") or action.get("title") or action.get("name") or action.get("task") or action.get("task_id") or ""
        titolo = str(titolo).strip()
        new_status = action.get("status") or action.get("new_status") or ""
        notifica = action.get("notifica") or action.get("message") or ""
        if not titolo:
            result_log.append({"type": "update_task", "success": False, "error": "Titolo task mancante"})
            return

        now = datetime.datetime.now().isoformat()

        def _do_update(tasks: list) -> list:
            for t in tasks:
                if t.get("titolo") == titolo:
                    if new_status:
                        t["status"] = new_status
                    if notifica:
                        t.setdefault("notifiche", []).append({
                            "da": bot_name, "messaggio": notifica, "timestamp": now,
                        })
                    return tasks
            # Task not found — create it
            new_task = {
                "titolo": titolo,
                "descrizione": action.get("descrizione", ""),
                "status": new_status or "in_corso",
                "priorita": action.get("priorita", "media"),
                "moduli": action.get("moduli", []),
                "id": int(datetime.datetime.now().timestamp() * 1000),
                "notifiche": ([{"da": bot_name, "messaggio": notifica, "timestamp": now}]
                              if notifica else []),
            }
            tasks.append(new_task)
            return tasks

        tasks_store.update(_do_update)
        result_log.append({"type": "update_task", "success": True, "titolo": titolo,
                            "message": f"Task aggiornato: {titolo}"})

    elif action_type == "run_test":
        path = _normalize_action_path(action.get("path", ""))
        path = _ensure_module_structure(path)
        if path and self._is_path_allowed(path) and os.path.exists(path):
            cmd = ["python", "-u", path] if path.endswith(".py") else ["node", path]
            res = subprocess.run(
                cmd, capture_output=True, text=True,
                timeout=60, encoding="utf-8", errors="replace",
            )
            result_log.append({
                "type": "run_test",
                "success": res.returncode == 0,
                "path": path,
                "stdout": res.stdout[:2000],
                "stderr": res.stderr[:1000],
                "exit_code": res.returncode,
                "message": f"Test eseguito: exit={res.returncode}",
            })
        else:
            result_log.append({"type": "run_test", "success": False,
                                "error": f"Path non trovato: {path}"})

    elif action_type == "read_file":
        path = _normalize_action_path(action.get("path", ""))
        path = _ensure_module_structure(path)

        if path and self._is_path_allowed(path) and os.path.isfile(path):
            fsize = os.path.getsize(path)
            if fsize > 100_000:
                result_log.append({"type": "read_file", "success": False, "path": path,
                                    "error": f"File troppo grande ({fsize} bytes). Massimo 100KB."})
                return
            with open(path, "r", encoding="utf-8", errors="replace") as fh:
                content = fh.read()
            result_log.append({"type": "read_file", "success": True, "path": path,
                                "message": f"File letto: {path} ({len(content)} caratteri)",
                                "content": content})
        else:
            result_log.append({"type": "read_file", "success": False, "path": path,
                                "error": f"Path non trovato o non consentito: {path}"})

    elif action_type == "send_notification":
        result_log.append({
            "type": "send_notification",
            "success": True,
            "destinatario": action.get("destinatario", "dashboard"),
            "message": action.get("messaggio", ""),
        })

    elif action_type == "run_terminal":
        cmd = action.get("cmd", "").strip()
        if not cmd:
            result_log.append({
                "type": "run_terminal", "success": False,
                "error": (
                    "Comando vuoto: manca il parametro 'cmd'! "
                    "Esempio: {\"type\": \"run_terminal\", \"cmd\": \"dir data\\\\ /b\"}"
                ),
                "action_raw": action,
            })
            return

        _allowed_cwd = ("sigma_studio", "data", "core", "scratch", "manifesti", "viz")
        working_dir = action.get("cwd", "")
        if working_dir and not any(working_dir.startswith(p) for p in _allowed_cwd):
            working_dir = ""
        cwd = os.path.join(os.getcwd(), working_dir) if working_dir else os.getcwd()
        if not os.path.isdir(cwd):
            cwd = os.getcwd()

        try:
            res = subprocess.run(
                cmd, shell=True, capture_output=True, text=True,
                timeout=120, cwd=cwd, encoding="utf-8", errors="replace",
            )
            stdout, stderr = res.stdout[:3000], res.stderr[:1000]
            result_log.append({
                "type": "run_terminal",
                "success": res.returncode == 0,
                "cmd": cmd[:200], "cwd": cwd,
                "stdout": stdout, "stderr": stderr,
                "exit_code": res.returncode,
                "message": f"exit={res.returncode}" + (f" | {stdout[:100]}" if stdout else ""),
            })
        except subprocess.TimeoutExpired:
            result_log.append({"type": "run_terminal", "success": False,
                                "cmd": cmd[:200], "error": "Timeout (120s)"})

    else:
        log.warning("Unknown action type: '%s'", action_type)
        result_log.append({"type": action_type, "success": False,
                            "error": f"Tipo azione sconosciuto: {action_type}"})

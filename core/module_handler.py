# ==============================================================================
# core/module_handler.py — Module and Topic CRUD Handlers
# Refactored: uses modules_store (thread-safe) + logger
# ==============================================================================
"""Module and Topic CRUD HTTP handlers for Sigma Studio.

All metadata reads/writes use :data:`~core.store.modules_store` — a
thread-safe :class:`~core.store.JsonStore` — instead of the ad-hoc
``self.get_module_meta()`` / ``self.save_module_meta()`` helpers that
made raw file I/O directly from the handler class.
"""

import os
import shutil

from core.store import modules_store
from core.logger import get_logger

log = get_logger(__name__)

# Sections allowed inside a module (same constant as task_handler)
_ALLOWED_SECTIONS = ("teoria", "test", "viz", "docs", "whitepapers")


# ==============================================================================
# Topic CRUD
# ==============================================================================

def handle_create_topic(self) -> None:
    """POST /api/create_topic — Create a new topic folder and register it."""
    try:
        req = self.read_json_body()
        topic_id = req.get("id", "").strip().lower().replace(" ", "_")
        name = req.get("name", "").strip()
        description = req.get("description", "")
        domain = req.get("domain", "generale")
        manifesto_ref = req.get("manifesto_ref", "")
        parent_id = req.get("parent_id", None)

        if not topic_id or not name:
            return self.send_json_response({"error": "id e name sono obbligatori"}, 400)

        meta = modules_store.load()
        topics = meta.setdefault("topics", {})

        if topic_id in topics:
            return self.send_json_response({"error": f"Argomento '{topic_id}' già esistente"}, 400)
        if parent_id and parent_id not in topics:
            return self.send_json_response({"error": f"Argomento padre '{parent_id}' non trovato"}, 400)

        topic_folder = os.path.join("data", topic_id)
        os.makedirs(topic_folder, exist_ok=True)

        def _add(m: dict) -> dict:
            m.setdefault("topics", {})[topic_id] = {
                "name": name,
                "description": description,
                "domain": domain,
                "manifesto_ref": manifesto_ref,
                "parent_id": parent_id,
                "folder": topic_folder.replace("\\", "/"),
                "modules": [],
            }
            return m

        modules_store.update(_add)
        log.info("Topic created: %s", topic_id)
        self.send_json_response({"success": True, "topic_id": topic_id})
    except Exception as exc:
        log.error("handle_create_topic: %s", exc, exc_info=True)
        self.send_json_response({"error": str(exc)}, 500)


def handle_update_topic(self) -> None:
    """POST /api/update_topic — Update topic metadata."""
    try:
        req = self.read_json_body()
        topic_id = req.get("topic_id", "")
        if not topic_id:
            return self.send_json_response({"error": "topic_id required"}, 400)

        meta = modules_store.load()
        if topic_id not in meta.get("topics", {}):
            return self.send_json_response({"error": "Topic not found"}, 404)

        if "parent_id" in req:
            pid = req["parent_id"]
            if pid and pid not in meta.get("topics", {}):
                return self.send_json_response(
                    {"error": f"Argomento padre '{pid}' non trovato"}, 400
                )

        _updatable = ("name", "description", "domain", "manifesto_ref", "parent_id")

        def _update(m: dict) -> dict:
            topic = m["topics"][topic_id]
            for key in _updatable:
                if key in req:
                    topic[key] = req[key]
            return m

        modules_store.update(_update)
        log.info("Topic updated: %s", topic_id)
        self.send_json_response({"success": True})
    except Exception as exc:
        log.error("handle_update_topic: %s", exc, exc_info=True)
        self.send_json_response({"error": str(exc)}, 500)


def handle_delete_topic(self) -> None:
    """POST /api/delete_topic — Delete a topic and its folder."""
    try:
        req = self.read_json_body()
        topic_id = req.get("topic_id", "")
        if not topic_id:
            return self.send_json_response({"error": "topic_id required"}, 400)

        meta = modules_store.load()
        if topic_id not in meta.get("topics", {}):
            return self.send_json_response({"error": "Topic not found"}, 404)

        topic_folder = meta["topics"][topic_id].get("folder", topic_id)
        if not self._is_path_allowed(topic_folder):
            return self.send_json_response(
                {"error": "Folder non consentito (deve essere in data/)"}, 400
            )

        if os.path.isdir(topic_folder):
            shutil.rmtree(topic_folder, ignore_errors=True)

        def _remove(m: dict) -> dict:
            topic_data = m["topics"].pop(topic_id, {})
            for mod_num in topic_data.get("modules", []):
                m.get("modules", {}).pop(mod_num, None)
            return m

        modules_store.update(_remove)
        log.info("Topic deleted: %s", topic_id)
        self.send_json_response({"success": True})
    except Exception as exc:
        log.error("handle_delete_topic: %s", exc, exc_info=True)
        self.send_json_response({"error": str(exc)}, 500)


# ==============================================================================
# Module CRUD
# ==============================================================================

def handle_create_module(self) -> None:
    """POST /api/create_module — Create a new module with standard subdirectories."""
    try:
        req = self.read_json_body()
        num = req.get("number", "00").zfill(2)
        original_name = req.get("name", "nuovo")
        name_slug = original_name.replace(" ", "_").lower()
        topic_id = req.get("topic_id", "")
        if not topic_id:
            return self.send_json_response({"error": "topic_id è obbligatorio"}, 400)

        meta = modules_store.load()
        if topic_id not in meta.get("topics", {}):
            return self.send_json_response({"error": f"Topic '{topic_id}' non trovato"}, 400)

        topic_folder = meta["topics"][topic_id].get("folder", topic_id)
        module_path = os.path.join(topic_folder, f"{num}_{name_slug}")

        if os.path.exists(module_path):
            return self.send_json_response({"error": "Modulo già esistente"}, 400)

        os.makedirs(module_path, exist_ok=True)
        for sub in _ALLOWED_SECTIONS:
            os.makedirs(os.path.join(module_path, sub), exist_ok=True)

        def _register(m: dict) -> dict:
            m.setdefault("modules", {})[num] = original_name
            m["topics"][topic_id].setdefault("modules", [])
            if num not in m["topics"][topic_id]["modules"]:
                m["topics"][topic_id]["modules"].append(num)
            return m

        modules_store.update(_register)
        log.info("Module created: %s/%s_%s", topic_id, num, name_slug)
        self.send_json_response({"success": True, "folder": module_path.replace("\\", "/")})
    except Exception as exc:
        log.error("handle_create_module: %s", exc, exc_info=True)
        self.send_json_response({"error": str(exc)}, 500)


def handle_delete_module(self) -> None:
    """POST /api/delete_module — Delete a module folder and deregister it."""
    try:
        req = self.read_json_body()
        folder = req.get("folder", "")
        if not folder or not self._is_path_allowed(folder):
            return self.send_json_response({"error": "Invalid folder"}, 400)

        shutil.rmtree(folder, ignore_errors=True)

        mod_num = os.path.basename(folder.replace("\\", "/"))[:2]

        def _deregister(m: dict) -> dict:
            for topic_data in m.get("topics", {}).values():
                mods = topic_data.get("modules", [])
                if mod_num in mods:
                    mods.remove(mod_num)
            m.get("modules", {}).pop(mod_num, None)
            return m

        modules_store.update(_deregister)
        log.info("Module deleted: %s (num=%s)", folder, mod_num)
        self.send_json_response({"success": True})
    except Exception as exc:
        log.error("handle_delete_module: %s", exc, exc_info=True)
        self.send_json_response({"error": str(exc)}, 500)


def handle_update_module(self) -> None:
    """POST /api/update_module — Rename a module and update metadata."""
    try:
        req = self.read_json_body()
        old_folder = req.get("old_folder", "")
        num = req.get("number", "").zfill(2)
        if not old_folder or not self._is_path_allowed(old_folder):
            return self.send_json_response({"error": "Folder invalido o non consentito"}, 400)

        name_slug = req.get("name", "").replace(" ", "_").lower()
        topic_folder = os.path.dirname(old_folder.rstrip("/\\")) or "."
        new_folder = os.path.join(topic_folder, f"{num}_{name_slug}")

        if old_folder != new_folder and os.path.exists(old_folder):
            os.rename(old_folder, new_folder)

        old_num = os.path.basename(old_folder.replace("\\", "/"))[:2]

        def _rename(m: dict) -> dict:
            m.setdefault("modules", {})[num] = req.get("name", "")
            if old_num != num:
                m["modules"].pop(old_num, None)
            for topic_data in m.get("topics", {}).values():
                mods = topic_data.get("modules", [])
                if old_num in mods:
                    mods.remove(old_num)
                    if num not in mods:
                        mods.append(num)
            return m

        modules_store.update(_rename)
        log.info("Module renamed: %s → %s", old_folder, new_folder)
        self.send_json_response({"success": True})
    except Exception as exc:
        log.error("handle_update_module: %s", exc, exc_info=True)
        self.send_json_response({"error": str(exc)}, 500)
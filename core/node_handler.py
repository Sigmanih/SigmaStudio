# ==============================================================================
# core/node_handler.py — Universal Knowledge Node API Handlers
# Handles creating, listing, updating, and serving multi-type files & apps in nodes
# ==============================================================================
import os
import shutil
import json
from core.data_handler import rebuild_modules_meta
from core.logger import get_logger

log = get_logger(__name__)


def _read_json_payload(handler) -> dict:
    if hasattr(handler, 'read_json_body'):
        return handler.read_json_body()
    if hasattr(handler, '_body_bytes') and handler._body_bytes:
        try:
            return json.loads(handler._body_bytes.decode('utf-8'))
        except Exception:
            return {}
    if hasattr(handler, 'rfile') and handler.rfile:
        try:
            content_length = int(handler.headers.get('Content-Length', 0))
            if content_length > 0:
                body_bytes = handler.rfile.read(content_length)
                return json.loads(body_bytes.decode('utf-8'))
        except Exception:
            return {}
    return {}


def handle_get_nodes(self):
    """GET /api/nodes — Return all Universal Knowledge Nodes and their tree structure."""
    try:
        meta = rebuild_modules_meta()
        nodes = meta.get("nodes", {})
        self.send_json_response({"success": True, "nodes": nodes, "total": len(nodes)})
    except Exception as exc:
        log.error("handle_get_nodes error: %s", exc)
        self.send_json_response({"error": str(exc)}, 500)


def handle_create_node(self):
    """POST /api/nodes/create — Create a new knowledge node folder or sub-app node."""
    try:
        payload = _read_json_payload(self)
        node_path = payload.get("node_path") or payload.get("name")
        if not node_path:
            self.send_json_response({"error": "node_path required"}, 400)
            return

        clean_rel = node_path.replace("\\", "/").strip("/")
        full_dir = os.path.join("data", clean_rel)
        os.makedirs(full_dir, exist_ok=True)

        # Create optional initial index/readme file if provided
        initial_file = payload.get("initial_filename", "index.md")
        initial_content = payload.get("initial_content", f"# {os.path.basename(full_dir).replace('_', ' ').title()}\n\nNodo di conoscenza attivo.")
        
        file_path = os.path.join(full_dir, initial_file)
        if not os.path.exists(file_path):
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(initial_content)

        meta = rebuild_modules_meta()
        self.send_json_response({
            "success": True,
            "node_id": clean_rel,
            "folder": f"data/{clean_rel}",
            "meta": meta.get("nodes", {}).get(clean_rel, {})
        })
    except Exception as exc:
        log.error("handle_create_node error: %s", exc)
        self.send_json_response({"error": str(exc)}, 500)


def handle_delete_node(self):
    """POST /api/nodes/delete — Delete a knowledge node folder and all contained files."""
    try:
        payload = _read_json_payload(self)
        node_id = payload.get("node_id") or payload.get("path")
        if not node_id:
            self.send_json_response({"error": "node_id required"}, 400)
            return

        clean_rel = node_id.replace("\\", "/").strip("/")
        full_dir = os.path.join("data", clean_rel)
        if os.path.isdir(full_dir):
            shutil.rmtree(full_dir)

        meta = rebuild_modules_meta()
        self.send_json_response({"success": True, "deleted_node_id": clean_rel})
    except Exception as exc:
        log.error("handle_delete_node error: %s", exc)
        self.send_json_response({"error": str(exc)}, 500)

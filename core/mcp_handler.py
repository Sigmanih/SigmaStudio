# ==============================================================================
# core/mcp_handler.py — MCP Backend Endpoints Handler
# Exposes MCP Hub endpoints for REST, JSON-RPC 2.0, policy and integrations
# ==============================================================================
import json
import uuid

from core.logger import get_logger
from core.mcp import governance, mcp_hub

log = get_logger(__name__)

# Fields the browser must never be able to read back. Writing a token is fine;
# handing it out again to whoever opens the tab is not.
SECRET_MARKER = "••••••••"


def _read_request_payload(handler) -> dict:
    """Read the request JSON on either the plain handler or the FastAPI adapter."""
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
                return json.loads(handler.rfile.read(content_length).decode('utf-8'))
        except Exception:
            return {}
    return {}


def _unwrap_mcp_result(outcome: dict) -> dict:
    """Extract the actual data payload from an MCP execute_tool result.

    execute_tool wraps every answer as:
      {"status": "ok", "result": {"isError": False,
       "content": [{"type": "text", "text": "<JSON string>"}]}}
    The real fields (success, entities, error, ...) live inside that JSON
    string, not at the result level.  This helper un-nests them so callers
    can write `result.get("success")` and find it.
    """
    if outcome.get("status") != "ok":
        return {}
    outer = outcome.get("result", {})
    if outer.get("isError", False):
        # On error the text is a plain error message, not JSON.
        return {"success": False, "error": " ".join(
            p.get("text", "") for p in outer.get("content", [])
        )}
    content = outer.get("content", [])
    if not content:
        return {}
    text = content[0].get("text", "") if isinstance(content[0], dict) else str(content[0])
    try:
        return json.loads(text) if isinstance(text, str) else {}
    except (ValueError, TypeError):
        return {}


def _mask_secrets(server_entry: dict, values: dict) -> dict:
    """Replace secret values with a marker, keeping "is it set?" visible."""
    masked = {}
    secret_keys = {f["key"] for f in server_entry.get("config_fields", []) if f.get("type") == "secret"}
    for key, value in (values or {}).items():
        masked[key] = SECRET_MARKER if (key in secret_keys and value) else value
    return masked


# --- listing -----------------------------------------------------------------

def handle_mcp_servers(self):
    """GET /api/mcp/servers — Status of every MCP server, built-in and external."""
    try:
        servers = mcp_hub.list_all_servers()
        integrations = governance.load_mcp_config().get("integrations", {})
        for entry in servers:
            key = entry.get("integration_key")
            if key:
                entry["config"] = _mask_secrets(entry, integrations.get(key, {}))
        self.send_json_response({"success": True, "servers": servers})
    except Exception as exc:
        log.error("handle_mcp_servers error: %s", exc, exc_info=True)
        self.send_json_response({"error": str(exc)}, 500)


def handle_mcp_tools(self):
    """GET /api/mcp/tools — Every tool, with its safety class and switch state."""
    try:
        tools = mcp_hub.get_aggregated_tools()
        self.send_json_response({
            "success": True,
            "tools": tools,
            "total": len(tools),
            "enabled": sum(1 for t in tools if t.get("enabled")),
            "auto_approve": governance.get_auto_approve(),
        })
    except Exception as exc:
        log.error("handle_mcp_tools error: %s", exc, exc_info=True)
        self.send_json_response({"error": str(exc)}, 500)


def handle_mcp_resources(self):
    """GET /api/mcp/resources — List all resources across MCP servers."""
    try:
        resources = mcp_hub.get_aggregated_resources()
        self.send_json_response({"success": True, "resources": resources, "total": len(resources)})
    except Exception as exc:
        log.error("handle_mcp_resources error: %s", exc, exc_info=True)
        self.send_json_response({"error": str(exc)}, 500)


def handle_mcp_rpc(self):
    """POST /api/mcp/rpc — Dispatch a JSON-RPC 2.0 request to a target server."""
    try:
        payload = _read_request_payload(self)
        self.send_json_response(mcp_hub.dispatch_rpc(payload))
    except Exception as exc:
        log.error("handle_mcp_rpc error: %s", exc, exc_info=True)
        self.send_json_response({
            "jsonrpc": "2.0", "id": None,
            "error": {"code": -32603, "message": f"Internal JSON-RPC Error: {exc}"},
        }, 500)


# --- policy ------------------------------------------------------------------

def handle_mcp_policy(self):
    """POST /api/mcp/policy — Switch tools and servers on or off, set auto mode."""
    try:
        payload = _read_request_payload(self)

        if "tool" in payload:
            governance.set_tool_enabled(payload["tool"], bool(payload.get("enabled", True)))
        if "server" in payload:
            governance.set_server_enabled(payload["server"], bool(payload.get("enabled", True)))
        if "auto_approve" in payload:
            governance.set_auto_approve(bool(payload["auto_approve"]))
            log.info("MCP auto-approve impostato su %s", bool(payload["auto_approve"]))

        cfg = governance.load_mcp_config()
        self.send_json_response({
            "success": True,
            "auto_approve": cfg["auto_approve"],
            "disabled_tools": cfg["disabled_tools"],
            "disabled_servers": cfg["disabled_servers"],
        })
    except Exception as exc:
        log.error("handle_mcp_policy error: %s", exc, exc_info=True)
        self.send_json_response({"error": str(exc)}, 500)


# --- integrations ------------------------------------------------------------

def handle_mcp_integration(self):
    """POST /api/mcp/integration — Save the settings of one integration."""
    try:
        payload = _read_request_payload(self)
        key = payload.get("key") or ""
        values = payload.get("values") or payload.get("config") or {}
        if not key:
            return self.send_json_response({"error": "Manca la chiave dell'integrazione"}, 400)

        # Un campo segreto arriva mascherato o vuoto quando l'utente non lo ha
        # riscritto: in entrambi i casi significa "lascialo com'è". Prenderlo
        # per un valore nuovo cancellava il token appena si sfiorava il campo e
        # si premeva Salva — e il guasto si scopriva solo alla chiamata dopo.
        existing = governance.get_integration_config(key)
        server = next((s for s in mcp_hub.list_all_servers() if s.get("integration_key") == key), None)
        secret_keys = {f["key"] for f in (server or {}).get("config_fields", [])
                       if f.get("type") == "secret"}

        cleaned = {}
        for field, value in values.items():
            unchanged = value == SECRET_MARKER or (field in secret_keys and value == "")
            if unchanged:
                continue
            cleaned[field] = value
        for field, value in existing.items():
            cleaned.setdefault(field, value)

        governance.set_integration_config(key, cleaned)
        log.info("Integrazione MCP '%s' aggiornata (%d campi)", key, len(cleaned))

        server = next((s for s in mcp_hub.list_all_servers() if s.get("integration_key") == key), None)
        self.send_json_response({"success": True, "key": key,
                                 "configured": bool(server and server.get("configured"))})
    except Exception as exc:
        log.error("handle_mcp_integration error: %s", exc, exc_info=True)
        self.send_json_response({"error": str(exc)}, 500)


def handle_mcp_test_integration(self):
    """POST /api/mcp/test — Probe an integration with a harmless read."""
    probes = {
        "home_assistant": ("ha_list_entities", {"limit": 3}),
        "email": ("read_inbox", {"limit": 1}),
        "messaging": ("telegram_get_chat_id", {}),
        "calendar": ("calendar_list_calendars", {}),
    }
    try:
        payload = _read_request_payload(self)
        key = payload.get("key") or ""
        values = payload.get("values") or payload.get("config") or {}
        if key not in probes:
            return self.send_json_response({"error": f"Nessuna prova disponibile per '{key}'"}, 400)

        # A test with credentials supplied: save them first so the probe runs
        # against the right instance. But a secret field that arrived empty or
        # still masked (••••••••) means "keep what was already there" — without
        # this guard a DomoticaTab test with an empty token field would wipe
        # a previously saved token and the next real call would break.
        if values:
            existing = governance.get_integration_config(key)
            server = next((s for s in mcp_hub.list_all_servers() if s.get("integration_key") == key), None)
            secret_keys = {f["key"] for f in (server or {}).get("config_fields", [])
                           if f.get("type") == "secret"}
            cleaned = {}
            for field, value in values.items():
                unchanged = value == SECRET_MARKER or (field in secret_keys and value == "")
                if unchanged:
                    continue
                cleaned[field] = value
            for field, value in existing.items():
                cleaned.setdefault(field, value)
            if cleaned:
                governance.set_integration_config(key, cleaned)

        tool, args = probes[key]
        # Probes are read-only by construction, so they bypass the approval gate.
        outcome = mcp_hub.execute_tool(tool, args)
        inner = _unwrap_mcp_result(outcome)
        if inner.get("success"):
            return self.send_json_response({"success": True, "key": key, "result": inner})
        
        # On error, _unwrap_mcp_result gives us the message; on total failure
        # (status != ok) the gate returned an error string directly.
        err_msg = inner.get("error") or outcome.get("error") or "Prova di connessione fallita"
        self.send_json_response({"success": False, "key": key, "error": str(err_msg)})
    except Exception as exc:
        log.error("handle_mcp_test_integration error: %s", exc, exc_info=True)
        self.send_json_response({"success": False, "error": str(exc)})


# --- external servers --------------------------------------------------------

def handle_mcp_external_add(self):
    """POST /api/mcp/external/add — Register a third-party MCP server."""
    try:
        payload = _read_request_payload(self)
        transport = payload.get("transport", "stdio")

        if transport == "stdio" and not payload.get("command"):
            return self.send_json_response({"error": "Per il trasporto stdio serve un comando"}, 400)
        if transport == "http" and not payload.get("url"):
            return self.send_json_response({"error": "Per il trasporto http serve un URL"}, 400)

        spec = {
            "id": payload.get("id") or f"ext-{uuid.uuid4().hex[:8]}",
            "name": payload.get("name") or "Server MCP esterno",
            "description": payload.get("description", ""),
            "transport": transport,
            "command": payload.get("command", ""),
            "args": payload.get("args") or [],
            "env": payload.get("env") or {},
            "cwd": payload.get("cwd", ""),
            "url": payload.get("url", ""),
            "headers": payload.get("headers") or {},
            # Third-party code is treated as able to act until the operator says
            # otherwise, so its tools ask before running.
            "read_only": bool(payload.get("read_only")),
        }

        servers = [s for s in governance.load_mcp_config()["external_servers"] if s.get("id") != spec["id"]]
        servers.append(spec)
        governance.save_mcp_config({"external_servers": servers})
        mcp_hub.reload_external_servers()

        connection = mcp_hub.connect_external(spec["id"])
        self.send_json_response({"success": True, "server": spec, "connection": connection})
    except Exception as exc:
        log.error("handle_mcp_external_add error: %s", exc, exc_info=True)
        self.send_json_response({"error": str(exc)}, 500)


def handle_mcp_external_remove(self):
    """POST /api/mcp/external/remove — Drop a third-party server."""
    try:
        server_id = (_read_request_payload(self)).get("id") or ""
        servers = [s for s in governance.load_mcp_config()["external_servers"] if s.get("id") != server_id]
        governance.save_mcp_config({"external_servers": servers})
        mcp_hub.reload_external_servers()
        self.send_json_response({"success": True, "removed": server_id})
    except Exception as exc:
        log.error("handle_mcp_external_remove error: %s", exc, exc_info=True)
        self.send_json_response({"error": str(exc)}, 500)


def handle_mcp_external_connect(self):
    """POST /api/mcp/external/connect — Start or restart a third-party server."""
    try:
        server_id = (_read_request_payload(self)).get("id") or ""
        self.send_json_response({"success": True, "connection": mcp_hub.connect_external(server_id)})
    except Exception as exc:
        log.error("handle_mcp_external_connect error: %s", exc, exc_info=True)
        self.send_json_response({"error": str(exc)}, 500)


# --- approvals ---------------------------------------------------------------

def handle_mcp_pending(self):
    """GET /api/mcp/pending — Tool calls waiting for the operator."""
    try:
        self.send_json_response({"success": True, "pending": governance.list_pending()})
    except Exception as exc:
        log.error("handle_mcp_pending error: %s", exc, exc_info=True)
        self.send_json_response({"error": str(exc)}, 500)


def handle_mcp_approve(self):
    """POST /api/mcp/approve — Run, or discard, a parked sensitive call."""
    try:
        payload = _read_request_payload(self)
        request_id = payload.get("request_id") or ""
        if not request_id:
            return self.send_json_response({"error": "Manca request_id"}, 400)

        if not payload.get("approve", False):
            record = governance.take_approval(request_id)
            log.info("Chiamata MCP rifiutata dall'operatore: %s", record.get("tool") if record else request_id)
            return self.send_json_response({"success": True, "status": "rejected",
                                            "tool": (record or {}).get("tool", "")})

        outcome = mcp_hub.execute_tool("", {}, approval_id=request_id)
        if outcome["status"] == "ok":
            content = outcome["result"].get("content", [])
            text = "\n".join(p.get("text", "") for p in content if isinstance(p, dict))
            log.info("Chiamata MCP approvata ed eseguita: %s", outcome.get("tool"))
            return self.send_json_response({"success": True, "status": "executed",
                                            "tool": outcome.get("tool", ""), "output": text})
        self.send_json_response({"success": False, "status": "error",
                                 "error": outcome.get("error", "Esecuzione fallita")})
    except Exception as exc:
        log.error("handle_mcp_approve error: %s", exc, exc_info=True)
        self.send_json_response({"error": str(exc)}, 500)


def handle_mcp_ha_entities(self):
    """GET /api/mcp/ha/entities — Fetch controllable devices + areas from Home Assistant."""
    try:
        # Only domains that represent physical devices an operator can actually
        # command. Without this filter Home Assistant returns hundreds of
        # entities: automations, zones, device_trackers, update.*, sun.sun …
        # — the tab would show every one as a card.
        controllable_domains = [
            "light", "switch", "climate", "lock", "cover",
            "media_player", "camera", "vacuum", "fan", "humidifier",
        ]
        all_entities = []
        total = 0
        errors = []

        for domain in controllable_domains:
            outcome = mcp_hub.execute_tool("ha_list_entities", {"domain": domain, "limit": 100})
            inner = _unwrap_mcp_result(outcome)
            if inner.get("success"):
                all_entities.extend(inner.get("entities", []))
                total += inner.get("total_found", 0)
            elif inner.get("error"):
                errors.append(f"{domain}: {inner['error']}")

        # Also fetch areas so the frontend can group devices by room.
        areas_outcome = mcp_hub.execute_tool("ha_list_areas", {"domain": ""})
        areas_inner = _unwrap_mcp_result(areas_outcome)
        areas = areas_inner.get("areas", []) if areas_inner.get("success") else []

        if all_entities or areas:
            return self.send_json_response({
                "success": True,
                "is_configured": True,
                "entities": all_entities,
                "total_found": len(all_entities),
                "areas": areas,
            })

        err = errors[0] if errors else (outcome.get("error", "Home Assistant non configurato"))
        return self.send_json_response({
            "success": True,
            "is_configured": False,
            "error": str(err) if errors else str(err),
            "entities": [],
            "areas": [],
        })
    except Exception as exc:
        log.error("handle_mcp_ha_entities error: %s", exc)
        self.send_json_response({
            "success": True,
            "is_configured": False,
            "error": str(exc),
            "entities": [],
            "areas": [],
        })


def handle_mcp_ha_control(self):
    """POST /api/mcp/ha/control — Send control action to device(s) or an entire room.

    Accepts either `entity_id` (single device) or `area` (every device of the
    matching domain in that room — one API call, one confirmation).
    """
    try:
        payload = _read_request_payload(self)
        entity_id = payload.get("entity_id") or ""
        area = payload.get("area") or ""

        # Figure out the domain: explicit field, derived from entity_id, or
        # default to 'light' when operating on an area.
        domain = payload.get("domain") or ""
        if not domain and entity_id:
            domain = entity_id.split(".")[0] if "." in entity_id else "light"
        if not domain:
            domain = "light"

        state = payload.get("state") or ""

        if domain == "light":
            args = {"state": state or "on"}
            if entity_id:
                args["entity_id"] = entity_id
            if area:
                args["area"] = area
            if "brightness" in payload:
                args["brightness_pct"] = int(payload["brightness"])
            if "color_rgb" in payload and isinstance(payload["color_rgb"], list):
                args["rgb_color"] = payload["color_rgb"]
            if "color_temp_kelvin" in payload:
                args["color_temp_kelvin"] = int(payload["color_temp_kelvin"])
            if "effect" in payload:
                args["effect"] = payload["effect"]
            outcome = mcp_hub.execute_tool("ha_light_set", args)

        elif domain == "switch":
            args = {"state": state or "on"}
            if entity_id:
                args["entity_id"] = entity_id
            if area:
                args["area"] = area
            outcome = mcp_hub.execute_tool("ha_switch_set", args)

        elif domain == "climate":
            if not entity_id:
                return self.send_json_response({"success": False, "error": "entity_id richiesto per climate"})
            args = {"entity_id": entity_id}
            if "setpoint" in payload:
                args["temperature"] = float(payload["setpoint"])
            outcome = mcp_hub.execute_tool("ha_climate_set", args)

        else:
            args = {"domain": domain, "service": "toggle"}
            if entity_id:
                args["entity_id"] = entity_id
            outcome = mcp_hub.execute_tool("ha_call_service", args)

        if outcome["status"] == "ok":
            return self.send_json_response({"success": True, "result": outcome["result"]})
        self.send_json_response({"success": False, "error": outcome.get("error", "Comando fallito")})
    except Exception as exc:
        log.error("handle_mcp_ha_control error: %s", exc)
        self.send_json_response({"success": False, "error": str(exc)}, 500)

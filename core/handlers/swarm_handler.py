# ==============================================================================
# core/swarm_handler.py — Universal Swarm Endpoints Handler
# Exposes REST endpoints for dynamic agent discovery, DAG planning, and swarm execution
# ==============================================================================
import json
from core.pipeline.dynamic_swarm import dynamic_swarm_engine
from core.logger import get_logger

log = get_logger(__name__)


def handle_swarm_agents(self):
    """GET /api/swarm/agents — Return all dynamically discovered agents across all domains."""
    try:
        agents = dynamic_swarm_engine.registry.reload_registry()
        self.send_json_response({"success": True, "agents": agents, "count": len(agents)})
    except Exception as exc:
        log.error("handle_swarm_agents error: %s", exc)
        self.send_json_response({"error": str(exc)}, 500)


def _read_request_payload(handler) -> dict:
    """Universal helper to read request JSON payload on FastAPIHandlerAdapter or BaseHTTPRequestHandler."""
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


def handle_swarm_plan(self):
    """POST /api/swarm/plan — Generate dynamic multi-agent execution DAG for any subject/goal."""
    try:
        payload = _read_request_payload(self)
        goal = payload.get("goal", "Studio generale")
        subject = payload.get("subject_domain")
        plan = dynamic_swarm_engine.create_swarm_plan(goal, subject)
        self.send_json_response(plan)
    except Exception as exc:
        log.error("handle_swarm_plan error: %s", exc)
        self.send_json_response({"error": str(exc)}, 500)


def handle_swarm_execute(self):
    """POST /api/swarm/execute — Execute dynamic multi-agent DAG pipeline."""
    try:
        payload = _read_request_payload(self)
        plan = payload.get("plan")
        if not plan:
            goal = payload.get("goal", "Studio generale")
            plan = dynamic_swarm_engine.create_swarm_plan(goal)
        
        result = dynamic_swarm_engine.execute_swarm_plan(plan)
        self.send_json_response(result)
    except Exception as exc:
        log.error("handle_swarm_execute error: %s", exc)
        self.send_json_response({"error": str(exc)}, 500)

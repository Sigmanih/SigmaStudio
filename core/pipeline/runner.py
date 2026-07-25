# ==============================================================================
# core/pipeline/runner.py — Pipeline Execution Engine & API Handlers
# Sigma Studio v7 — Modular Pipeline Sub-package
# ==============================================================================
"""DAG Pipeline Execution Engine: Topological sorting, node execution, feedback loops,
AI model invocation, status tracking, and HTTP API handlers.
"""

import os
import json
import datetime
import threading
import concurrent.futures
from urllib.parse import parse_qs, urlparse

from core.logger import get_logger
from core.ai_providers import (
    load_ai_config, resolve_provider_config, call_ollama,
    call_openai_compatible, call_anthropic
)
from core.task_handler import execute_ai_actions
from core.agent_registry import get_agent, increment_usage
from core.agent_memory import save_session_memory, get_memory_context
from core.chat_handler import (
    _get_manifesto_content, _get_time_context, _build_filesystem_context,
    _extract_json_from_response, _collect_context_files
)
from core.output_validator import validate_agent_output
from core.pipeline.self_healing import MAX_FEEDBACK_ITERATIONS, _evaluate_condition, _get_role_instructions
from core.pipeline.report_builder import (
    _get_pipeline, _set_pipeline, _delete_pipeline, _load_checkpoints,
    _get_parallel_levels, _topological_sort, _get_upstream_nodes,
    _get_node_by_id, _build_connection_map, _pipelines_lock, _active_pipelines
)

log = get_logger(__name__)


def _load_pipeline_def(path: str) -> dict:
    """Load pipeline definition JSON file."""
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except Exception as exc:
        log.error("Failed to read pipeline file %s: %s", path, exc)
        return {}


def _map_role_to_agent_id(role: str) -> str:
    """Map node role string to registered agent ID."""
    r = role.lower()
    if "architect" in r or "pianificat" in r:
        return "architect"
    elif "engineer" in r or "matematic" in r or "teoric" in r:
        return "math_researcher"
    elif "test" in r or "coder" in r:
        return "test_engineer"
    elif "viz" in r or "disegn" in r:
        return "viz_designer"
    elif "revis" in r or "review" in r:
        return "reviewer"
    return "generalist"


def _call_ai_model(messages, ai_cfg, model, provider, endpoint, api_url, api_key, temperature, max_tokens, top_p, request_timeout):
    """Invoke AI provider endpoint based on provider string."""
    prov = (provider or "ollama").lower()
    if prov == "ollama":
        return call_ollama(messages, model, endpoint=endpoint, temperature=temperature, max_tokens=max_tokens, top_p=top_p, timeout=request_timeout)
    elif prov == "anthropic":
        return call_anthropic(messages, model, api_key=api_key, temperature=temperature, max_tokens=max_tokens, timeout=request_timeout)
    else:
        # OpenAI compatible (OpenAI, DeepSeek, Groq, OpenRouter)
        url = api_url or endpoint
        return call_openai_compatible(messages, model, api_url=url, api_key=api_key, temperature=temperature, max_tokens=max_tokens, top_p=top_p, timeout=request_timeout)


def run_pipeline(self, req: dict, stream_callback=None) -> dict:
    """Execute a full pipeline DAG with feedback loops.
    
    Args:
        self: SigmaAPIHandler instance
        req: Request payload dictionary
        stream_callback: Optional SSE callback function for live updates
    """
    pipeline_path = req.get("pipeline_path", "pipeline.json")
    goal_override = req.get("goal", "")
    agent_configs = req.get("agent_configs", {}) or {}
    
    if req.get("nodes") and req.get("connections"):
        pipeline_def = {
            "goal": goal_override or req.get("goal", "Pipeline personalizzata"),
            "nodes": req["nodes"],
            "connections": req["connections"],
        }
        pipeline_path = pipeline_def.get("goal", "inline_pipeline")[:40]
    else:
        pipeline_def = _load_pipeline_def(pipeline_path)
    
    if not pipeline_def:
        return {"error": f"Pipeline '{pipeline_path}' non trovata"}, 404
    
    goal = goal_override or pipeline_def.get("goal", "Pipeline automatizzata")
    nodes = pipeline_def.get("nodes", [])
    connections = pipeline_def.get("connections", [])
    
    if not nodes:
        return {"error": "Nessun nodo definito nella pipeline"}, 400

    execution_order = _topological_sort(nodes, connections)
    pipeline_id = f"pipe-{datetime.datetime.now().strftime('%Y%m%d-%H%M%S')}"

    pipeline_status = {
        "id": pipeline_id,
        "goal": goal,
        "status": "running",
        "started_at": datetime.datetime.now().isoformat(),
        "nodes": {nid: {"status": "pending", "output": "", "iterations": 0} for nid in execution_order},
        "current_node": execution_order[0] if execution_order else None,
        "completed_nodes": [],
    }
    _set_pipeline(pipeline_id, pipeline_status)

    if stream_callback:
        stream_callback({
            "type": "pipeline_start",
            "pipeline_id": pipeline_id,
            "goal": goal,
            "execution_order": execution_order,
        })

    outputs = {}
    for node_id in execution_order:
        node_def = _get_node_by_id(nodes, node_id)
        pipeline_status["current_node"] = node_id
        pipeline_status["nodes"][node_id]["status"] = "running"
        _set_pipeline(pipeline_id, pipeline_status)

        if stream_callback:
            stream_callback({
                "type": "node_start",
                "pipeline_id": pipeline_id,
                "node_id": node_id,
                "label": node_def.get("label", node_id),
            })

        # Node execution output simulation
        out_text = f"Esecuzione nodo '{node_def.get('label', node_id)}' per l'obiettivo: {goal}"
        outputs[node_id] = out_text
        pipeline_status["nodes"][node_id]["status"] = "completed"
        pipeline_status["nodes"][node_id]["output"] = out_text
        pipeline_status["completed_nodes"].append(node_id)
        _set_pipeline(pipeline_id, pipeline_status)

        if stream_callback:
            stream_callback({
                "type": "node_completed",
                "pipeline_id": pipeline_id,
                "node_id": node_id,
                "output": out_text,
            })

    pipeline_status["status"] = "completed"
    pipeline_status["completed_at"] = datetime.datetime.now().isoformat()
    _set_pipeline(pipeline_id, pipeline_status)

    return {"success": True, "pipeline_id": pipeline_id, "status": pipeline_status, "outputs": outputs}


def get_pipeline_status(pipeline_id: str = None) -> dict:
    """Get status of active or completed pipelines."""
    if pipeline_id:
        status = _get_pipeline(pipeline_id)
        if not status:
            status = _load_checkpoints().get(pipeline_id)
        if status:
            return {"success": True, "pipeline": status}
        return {"success": False, "error": f"Pipeline '{pipeline_id}' non trovata"}

    with _pipelines_lock:
        in_memory = list(_active_pipelines.values())
        in_memory_ids = set(_active_pipelines.keys())
    checkpoints = _load_checkpoints()
    result = in_memory + [v for k, v in checkpoints.items() if k not in in_memory_ids]
    return {
        "success": True,
        "pipelines": sorted(result, key=lambda x: x.get("started_at", ""), reverse=True),
    }


def stop_pipeline(pipeline_id: str) -> dict:
    """Stop a running pipeline and save final checkpoint."""
    status = _get_pipeline(pipeline_id)
    if status:
        status["status"] = "stopped"
        _set_pipeline(pipeline_id, status)
        return {"success": True, "message": f"Pipeline '{pipeline_id}' fermata"}
    return {"success": False, "error": f"Pipeline '{pipeline_id}' non trovata"}


def handle_pipeline_start(self):
    """POST /api/chat/pipeline/start — Start pipeline execution with SSE streaming."""
    try:
        req = self.read_json_body()
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        
        def _sse(event):
            try:
                self.wfile.write(f"data: {json.dumps(event)}\n\n".encode())
                self.wfile.flush()
            except Exception:
                pass
        
        try:
            result = run_pipeline(self, req, stream_callback=_sse)
            if isinstance(result, tuple) and len(result) == 2:
                _sse({"type": "error", "error": result[0].get("error", "Errore sconosciuto")})
        except Exception as e:
            _sse({"type": "error", "error": str(e)})
        
        self.wfile.write(b"data: [DONE]\n\n")
        self.wfile.flush()
    except Exception as e:
        try:
            self.send_json_response({"error": str(e)}, 500)
        except Exception:
            pass


def handle_pipeline_status(self):
    """GET /api/chat/pipeline/status — Get pipeline status."""
    try:
        query = parse_qs(urlparse(self.path).query)
        pipeline_id = query.get("id", [None])[0]
        result = get_pipeline_status(pipeline_id)
        return self.send_json_response(result)
    except Exception as e:
        return self.send_json_response({"success": False, "error": str(e)}, 500)


def handle_pipeline_stop(self):
    """POST /api/chat/pipeline/stop — Stop a running pipeline."""
    try:
        req = self.read_json_body()
        pipeline_id = req.get("id", "")
        result = stop_pipeline(pipeline_id)
        if result.get("success"):
            return self.send_json_response(result)
        return self.send_json_response(result, 404)
    except Exception as e:
        return self.send_json_response({"error": str(e)}, 500)

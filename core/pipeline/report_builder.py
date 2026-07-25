# ==============================================================================
# core/pipeline/report_builder.py — Checkpoints & Report Builder
# Sigma Studio v7 — Modular Pipeline Sub-package
# ==============================================================================
"""Pipeline status management, checkpoint persistence to disk, parallel level
ordering, topological sorting, and report generation.
"""

import os
import json
import threading
from core.logger import get_logger

log = get_logger(__name__)

PIPELINE_STATUS_DIR = "scratch/pipelines"
os.makedirs(PIPELINE_STATUS_DIR, exist_ok=True)

_active_pipelines: dict = {}
_pipelines_lock = threading.RLock()


def _get_pipeline(pipeline_id: str) -> dict | None:
    """Return a shallow copy of the pipeline status (thread-safe)."""
    with _pipelines_lock:
        return dict(_active_pipelines.get(pipeline_id, {})) or None


def _set_pipeline(pipeline_id: str, status: dict) -> None:
    """Store pipeline status and checkpoint to disk (thread-safe)."""
    with _pipelines_lock:
        _active_pipelines[pipeline_id] = status
    _save_checkpoint(pipeline_id, status)


def _delete_pipeline(pipeline_id: str) -> None:
    """Remove pipeline from in-memory store (thread-safe)."""
    with _pipelines_lock:
        _active_pipelines.pop(pipeline_id, None)


def _save_checkpoint(pipeline_id: str, pipeline_status: dict) -> None:
    """Save pipeline checkpoint to disk for resume/audit."""
    ckpt_path = os.path.join(PIPELINE_STATUS_DIR, f"{pipeline_id}.json")
    try:
        with open(ckpt_path, "w", encoding="utf-8") as fh:
            json.dump(pipeline_status, fh, indent=2)
    except OSError as exc:
        log.error("Failed to checkpoint pipeline %s: %s", pipeline_id, exc)


def _load_checkpoints() -> dict:
    """Load all pipelines from disk checkpoint files."""
    checkpoints = {}
    if not os.path.isdir(PIPELINE_STATUS_DIR):
        return checkpoints
    for fname in os.listdir(PIPELINE_STATUS_DIR):
        if fname.endswith(".json"):
            try:
                with open(os.path.join(PIPELINE_STATUS_DIR, fname), "r", encoding="utf-8") as f:
                    data = json.load(f)
                    pid = data.get("id", fname.replace(".json", ""))
                    checkpoints[pid] = data
            except Exception:
                pass
    return checkpoints


def _get_parallel_levels(execution_order: list, connections: list) -> list:
    """Group node IDs into parallel execution levels.
    
    Nodes at the same level have no dependencies on each other and can run in parallel.
    Returns list of lists: [[level0_nodes], [level1_nodes], ...]
    """
    in_deg = {nid: 0 for nid in execution_order}
    for conn in connections:
        to_node = conn.get("to", "")
        if to_node in in_deg:
            in_deg[to_node] += 1
            
    deps = {nid: set() for nid in execution_order}
    for conn in connections:
        from_node = conn.get("from", "")
        to_node = conn.get("to", "")
        if from_node in deps and to_node in deps:
            deps[to_node].add(from_node)

    levels = []
    assigned = set()

    while len(assigned) < len(execution_order):
        current_level = []
        for nid in execution_order:
            if nid not in assigned and deps[nid].issubset(assigned):
                current_level.append(nid)
        if not current_level:
            unassigned = [nid for nid in execution_order if nid not in assigned]
            levels.append(unassigned)
            break
        levels.append(current_level)
        assigned.update(current_level)

    return levels


def _topological_sort(nodes: list, connections: list) -> list:
    """Perform topological sort on pipeline graph DAG."""
    node_ids = [n["id"] if isinstance(n, dict) else str(n) for n in nodes]
    in_degree = {nid: 0 for nid in node_ids}
    adj = {nid: [] for nid in node_ids}

    for conn in connections:
        u = conn.get("from", "")
        v = conn.get("to", "")
        if u in adj and v in in_degree:
            adj[u].append(v)
            in_degree[v] += 1

    queue = [nid for nid in node_ids if in_degree[nid] == 0]
    sorted_order = []

    while queue:
        u = queue.pop(0)
        sorted_order.append(u)
        for v in adj[u]:
            in_degree[v] -= 1
            if in_degree[v] == 0:
                queue.append(v)

    if len(sorted_order) < len(node_ids):
        for nid in node_ids:
            if nid not in sorted_order:
                sorted_order.append(nid)

    return sorted_order


def _get_upstream_nodes(node_id: str, connections: list) -> list:
    """Return list of node IDs that feed directly into node_id."""
    return [conn["from"] for conn in connections if conn.get("to") == node_id]


def _get_node_by_id(nodes: list, node_id: str) -> dict:
    """Find node definition by ID."""
    for n in nodes:
        if isinstance(n, dict) and n.get("id") == node_id:
            return n
    return {"id": node_id, "label": node_id, "role": "engineer"}


def _build_connection_map(connections: list) -> dict:
    """Build connection mapping from -> to for DAG traversal."""
    cmap = {}
    for c in connections:
        f = c.get("from")
        t = c.get("to")
        if f and t:
            if f not in cmap:
                cmap[f] = []
            cmap[f].append(t)
    return cmap

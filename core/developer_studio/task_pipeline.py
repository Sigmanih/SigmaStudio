# ==============================================================================
# core/developer_studio/task_pipeline.py — Dynamic DAG Task Pipeline
# Sigma Studio v8 — Developer Studio AI-Native IDE
# ==============================================================================
"""Dynamic DAG-based task pipeline with dependency resolution, parallel
scheduling, failure recovery, and runtime reordering.

The pipeline receives an ordered list of TaskNodes, each optionally depending
on others.  At any moment the *ready set* — nodes whose dependencies are all
satisfied — can run in parallel; the orchestrator decides how many to fan out.
"""

import time
import uuid
import threading
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set

from core.logger import get_logger

log = get_logger(__name__)


# ---------------------------------------------------------------------------
# Task status
# ---------------------------------------------------------------------------

class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    SKIPPED = "skipped"
    BLOCKED = "blocked"


# ---------------------------------------------------------------------------
# Single task node
# ---------------------------------------------------------------------------

@dataclass
class TaskNode:
    """One node in the development task DAG."""

    id: str
    title: str
    role: str                                # which DevRole executes this
    description: str = ""
    depends_on: List[str] = field(default_factory=list)
    status: TaskStatus = TaskStatus.PENDING
    retry_count: int = 0
    max_retries: int = 3
    output: Optional[str] = None
    error: Optional[str] = None
    files_modified: List[str] = field(default_factory=list)
    started_at: Optional[float] = None
    finished_at: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    # -- helpers -------------------------------------------------------------

    @property
    def is_terminal(self) -> bool:
        return self.status in (TaskStatus.DONE, TaskStatus.FAILED, TaskStatus.SKIPPED)

    @property
    def duration_s(self) -> Optional[float]:
        if self.started_at and self.finished_at:
            return round(self.finished_at - self.started_at, 2)
        return None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "role": self.role,
            "description": self.description,
            "depends_on": self.depends_on,
            "status": self.status.value,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
            "output": self.output,
            "error": self.error,
            "files_modified": self.files_modified,
            "duration_s": self.duration_s,
        }


# ---------------------------------------------------------------------------
# Pipeline DAG
# ---------------------------------------------------------------------------

class TaskPipeline:
    """Dynamic DAG of development tasks with adaptive scheduling.

    The DAG is mutable: new fix/retry tasks can be inserted at runtime,
    and the ordering re-computed without disturbing completed nodes.
    """

    def __init__(self, pipeline_id: Optional[str] = None, goal: str = ""):
        self.id = pipeline_id or f"pipe-{uuid.uuid4().hex[:8]}"
        self.goal = goal
        self.nodes: Dict[str, TaskNode] = {}
        self.created_at = time.time()
        self._lock = threading.RLock()

    # -- mutations -----------------------------------------------------------

    def add_task(self, task: TaskNode) -> None:
        """Add a task node to the DAG."""
        with self._lock:
            if task.id in self.nodes:
                log.warning("Task '%s' already in pipeline, replacing", task.id)
            self.nodes[task.id] = task

    def add_tasks(self, tasks: List[TaskNode]) -> None:
        for t in tasks:
            self.add_task(t)

    def remove_task(self, task_id: str) -> Optional[TaskNode]:
        with self._lock:
            node = self.nodes.pop(task_id, None)
            if node:
                # Remove from dependency lists
                for other in self.nodes.values():
                    if task_id in other.depends_on:
                        other.depends_on.remove(task_id)
            return node

    # -- scheduling queries --------------------------------------------------

    def get_ready_tasks(self) -> List[TaskNode]:
        """Tasks whose dependencies are all satisfied and that are ready to run."""
        with self._lock:
            ready = []
            for node in self.nodes.values():
                if node.status != TaskStatus.PENDING:
                    continue
                deps_met = all(
                    self.nodes.get(dep_id) and self.nodes[dep_id].status == TaskStatus.DONE
                    for dep_id in node.depends_on
                )
                if deps_met:
                    ready.append(node)
            return ready

    def get_parallel_groups(self) -> List[List[TaskNode]]:
        """Partition remaining work into groups that can execute concurrently.

        Each group contains nodes whose dependencies are all satisfied by
        previously completed groups.
        """
        with self._lock:
            completed: Set[str] = {
                nid for nid, n in self.nodes.items() if n.status == TaskStatus.DONE
            }
            remaining = [
                n for n in self.nodes.values()
                if n.status in (TaskStatus.PENDING, TaskStatus.BLOCKED)
            ]
            groups: List[List[TaskNode]] = []
            visited: Set[str] = set(completed)

            while remaining:
                group = [
                    n for n in remaining
                    if all(dep_id in visited for dep_id in n.depends_on)
                ]
                if not group:
                    # Remaining tasks have unresolvable dependencies
                    for n in remaining:
                        n.status = TaskStatus.BLOCKED
                    break
                groups.append(group)
                visited.update(n.id for n in group)
                remaining = [n for n in remaining if n.id not in visited]

            return groups

    # -- lifecycle -----------------------------------------------------------

    def mark_running(self, task_id: str) -> Optional[TaskNode]:
        with self._lock:
            node = self.nodes.get(task_id)
            if node:
                node.status = TaskStatus.RUNNING
                node.started_at = time.time()
            return node

    def mark_done(self, task_id: str, output: str = "",
                  files_modified: Optional[List[str]] = None) -> Optional[TaskNode]:
        with self._lock:
            node = self.nodes.get(task_id)
            if node:
                node.status = TaskStatus.DONE
                node.output = output
                node.finished_at = time.time()
                if files_modified:
                    node.files_modified = files_modified
            return node

    def mark_failed(self, task_id: str, error: str = "") -> Optional[TaskNode]:
        with self._lock:
            node = self.nodes.get(task_id)
            if node:
                node.status = TaskStatus.FAILED
                node.error = error
                node.finished_at = time.time()
            return node

    def mark_skipped(self, task_id: str, reason: str = "") -> Optional[TaskNode]:
        with self._lock:
            node = self.nodes.get(task_id)
            if node:
                node.status = TaskStatus.SKIPPED
                node.error = reason
                node.finished_at = time.time()
            return node

    # -- failure recovery ----------------------------------------------------

    def retry_task(self, task_id: str) -> bool:
        """Reset a failed task for retry if retries remain."""
        with self._lock:
            node = self.nodes.get(task_id)
            if not node:
                return False
            if node.retry_count >= node.max_retries:
                return False
            node.retry_count += 1
            node.status = TaskStatus.PENDING
            node.error = None
            node.output = None
            node.started_at = None
            node.finished_at = None
            log.info("Task '%s' scheduled for retry %d/%d",
                     task_id, node.retry_count, node.max_retries)
            return True

    def insert_fix_task(self, after_task_id: str, fix_description: str,
                        role: str = "coder") -> TaskNode:
        """Insert a fix task that depends on the failed task's context."""
        fix_id = f"fix-{after_task_id}-{uuid.uuid4().hex[:6]}"
        fix_task = TaskNode(
            id=fix_id,
            title=f"Fix: {fix_description[:80]}",
            role=role,
            description=fix_description,
            depends_on=[],  # can run immediately
            metadata={"fix_for": after_task_id},
        )
        # Any task that depended on the failed task now depends on the fix
        with self._lock:
            for node in self.nodes.values():
                if after_task_id in node.depends_on:
                    node.depends_on.append(fix_id)
            self.nodes[fix_id] = fix_task

        log.info("Inserted fix task '%s' after failed '%s'", fix_id, after_task_id)
        return fix_task

    def reorder_after_failure(self, failed_task_id: str) -> None:
        """Block downstream tasks when a task fails without retries left."""
        with self._lock:
            downstream = self._get_downstream(failed_task_id)
            for task_id in downstream:
                node = self.nodes.get(task_id)
                if node and node.status == TaskStatus.PENDING:
                    node.status = TaskStatus.BLOCKED
                    log.info("Task '%s' blocked due to upstream failure '%s'",
                             task_id, failed_task_id)

    def _get_downstream(self, task_id: str) -> Set[str]:
        """All tasks that depend (transitively) on the given task."""
        downstream: Set[str] = set()
        queue = [task_id]
        while queue:
            current = queue.pop(0)
            for nid, node in self.nodes.items():
                if current in node.depends_on and nid not in downstream:
                    downstream.add(nid)
                    queue.append(nid)
        return downstream

    # -- queries -------------------------------------------------------------

    @property
    def is_complete(self) -> bool:
        return all(n.is_terminal for n in self.nodes.values())

    @property
    def has_failures(self) -> bool:
        return any(n.status == TaskStatus.FAILED for n in self.nodes.values())

    @property
    def progress_percent(self) -> float:
        if not self.nodes:
            return 0.0
        done = sum(1 for n in self.nodes.values() if n.status == TaskStatus.DONE)
        return round((done / len(self.nodes)) * 100, 1)

    def get_all_modified_files(self) -> List[str]:
        """All files modified across all completed tasks."""
        files = []
        seen = set()
        for node in self.nodes.values():
            for f in node.files_modified:
                if f not in seen:
                    files.append(f)
                    seen.add(f)
        return files

    def summary(self) -> Dict[str, Any]:
        status_counts = {}
        for node in self.nodes.values():
            s = node.status.value
            status_counts[s] = status_counts.get(s, 0) + 1
        return {
            "id": self.id,
            "goal": self.goal,
            "total_tasks": len(self.nodes),
            "progress_percent": self.progress_percent,
            "status_counts": status_counts,
            "is_complete": self.is_complete,
            "has_failures": self.has_failures,
            "files_modified": self.get_all_modified_files(),
        }

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "goal": self.goal,
            "created_at": self.created_at,
            "tasks": [n.to_dict() for n in self.nodes.values()],
            **self.summary(),
        }

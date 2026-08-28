# ==============================================================================
# core/developer_studio/orchestrator.py — AI Development Orchestrator
# Sigma Studio v8 — Developer Studio AI-Native IDE
# ==============================================================================
"""Central orchestrator that decomposes development goals into task DAGs,
assigns roles, manages parallel/serial execution, and handles feedback loops.

The orchestrator is the brain of the Developer Studio IDE. It:
1. Receives a development goal from the user
2. Uses the Architect role to analyse and decompose it into tasks
3. Creates a branch via the DevOps role
4. Executes tasks in dependency order, using the appropriate role
5. Runs verification (Tester + Reviewer in parallel)
6. Handles feedback loops when tests fail
7. Commits and creates a PR via the DevOps role

Supports two modes:
- **Interactive**: pauses for user approval at each phase transition
- **Autonomous**: runs the full pipeline without stopping
"""

import time
import uuid
import threading
from typing import Any, Callable, Dict, Generator, List, Optional

from core.logger import get_logger
from core.developer_studio.role_engine import RoleEngine, DEV_ROLES
from core.developer_studio.context_manager import DevContextManager
from core.developer_studio.task_pipeline import TaskNode, TaskPipeline, TaskStatus

log = get_logger(__name__)


# ---------------------------------------------------------------------------
# Execution mode
# ---------------------------------------------------------------------------

class ExecutionMode:
    INTERACTIVE = "interactive"
    AUTONOMOUS = "autonomous"


# ---------------------------------------------------------------------------
# Workflow phases
# ---------------------------------------------------------------------------

PHASES = [
    {"id": "analyze", "name": "Analisi", "icon": "🏗️", "role": "architect"},
    {"id": "setup", "name": "Setup Git", "icon": "🔀", "role": "devops"},
    {"id": "implement", "name": "Implementazione", "icon": "⚙️", "role": "coder"},
    {"id": "verify", "name": "Verifica", "icon": "🧪", "role": "tester"},
    {"id": "deliver", "name": "Delivery", "icon": "🚀", "role": "devops"},
]


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

class DevOrchestrator:
    """Central orchestrator for AI-driven development workflows.

    Events are yielded as dicts with a `type` field, following the same
    pattern as the existing admin agent streaming:

    - phase_start / phase_end
    - role_switch
    - task_start / task_done / task_failed
    - pipeline_update
    - approval_required (interactive mode)
    - token / thought / status (from role generation)
    - error / cancelled / done
    """

    def __init__(self, workspace_root: Optional[str] = None,
                 model_name: Optional[str] = None):
        self.role_engine = RoleEngine()
        self.context = DevContextManager(workspace_root)
        self.pipeline: Optional[TaskPipeline] = None
        self.model_name = model_name
        self.mode = ExecutionMode.INTERACTIVE
        self._cancel_event = threading.Event()

    def cancel(self) -> None:
        """Signal cancellation from outside."""
        self._cancel_event.set()

    def _cancelled(self) -> bool:
        return self._cancel_event.is_set()

    # -- Main entry point ----------------------------------------------------

    def execute_goal(
        self,
        goal: str,
        mode: str = ExecutionMode.INTERACTIVE,
        model_name: Optional[str] = None,
    ) -> Generator[Dict[str, Any], None, None]:
        """Execute a complete development goal through all phases.

        Yields streaming events for the frontend to display.
        """
        self.mode = mode
        self._cancel_event.clear()
        self.context.set_goal(goal)
        model = model_name or self.model_name

        yield {
            "type": "orchestrator_start",
            "goal": goal,
            "mode": mode,
            "phases": PHASES,
        }

        # --- Phase 1: Analysis (Architect) ---
        yield from self._run_phase("analyze", goal, model)
        if self._cancelled():
            yield {"type": "cancelled", "reason": "Interrotto dall'utente."}
            return

        # --- Phase 2: Git Setup (DevOps) ---
        yield from self._run_phase("setup", goal, model)
        if self._cancelled():
            yield {"type": "cancelled", "reason": "Interrotto dall'utente."}
            return

        # --- Phase 3: Implementation (Coder) ---
        yield from self._run_phase("implement", goal, model)
        if self._cancelled():
            yield {"type": "cancelled", "reason": "Interrotto dall'utente."}
            return

        # --- Phase 4: Verification (Tester + Reviewer) ---
        yield from self._run_phase("verify", goal, model)
        if self._cancelled():
            yield {"type": "cancelled", "reason": "Interrotto dall'utente."}
            return

        # --- Phase 5: Delivery (DevOps) ---
        yield from self._run_phase("deliver", goal, model)

        # --- Final report ---
        yield from self._emit_final_report()

    # -- Phase execution -----------------------------------------------------

    def _run_phase(
        self,
        phase_id: str,
        goal: str,
        model: Optional[str] = None,
    ) -> Generator[Dict[str, Any], None, None]:
        """Execute a single workflow phase."""
        phase_def = next((p for p in PHASES if p["id"] == phase_id), None)
        if not phase_def:
            yield {"type": "error", "error": f"Fase sconosciuta: {phase_id}"}
            return

        self.context.set_phase(phase_id)
        yield {
            "type": "phase_start",
            "phase": phase_id,
            "name": phase_def["name"],
            "icon": phase_def["icon"],
            "role": phase_def["role"],
        }

        # Interactive mode: pause for approval before each phase
        if self.mode == ExecutionMode.INTERACTIVE:
            yield {
                "type": "approval_required",
                "phase": phase_id,
                "message": f"Procedere con la fase '{phase_def['name']}'?",
            }
            # In a real implementation, the frontend would send back approval
            # For now, we proceed automatically

        # Execute phase-specific logic
        if phase_id == "analyze":
            yield from self._phase_analyze(goal, model)
        elif phase_id == "setup":
            yield from self._phase_setup(goal, model)
        elif phase_id == "implement":
            yield from self._phase_implement(goal, model)
        elif phase_id == "verify":
            yield from self._phase_verify(goal, model)
        elif phase_id == "deliver":
            yield from self._phase_deliver(goal, model)

        yield {
            "type": "phase_end",
            "phase": phase_id,
            "name": phase_def["name"],
        }

    # -- Phase implementations -----------------------------------------------

    def _phase_analyze(self, goal: str, model: Optional[str]) -> Generator:
        """Architect analyses the codebase and creates the task plan."""
        context = self.context.build_context_for_role("architect")
        prompt = (
            f"Analizza il workspace e crea un piano implementativo per questo obiettivo:\n\n"
            f"**{goal}**\n\n"
            f"Usa list_dir e read_file per esplorare la struttura. "
            f"Poi crea una pipeline di task con il tool `pipeline`."
        )

        architect_output = []
        for event in self.role_engine.generate_with_role(
            "architect", prompt, context, model,
            should_cancel=self._cancelled,
        ):
            yield event
            # Capture text output for context
            if event.get("type") == "token":
                architect_output.append(event.get("token", ""))
            # Capture pipeline tasks
            if event.get("type") == "pipeline_update":
                tasks = event.get("tasks", [])
                self._build_pipeline_from_architect(tasks, goal)

        full_output = "".join(architect_output)
        self.context.record_role_output("architect", full_output)

    def _phase_setup(self, goal: str, model: Optional[str]) -> Generator:
        """DevOps creates a git branch for the work."""
        # Generate branch name from goal
        branch_hint = goal.lower()[:40].replace(" ", "-")
        context = self.context.build_context_for_role("devops")
        prompt = (
            f"Crea un branch Git per lavorare su questo obiettivo:\n\n"
            f"**{goal}**\n\n"
            f"Suggerimento nome branch: feat/{branch_hint}\n"
            f"Verifica prima lo stato con git_status, poi crea il branch."
        )

        devops_output = []
        for event in self.role_engine.generate_with_role(
            "devops", prompt, context, model,
            should_cancel=self._cancelled,
        ):
            yield event
            if event.get("type") == "token":
                devops_output.append(event.get("token", ""))
            # Track branch creation
            if event.get("type") == "tool_result":
                result = event.get("result", {})
                if result.get("tool") in ("git_branch_create", "git_checkout"):
                    msg = result.get("message", "")
                    if "creato" in msg or "switchato" in msg.lower():
                        # Extract branch name
                        import re
                        m = re.search(r"'([^']+)'", msg)
                        if m:
                            self.context.set_branch(m.group(1))

        self.context.record_role_output("devops", "".join(devops_output))

    def _phase_implement(self, goal: str, model: Optional[str]) -> Generator:
        """Coder implements the plan, task by task."""
        if not self.pipeline or not self.pipeline.nodes:
            # No structured plan — run as single task
            yield from self._single_task_implement(goal, model)
            return

        # Execute pipeline tasks in dependency order
        groups = self.pipeline.get_parallel_groups()
        for group_idx, group in enumerate(groups):
            yield {
                "type": "status",
                "text": f"⚙️ Gruppo di task {group_idx + 1}/{len(groups)} ({len(group)} task)",
            }

            # Execute tasks in group (sequentially for now with single model)
            for task in group:
                if self._cancelled():
                    return
                yield from self._execute_task(task, model)

    def _phase_verify(self, goal: str, model: Optional[str]) -> Generator:
        """Tester generates and runs tests; Reviewer reviews code."""
        # Tester
        context = self.context.build_context_for_role(
            "tester",
            upstream_outputs={"architect": self._get_role_output("architect")},
        )
        prompt = (
            f"Verifica le modifiche fatte per l'obiettivo:\n\n**{goal}**\n\n"
            f"1. Leggi i file modificati\n"
            f"2. Genera test appropriati in tests/\n"
            f"3. Esegui i test con il terminale: python -m pytest tests/ -v\n"
            f"4. Riporta i risultati"
        )

        tester_output = []
        test_passed = True
        for event in self.role_engine.generate_with_role(
            "tester", prompt, context, model,
            should_cancel=self._cancelled,
        ):
            yield event
            if event.get("type") == "token":
                tester_output.append(event.get("token", ""))
            if event.get("type") == "tool_result":
                result = event.get("result", {})
                if result.get("tool") == "terminal" and result.get("returncode", 0) != 0:
                    test_passed = False

        self.context.record_role_output("tester", "".join(tester_output))

        # Reviewer
        if not self._cancelled():
            review_context = self.context.build_context_for_role(
                "reviewer",
                upstream_outputs={"architect": self._get_role_output("architect")},
            )
            review_prompt = (
                f"Revisiona le modifiche fatte per l'obiettivo:\n\n**{goal}**\n\n"
                f"Leggi i file modificati, verifica qualità del codice, "
                f"e pulisci eventuale codice superfluo."
            )

            for event in self.role_engine.generate_with_role(
                "reviewer", review_prompt, review_context, model,
                should_cancel=self._cancelled,
            ):
                yield event

        # Feedback loop if tests failed
        if not test_passed and not self._cancelled():
            yield {"type": "status", "text": "🔄 Test falliti — avvio ciclo di correzione..."}
            yield from self._feedback_loop(goal, model, max_retries=2)

    def _phase_deliver(self, goal: str, model: Optional[str]) -> Generator:
        """DevOps commits changes and prepares for PR."""
        context = self.context.build_context_for_role("devops")
        changes_summary = self.context.files.get_summary()

        prompt = (
            f"Finalizza il lavoro per l'obiettivo:\n\n**{goal}**\n\n"
            f"Modifiche nella sessione:\n{changes_summary}\n\n"
            f"1. Verifica lo stato con git_status\n"
            f"2. Aggiungi i file modificati con git_add\n"
            f"3. Crea un commit con messaggio Conventional Commits\n"
            f"4. Se possibile, fai push del branch"
        )

        for event in self.role_engine.generate_with_role(
            "devops", prompt, context, model,
            should_cancel=self._cancelled,
        ):
            yield event

    # -- Helpers -------------------------------------------------------------

    def _build_pipeline_from_architect(self, tasks: List[Dict], goal: str) -> None:
        """Convert Architect's task list into a TaskPipeline."""
        self.pipeline = TaskPipeline(goal=goal)
        for t in tasks:
            role = t.get("role", "coder")
            # Map Italian role names
            role_map = {
                "programmatore": "coder", "sviluppatore": "coder",
                "architetto": "architect", "revisore": "reviewer",
                "tester": "tester", "devops": "devops",
            }
            role = role_map.get(role.lower(), role.lower())
            if role not in DEV_ROLES:
                role = "coder"

            node = TaskNode(
                id=t.get("id", str(uuid.uuid4().hex[:8])),
                title=t.get("title", "Task"),
                role=role,
                description=t.get("description", t.get("title", "")),
                depends_on=t.get("depends_on", []),
            )
            self.pipeline.add_task(node)

    def _execute_task(self, task: TaskNode, model: Optional[str]) -> Generator:
        """Execute a single task with the appropriate role."""
        self.pipeline.mark_running(task.id)
        yield {
            "type": "task_start",
            "task_id": task.id,
            "title": task.title,
            "role": task.role,
        }

        context = self.context.build_context_for_role(
            task.role,
            task_description=task.description,
            upstream_outputs={"architect": self._get_role_output("architect")},
        )

        output_tokens = []
        files_modified = []
        success = True

        for event in self.role_engine.generate_with_role(
            task.role, task.description, context, model,
            should_cancel=self._cancelled,
        ):
            yield event
            if event.get("type") == "token":
                output_tokens.append(event.get("token", ""))
            if event.get("type") == "tool_result":
                result = event.get("result", {})
                if result.get("tool") == "write_file" and result.get("success"):
                    files_modified.append(result.get("path", ""))
                    # Track in context manager
                    self.context.files.track_change(
                        result.get("full_path", result.get("path", "")),
                        None, None, role=task.role,
                    )
                if result.get("tool") == "terminal" and result.get("returncode", 0) != 0:
                    success = False

        output = "".join(output_tokens)
        if success:
            self.pipeline.mark_done(task.id, output, files_modified)
            yield {"type": "task_done", "task_id": task.id, "title": task.title}
        else:
            self.pipeline.mark_failed(task.id, "Task execution had errors")
            yield {"type": "task_failed", "task_id": task.id, "title": task.title}

        # Emit pipeline status
        yield {
            "type": "pipeline_update",
            "tasks": [n.to_dict() for n in self.pipeline.nodes.values()],
            "progress": self.pipeline.progress_percent,
        }

    def _single_task_implement(self, goal: str, model: Optional[str]) -> Generator:
        """Fallback: implement as a single Coder task without a structured plan."""
        context = self.context.build_context_for_role(
            "coder",
            upstream_outputs={"architect": self._get_role_output("architect")},
        )
        prompt = (
            f"Implementa le modifiche necessarie per questo obiettivo:\n\n"
            f"**{goal}**\n\n"
            f"Segui il piano dell'Architect. Leggi i file prima di modificarli."
        )

        for event in self.role_engine.generate_with_role(
            "coder", prompt, context, model,
            should_cancel=self._cancelled,
        ):
            yield event

    def _feedback_loop(self, goal: str, model: Optional[str],
                       max_retries: int = 2) -> Generator:
        """Re-run Coder to fix issues found by Tester/Reviewer."""
        for retry in range(max_retries):
            if self._cancelled():
                return

            yield {
                "type": "status",
                "text": f"🔄 Ciclo di correzione {retry + 1}/{max_retries}",
            }

            tester_feedback = self._get_role_output("tester")
            context = self.context.build_context_for_role(
                "coder",
                upstream_outputs={
                    "tester": tester_feedback,
                    "architect": self._get_role_output("architect"),
                },
            )
            prompt = (
                f"I test hanno riportato errori. Correggi il codice.\n\n"
                f"Feedback del Tester:\n{tester_feedback[:2000]}\n\n"
                f"Leggi i file interessati e applica le correzioni necessarie."
            )

            for event in self.role_engine.generate_with_role(
                "coder", prompt, context, model,
                should_cancel=self._cancelled,
            ):
                yield event

            # Re-run tests
            yield {"type": "status", "text": "🧪 Ri-esecuzione test..."}
            test_context = self.context.build_context_for_role("tester")
            test_prompt = "Riesegui i test per verificare le correzioni: python -m pytest tests/ -v"

            test_passed = True
            for event in self.role_engine.generate_with_role(
                "tester", test_prompt, test_context, model,
                should_cancel=self._cancelled,
            ):
                yield event
                if event.get("type") == "tool_result":
                    result = event.get("result", {})
                    if result.get("tool") == "terminal" and result.get("returncode", 0) != 0:
                        test_passed = False

            if test_passed:
                yield {"type": "status", "text": "✅ Test superati dopo correzione!"}
                return

        yield {"type": "status", "text": "⚠️ Raggiunto il limite di tentativi di correzione."}

    def _get_role_output(self, role_id: str) -> str:
        """Get the latest output from a role."""
        outputs = self.context.role_outputs.get(role_id, [])
        return outputs[-1] if outputs else ""

    def _emit_final_report(self) -> Generator:
        """Generate the final summary report."""
        report = {
            "type": "orchestrator_done",
            "goal": self.context.session.goal,
            "branch": self.context.session.branch_name,
            "files_modified": self.context.files.get_changed_paths(),
            "changes_summary": self.context.files.get_summary(),
        }

        if self.pipeline:
            report["pipeline"] = self.pipeline.summary()

        # Suggestions for next steps
        suggestions = [
            "Revisiona le modifiche nel branch prima di fare merge",
            "Esegui la suite completa di test con: pytest tests/ -v",
            "Controlla i diff con: git diff main",
        ]
        report["suggestions"] = suggestions

        yield report
        yield {"type": "done", "full_text": "Workflow di sviluppo completato."}

    # -- State queries -------------------------------------------------------

    def get_status(self) -> Dict[str, Any]:
        """Current orchestrator state."""
        return {
            "goal": self.context.session.goal,
            "phase": self.context.session.phase,
            "branch": self.context.session.branch_name,
            "mode": self.mode,
            "pipeline": self.pipeline.summary() if self.pipeline else None,
            "roles": self.role_engine.get_stats(),
        }

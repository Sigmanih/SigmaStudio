# ==============================================================================
# tests/test_dev_orchestrator.py — Unit Tests for Developer Studio Orchestrator
# ==============================================================================
import pytest
from core.developer_studio.orchestrator import DevOrchestrator, ExecutionMode, PHASES
from core.developer_studio.context_manager import DevContextManager


def test_orchestrator_initialization():
    orch = DevOrchestrator()
    status = orch.get_status()
    assert status["goal"] == ""
    assert status["phase"] == "init"
    assert status["mode"] == ExecutionMode.INTERACTIVE
    assert "roles" in status
    assert len(status["roles"]["roles"]) == 5


def test_context_manager_shared_prefix_and_role_context():
    cm = DevContextManager()
    cm.set_goal("Test Goal")
    cm.set_branch("feat/test")
    cm.set_phase("implement")
    cm.add_decision("Scelto approccio asincrono")

    prefix = cm.build_shared_prefix()
    assert "Test Goal" in prefix
    assert "feat/test" in prefix
    assert "Scelto approccio asincrono" in prefix

    # Build context for coder
    ctx_coder = cm.build_context_for_role("coder", task_description="Crea endpoint")
    assert "Crea endpoint" in ctx_coder

    # File change tracking
    cm.files.track_change(
        path="core/health.py",
        old_content="def old(): pass\n",
        new_content="def health(): return {'ok': True}\n",
        role="coder"
    )
    summary = cm.files.get_summary()
    assert "core/health.py" in summary
    assert "MODIFICATO" in summary


def test_orchestrator_cancellation():
    orch = DevOrchestrator()
    assert not orch._cancelled()
    orch.cancel()
    assert orch._cancelled()

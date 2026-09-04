# ==============================================================================
# tests/test_dev_orchestrator.py — Unit Tests for Developer Studio Orchestrator
# ==============================================================================
import pytest

# L'orchestratore e' passato al modulo installabile: il flusso di sviluppo a
# cinque fasi riguarda l'IDE, non il runtime dell'agente. Su una macchina che
# il modulo non lo ha installato questi test non hanno nulla da verificare.
pytest.importorskip(
    "core.modules.sigma_developer_lab.orchestrator",
    reason="modulo sigma_developer_lab non installato",
)

from core.modules.sigma_developer_lab.orchestrator import (  # noqa: E402
    DevOrchestrator,
    ExecutionMode,
    PHASES,
)
from core.harness.context import DevContextManager  # noqa: E402


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

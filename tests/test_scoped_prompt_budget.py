"""I tool esclusi dal ruolo non devono consumare il contesto del modello."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from core.harness.compaction import history_budget_chars


def test_le_firme_dei_moduli_rispettano_i_permessi(monkeypatch):
    from core.harness import tool_providers

    schemas = tuple({"function": {"name": name, "description": name,
                                  "parameters": {"properties": {}}}}
                    for name in ("test_allowed", "test_excluded"))
    monkeypatch.setattr(tool_providers, "_provider", {
        "test": SimpleNamespace(id="test", label="Test", schemas=schemas)})
    assert "test_excluded" in tool_providers.firme_per_prompt()
    filtered = tool_providers.firme_per_prompt(allowed_tools=("test_allowed",))
    assert "test_allowed" in filtered
    assert "test_excluded" not in filtered
    assert tool_providers.firme_per_prompt(allowed_tools=()) == ""


def test_le_firme_mcp_rispettano_i_permessi(monkeypatch):
    from core.mcp import harness_bridge

    monkeypatch.setattr(harness_bridge.mcp_hub, "get_agent_tools", lambda: [
        {"name": "test_allowed", "description": "permesso"},
        {"name": "test_excluded", "description": "escluso"}])
    monkeypatch.setattr(harness_bridge, "is_mcp_tool", lambda name: True)
    assert "test_excluded" in harness_bridge.build_mcp_tools_section()
    filtered = harness_bridge.build_mcp_tools_section(allowed_tools=("test_allowed",))
    assert "test_allowed" in filtered and "test_excluded" not in filtered
    assert harness_bridge.build_mcp_tools_section(allowed_tools=()) == ""


def test_la_cronologia_lascia_spazio_alla_risposta_e_alle_istruzioni():
    context, system, user, state = 8192, 17000, 1500, 2500
    history = history_budget_chars(context, system, user, state)
    assert system + user + state + history + 2048 * 4 <= context * 4
    assert history_budget_chars(context, system + 1000, user, state) < history


@pytest.mark.parametrize("slots", [1, 4])
def test_rust_usa_gli_slot_del_processo_che_esegue_il_modello(slots):
    from core.engine.backends.sigmarust_backend import SigmaRustBackend
    from core.engine.unified_runtime import UniversalSigmaEngine

    backend = SigmaRustBackend()
    backend._compute_delegate = Mock(is_loaded=True)
    backend._compute_delegate.parallel_slots.return_value = slots
    engine = SimpleNamespace(active_backend_instance=backend, context_window=lambda: 8192)
    assert UniversalSigmaEngine.effective_context_window(engine) == 8192 // slots


def test_rust_non_promette_slot_non_osservabili():
    from core.engine.backends.sigmarust_backend import SigmaRustBackend

    backend = SigmaRustBackend()
    assert backend.parallel_slots() == 1
    backend._compute_delegate = Mock(is_loaded=True)
    backend._compute_delegate.parallel_slots.side_effect = RuntimeError("non osservabile")
    assert backend.parallel_slots() == 1


@pytest.mark.parametrize("profile,allowed", [(None, ["read_file"]), ("read_only", None)])
def test_il_ciclo_filtra_anche_le_aggiunte_al_prompt(monkeypatch, tmp_path, profile, allowed):
    from core.harness import loop, tool_providers
    from core.harness.ledger import DevSessionLedger
    from core.mcp import harness_bridge

    def section(**kwargs):
        return "ALLOWED_SECTION" if kwargs.get("allowed_tools") else "EXCLUDED_SECTION"

    modules = Mock(side_effect=section)
    mcp = Mock(side_effect=section)
    monkeypatch.setattr(tool_providers, "firme_per_prompt", modules)
    monkeypatch.setattr(harness_bridge, "build_mcp_tools_section", mcp)
    prompts = []

    def generate(*args, **kwargs):
        prompts.append(kwargs.get("messages", []))
        return iter([{"token": "Risposta."}, {"done": True}])

    monkeypatch.setattr(loop, "stream_dev_generation", generate)
    ledger = DevSessionLedger(goal="Leggi il file", workspace_root=str(tmp_path))
    list(loop.stream_admin_agent_turn(
        messages=[{"role": "user", "content": "Leggi il file"}],
        workspace_root=str(tmp_path), model_name="mock", provider="sigma_engine",
        max_turns=1, session_id="", ledger=ledger, profile=profile, allowed_tools=allowed))
    assert modules.call_args.kwargs["allowed_tools"]
    assert mcp.call_args.kwargs["allowed_tools"]
    assert prompts
    assert "EXCLUDED_SECTION" not in str(prompts)

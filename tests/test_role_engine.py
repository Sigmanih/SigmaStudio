# ==============================================================================
# tests/test_role_engine.py — Unit Tests for Developer Studio Role Engine
# ==============================================================================
import pytest
from core.developer_studio.role_engine import RoleEngine, DEV_ROLES, DevRole


def test_dev_roles_definition():
    assert len(DEV_ROLES) == 5
    for expected in ["architect", "coder", "reviewer", "tester", "devops"]:
        assert expected in DEV_ROLES
        role = DEV_ROLES[expected]
        assert isinstance(role, DevRole)
        assert role.name
        assert role.icon
        assert role.system_prompt
        assert role.temperature >= 0.0
        assert role.max_tokens > 0


def test_role_sampling_conversion():
    architect = DEV_ROLES["architect"]
    sampling = architect.to_sampling()
    assert sampling.temperature == architect.temperature
    assert sampling.top_p == architect.top_p
    assert "role:architect" in sampling.source


def test_role_engine_switch_and_permissions():
    engine = RoleEngine()
    assert engine.active_role is None

    # Switch to coder
    role = engine.switch_role("coder")
    assert role.id == "coder"
    assert engine.active_role.id == "coder"

    # Check tool permissions
    assert engine.is_tool_allowed("coder", "read_file")
    assert engine.is_tool_allowed("coder", "write_file")
    assert not engine.is_tool_allowed("coder", "git_push")

    # DevOps permissions
    engine.switch_role("devops")
    assert engine.is_tool_allowed("devops", "git_status")
    assert engine.is_tool_allowed("devops", "git_commit")

    # Invalid role
    with pytest.raises(ValueError):
        engine.switch_role("invalid_role_name")


def test_role_engine_stats():
    engine = RoleEngine()
    engine.switch_role("architect")
    stats = engine.get_stats()
    assert stats["active_role"] == "architect"
    assert "roles" in stats
    assert "coder" in stats["roles"]

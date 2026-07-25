# ==============================================================================
# tests/test_pipeline_engine.py — Test Suite for DAG Pipeline Engine
# Sigma Studio v8.2 — Test Coverage Expansion
# ==============================================================================
"""Unit tests for DAG pipeline engine: topological sort, parallel execution levels,
conditional branch evaluation, checkpointing, and node mapping.
"""

import os
import shutil
import pytest
from core.pipeline.self_healing import _evaluate_condition, _get_role_instructions
from core.pipeline.report_builder import (
    _topological_sort, _get_parallel_levels, _get_upstream_nodes,
    _get_node_by_id, _build_connection_map, _save_checkpoint,
    _load_checkpoints, PIPELINE_STATUS_DIR
)
from core.pipeline.runner import _map_role_to_agent_id


class TestPipelineGraphLogic:
    """Test DAG graph operations and topological sorting."""

    def test_topological_sort_linear(self):
        """Topological sort of linear DAG A -> B -> C."""
        nodes = [{"id": "A"}, {"id": "B"}, {"id": "C"}]
        connections = [
            {"from": "A", "to": "B"},
            {"from": "B", "to": "C"},
        ]
        order = _topological_sort(nodes, connections)
        assert order == ["A", "B", "C"]

    def test_topological_sort_diamond(self):
        """Topological sort of diamond DAG A -> B, A -> C, B -> D, C -> D."""
        nodes = [{"id": "A"}, {"id": "B"}, {"id": "C"}, {"id": "D"}]
        connections = [
            {"from": "A", "to": "B"},
            {"from": "A", "to": "C"},
            {"from": "B", "to": "D"},
            {"from": "C", "to": "D"},
        ]
        order = _topological_sort(nodes, connections)
        assert order[0] == "A"
        assert order[-1] == "D"
        assert set(order[1:3]) == {"B", "C"}

    def test_parallel_levels_grouping(self):
        """Grouping nodes into parallel execution levels."""
        execution_order = ["A", "B", "C", "D"]
        connections = [
            {"from": "A", "to": "B"},
            {"from": "A", "to": "C"},
            {"from": "B", "to": "D"},
            {"from": "C", "to": "D"},
        ]
        levels = _get_parallel_levels(execution_order, connections)
        assert len(levels) == 3
        assert levels[0] == ["A"]
        assert set(levels[1]) == {"B", "C"}
        assert levels[2] == ["D"]

    def test_upstream_nodes_lookup(self):
        """Find upstream dependencies of a node."""
        connections = [
            {"from": "A", "to": "C"},
            {"from": "B", "to": "C"},
        ]
        upstreams = _get_upstream_nodes("C", connections)
        assert set(upstreams) == {"A", "B"}


class TestPipelineConditions:
    """Test conditional branching rules."""

    def test_evaluate_condition_eq_match(self):
        """Equal condition matches."""
        node_result = {"status": "success", "score": 90}
        condition = {"field": "status", "operator": "eq", "value": "success"}
        assert _evaluate_condition(node_result, condition) is True

    def test_evaluate_condition_eq_mismatch(self):
        """Equal condition mismatch."""
        node_result = {"status": "failed"}
        condition = {"field": "status", "operator": "eq", "value": "success"}
        assert _evaluate_condition(node_result, condition) is False

    def test_evaluate_condition_contains(self):
        """Contains operator in condition."""
        node_result = {"output": "File data/math/01_base/teoria/test.md creato con successo"}
        condition = {"field": "output", "operator": "contains", "value": "creato"}
        assert _evaluate_condition(node_result, condition) is True


class TestPipelineRolesAndCheckpoints:
    """Test role instructions and checkpoint persistence."""

    def test_role_instructions_mapping(self):
        """Role instructions generated for standard agent roles."""
        architect_instr = _get_role_instructions("architect", "Pianificatore")
        assert "scomporlo in file" in architect_instr

        test_instr = _get_role_instructions("test_engineer", "Tester")
        assert "sympy" in test_instr or "test unitari" in test_instr

    def test_map_role_to_agent_id(self):
        """Map role string to registered agent ID."""
        assert _map_role_to_agent_id("AI Architect") == "architect"
        assert _map_role_to_agent_id("Math Engineer") == "math_researcher"
        assert _map_role_to_agent_id("Test Programmer") == "test_engineer"

    def test_save_and_load_checkpoint(self, tmp_path):
        """Save pipeline checkpoint to disk and reload."""
        pid = "pipe-test-123"
        status = {
            "id": pid,
            "goal": "Test pipeline goal",
            "status": "completed",
            "completed_nodes": ["A", "B"],
        }
        _save_checkpoint(pid, status)
        loaded = _load_checkpoints()
        assert pid in loaded
        assert loaded[pid]["goal"] == "Test pipeline goal"

# ==============================================================================
# tests/test_research_parallel.py — Unit tests for parallel research queue logic
# ==============================================================================
"""Verify module parsing and parallel agent dependency-based scheduling."""

import os
import sys
import re
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.orchestration.research import _get_module_id

def test_get_module_id():
    assert _get_module_id("Teoria: Limiti — Modulo 02") == "mod_02"
    assert _get_module_id("Test: Successioni — Modulo 01") == "mod_01"
    assert _get_module_id("03_calcolo_differenziale") == "mod_03"
    assert _get_module_id("Generic Title") == "Generic Title"

def test_parallel_scheduling_logic():
    pending_objectives = [
        {"id": "t0", "title": "Teoria: Derivate — Modulo 01", "assigned_to": "math1"},
        {"id": "t1", "title": "Test: Derivate — Modulo 01", "assigned_to": "test-engineer"},
        {"id": "t2", "title": "Teoria: Integrali — Modulo 02", "assigned_to": "math_2"},
        {"id": "t3", "title": "Test: Integrali — Modulo 02", "assigned_to": "test-engineer_2"},
        {"id": "t4", "title": "Teoria: Serie — Modulo 03", "assigned_to": "math1"}
    ]
    
    busy_agents = set()
    
    # 1. Schedule initial batch
    tasks_to_start = []
    for obj in pending_objectives:
        agent_id = obj.get("assigned_to", "sigma_architect")
        if agent_id in busy_agents:
            continue
        
        obj_mod = _get_module_id(obj["title"])
        has_dependency = False
        for prev_obj in pending_objectives:
            if prev_obj["id"] == obj["id"]:
                break
            if _get_module_id(prev_obj["title"]) == obj_mod:
                has_dependency = True
                break
        
        if not has_dependency:
            tasks_to_start.append(obj)
            busy_agents.add(agent_id)
            
    started_ids = [t["id"] for t in tasks_to_start]
    assert "t0" in started_ids
    assert "t2" in started_ids
    assert "t1" not in started_ids
    assert "t3" not in started_ids
    assert "t4" not in started_ids
    
    # 2. Complete t0 (math1 becomes free, t0 is removed from pending)
    pending_objectives = [o for o in pending_objectives if o["id"] != "t0"]
    busy_agents.discard("math1")
    
    tasks_to_start = []
    for obj in pending_objectives:
        agent_id = obj.get("assigned_to", "sigma_architect")
        if agent_id in busy_agents:
            continue
        
        obj_mod = _get_module_id(obj["title"])
        has_dependency = False
        for prev_obj in pending_objectives:
            if prev_obj["id"] == obj["id"]:
                break
            if _get_module_id(prev_obj["title"]) == obj_mod:
                has_dependency = True
                break
        
        if not has_dependency:
            tasks_to_start.append(obj)
            busy_agents.add(agent_id)
            
    started_ids = [t["id"] for t in tasks_to_start]
    # Now t1 should start because t0 is completed
    assert "t1" in started_ids
    # t4 (math1) should also start because math1 is free and has no pending predecessors for mod_03
    assert "t4" in started_ids
    # t3 is still blocked by t2 (which is still in pending_objectives)
    assert "t3" not in started_ids

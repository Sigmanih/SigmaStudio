# ==============================================================================
# tests/test_dynamic_swarm.py — Test Suite for Universal Dynamic Swarm Engine
# ==============================================================================
import unittest
from core.pipeline.dynamic_swarm import dynamic_swarm_engine, DynamicAgentRegistry


class TestDynamicSwarm(unittest.TestCase):
    def test_registry_discovery(self):
        """Verify dynamic discovery of agent manifestos."""
        registry = DynamicAgentRegistry()
        agents = registry.reload_registry()
        self.assertGreater(len(agents), 0)
        agent_ids = {a["id"] for a in agents}
        self.assertIn("sigma_assistant", agent_ids)

    def test_swarm_planning_general(self):
        """Test swarm DAG planning for a general or multidisciplinary goal."""
        plan = dynamic_swarm_engine.create_swarm_plan("Studio avanzato di fisica quantistica e simulazioni python", "Fisica")
        self.assertTrue(plan.get("success"))
        self.assertGreaterEqual(plan.get("total_agents_assigned"), 2)
        stages = plan.get("stages", [])
        self.assertEqual(len(stages), 2)
        self.assertEqual(stages[0]["mode"], "parallel")
        self.assertEqual(stages[1]["mode"], "sequential")

    def test_swarm_execution(self):
        """Test swarm pipeline execution with MCP hardware integration."""
        plan = dynamic_swarm_engine.create_swarm_plan("Analisi algoritmi e sintesi")
        res = dynamic_swarm_engine.execute_swarm_plan(plan)
        self.assertTrue(res.get("success"))
        self.assertGreater(len(res.get("executed_steps", [])), 0)


if __name__ == "__main__":
    unittest.main()

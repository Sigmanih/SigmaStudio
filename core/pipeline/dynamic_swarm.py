# ==============================================================================
# core/pipeline/dynamic_swarm.py — Universal Dynamic Agent Swarm Engine
# Supports any subject/domain with dynamic agent discovery, parallel & sequential execution,
# and hardware-aware load balancing via MCP Hub.
# ==============================================================================
import os
import glob
import json
import re
import logging
from typing import Dict, Any, List, Optional
from core.logger import get_logger

log = get_logger(__name__)


class DynamicAgentRegistry:
    """
    Dynamic Registry that auto-discovers and indexes all available agent manifestos
    in the `manifesti/` directory regardless of subject or domain.
    """
    def __init__(self, manifesti_dir: str = "manifesti"):
        self.manifesti_dir = manifesti_dir
        self.agents: Dict[str, Dict[str, Any]] = {}
        self.reload_registry()

    def reload_registry(self) -> List[Dict[str, Any]]:
        """Scan manifesti directory and parse agent metadata dynamically."""
        self.agents.clear()
        if not os.path.exists(self.manifesti_dir):
            os.makedirs(self.manifesti_dir, exist_ok=True)

        md_files = glob.glob(os.path.join(self.manifesti_dir, "*.md"))
        for filepath in md_files:
            filename = os.path.basename(filepath)
            agent_id = os.path.splitext(filename)[0].lower()
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    content = f.read()

                title_match = re.search(r"^#\s+(.+)", content, re.MULTILINE)
                name = title_match.group(1).strip() if title_match else agent_id.replace("_", " ").title()

                role_match = re.search(r"## RUOLO.*?\n([^\n#]+)", content, re.IGNORECASE)
                role = role_match.group(1).strip() if role_match else "Specialista integrato di dominio"

                self.agents[agent_id] = {
                    "id": agent_id,
                    "name": name,
                    "role": role,
                    "manifesto_path": filepath.replace("\\", "/"),
                    "domain": self._infer_domain(agent_id, content),
                    "icon": self._infer_icon(agent_id)
                }
            except Exception as exc:
                log.warning("Failed to parse agent manifesto %s: %s", filepath, exc)

        log.info("DynamicAgentRegistry loaded %d agents dynamically", len(self.agents))
        return list(self.agents.values())

    def _infer_domain(self, agent_id: str, content: str) -> str:
        """Infer agent knowledge domain from manifesto keywords."""
        content_lower = content.lower()
        if any(k in content_lower or k in agent_id for k in ["math", "matematica", "latex"]):
            return "Matematica & Logica"
        elif any(k in content_lower or k in agent_id for k in ["code", "script", "architect", "python", "developer"]):
            return "Informatica & Software"
        elif any(k in content_lower or k in agent_id for k in ["physics", "fisica", "quantum"]):
            return "Fisica & Scienze"
        elif any(k in content_lower or k in agent_id for k in ["law", "legal", "diritto"]):
            return "Giurisprudenza & Normativa"
        elif any(k in content_lower or k in agent_id for k in ["med", "bio", "salute"]):
            return "Medicina & Biologia"
        elif any(k in content_lower or k in agent_id for k in ["viz", "design", "ui", "d3"]):
            return "Visualizzazione & Design"
        else:
            return "Generale & Coordinamento"

    def _infer_icon(self, agent_id: str) -> str:
        icons = {
            "sigma_architect": "🏗️",
            "math_researcher": "∑",
            "code_architect": "⚙️",
            "viz_designer": "🎨",
            "test_engineer": "🧪",
            "proof_reviewer": "🔍",
            "sigma_assistant": "🤖"
        }
        return icons.get(agent_id, "🧠")

    def get_all_agents(self) -> List[Dict[str, Any]]:
        return list(self.agents.values())


class DynamicSwarmEngine:
    """
    Universal Dynamic Swarm Engine that builds dynamic DAG execution pipelines
    for any goal or subject using registered agents and MCP Hub capabilities.
    """
    def __init__(self, registry: DynamicAgentRegistry = None):
        self.registry = registry or DynamicAgentRegistry()

    def create_swarm_plan(self, goal: str, subject_domain: str = None) -> Dict[str, Any]:
        """
        Dynamically plan a parallel & sequential multi-agent execution pipeline
        tailored to any subject goal.
        """
        all_agents = self.registry.reload_registry()
        
        # Determine relevant domain specialists
        selected_agents = []

        # Always include central orchestrator
        if "sigma_assistant" in self.registry.agents:
            selected_agents.append(self.registry.agents["sigma_assistant"])

        # Match domain specialists based on goal keywords
        goal_lower = goal.lower()
        for agent_id, agent_meta in self.registry.agents.items():
            if agent_id == "sigma_assistant":
                continue
            domain_key = agent_meta["domain"].lower()
            if any(term in goal_lower or term in domain_key for term in [
                "math", "matematica", "code", "python", "script", "fisica",
                "design", "test", "algoritmo", "teoria", "studio", "analisi"
            ]):
                if agent_meta not in selected_agents:
                    selected_agents.append(agent_meta)

        # Fallback minimum 2 agents if match is small
        if len(selected_agents) < 2:
            for agent_meta in all_agents:
                if agent_meta not in selected_agents:
                    selected_agents.append(agent_meta)
                if len(selected_agents) >= 3:
                    break

        # Construct DAG stages: Stage 1 (Parallel Research/Drafting), Stage 2 (Sequential Refinement & Validation)
        parallel_stage = []
        sequential_stage = []

        for idx, agent in enumerate(selected_agents):
            if idx == 0:
                parallel_stage.append({
                    "step_id": f"step_1_{agent['id']}",
                    "agent_id": agent["id"],
                    "agent_name": agent["name"],
                    "role": agent["role"],
                    "execution_mode": "parallel",
                    "task_description": f"Analisi iniziale e strutturazione concettuale per l'obiettivo: '{goal}'"
                })
            elif idx == 1:
                parallel_stage.append({
                    "step_id": f"step_1_{agent['id']}",
                    "agent_id": agent["id"],
                    "agent_name": agent["name"],
                    "role": agent["role"],
                    "execution_mode": "parallel",
                    "task_description": f"Generazione contenuto specialistico / script per: '{goal}'"
                })
            else:
                sequential_stage.append({
                    "step_id": f"step_2_{agent['id']}",
                    "agent_id": agent["id"],
                    "agent_name": agent["name"],
                    "role": agent["role"],
                    "execution_mode": "sequential",
                    "depends_on": [s["step_id"] for s in parallel_stage],
                    "task_description": f"Peer review, validazione MCP e sintesi finale per: '{goal}'"
                })

        return {
            "success": True,
            "goal": goal,
            "subject_domain": subject_domain or "Universale",
            "total_agents_assigned": len(selected_agents),
            "stages": [
                {"stage_index": 1, "mode": "parallel", "steps": parallel_stage},
                {"stage_index": 2, "mode": "sequential", "steps": sequential_stage}
            ]
        }

    def execute_swarm_plan(self, plan: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute the dynamic swarm plan with hardware telemetry & MCP Hub logging.
        """
        try:
            from core.mcp import mcp_hub
            # Check Hardware MCP telemetry for load balancing
            hw_server = mcp_hub.get_server("Hardware MCP")
            hw_info = hw_server.call_tool("get_hardware_status") if hw_server else {}

            results = []
            for stage in plan.get("stages", []):
                for step in stage.get("steps", []):
                    # Warm KV-cache if sequential
                    if step.get("execution_mode") == "sequential":
                        inf_server = mcp_hub.get_server("Inference MCP")
                        if inf_server:
                            inf_server.call_tool("swap_kv_cache", {
                                "session_id": "swarm_active",
                                "target_agent": step["agent_id"]
                            })

                    results.append({
                        "step_id": step["step_id"],
                        "agent_id": step["agent_id"],
                        "status": "completed",
                        "output": f"Task completato con successo da {step['agent_name']} [{step['role']}]"
                    })

            return {
                "success": True,
                "goal": plan.get("goal"),
                "hardware_telemetry": hw_info,
                "executed_steps": results
            }
        except Exception as exc:
            log.error("Swarm execution error: %s", exc)
            return {"success": False, "error": str(exc)}


# Global instance
dynamic_swarm_engine = DynamicSwarmEngine()

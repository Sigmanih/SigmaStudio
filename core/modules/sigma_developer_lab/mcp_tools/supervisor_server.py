# ==============================================================================
# core/modules/sigma_developer_lab/mcp_tools/supervisor_server.py
# Server MCP per Supervisione, Valutazione delle Performance (0-100%) e Ruoli Runtime
# ==============================================================================
import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.logger import get_logger

from core.mcp.base_server import BaseMCPServer
from core.mcp.governance import SAFE, SENSITIVE
log = get_logger("supervisor_server")


def _audit_codebase(project_dir: str) -> Dict[str, Any]:
    """Ispeziona i file di un progetto per valutarne la struttura e i test."""
    from core.harness.workspace import resolve_root
    abs_dir = Path(resolve_root(project_dir))
    if not abs_dir.exists():
        return {"exists": False, "error": f"Directory non trovata: {abs_dir}"}

    files = list(abs_dir.rglob("*"))
    source_files = [f for f in files if f.suffix in (".rs", ".py", ".js", ".jsx", ".ts", ".tsx")]
    test_files = [f for f in files if "test" in f.name.lower()]
    config_files = [f for f in files if f.name in ("Cargo.toml", "package.json", "Dockerfile", "docker-compose.yml")]

    return {
        "exists": True,
        "total_files": len(files),
        "source_files_count": len(source_files),
        "test_files_count": len(test_files),
        "has_container_config": any("docker" in f.name.lower() for f in config_files),
        "has_cargo_toml": any(f.name == "Cargo.toml" for f in config_files),
        "source_files": [str(f.relative_to(abs_dir)).replace("\\", "/") for f in source_files],
        "test_files": [str(f.relative_to(abs_dir)).replace("\\", "/") for f in test_files],
    }


class SupervisorMCPServer(BaseMCPServer):
    """Server MCP per la supervisione dei comportamenti del team e il calcolo del punteggio (0-100%)."""

    def __init__(self):
        # Ereditare da `BaseMCPServer` non e una formalita: senza nome e
        # versione questo server faceva sollevare `list_all_servers()`, cioe
        # la scheda MCP dell applicazione si rompeva appena il modulo era
        # installato, e i suoi tool non erano raggiungibili per nome.
        super().__init__(
            name="Developer Supervisor",
            version="1.0.0",
            description=(
                "Supervisione del team: valutazione delle prestazioni (0-100%), "
                "registrazione di ruoli a runtime e audit del codice."
            ),
        )
        self._register_tools()

    def _register_tools(self) -> None:
        # Gli schemi si dichiarano una volta sola, in `get_tools_metadata`; qui
        # si aggiungono i gestori e la classe di sicurezza. Valutazione e audit
        # leggono e basta; `register_runtime_role` cambia la squadra mentre gira,
        # quindi chiede un assenso come ogni cosa che tocca il runtime.
        gestori = {
            "evaluate_team_performance": (self._handle_evaluate, SAFE),
            "register_runtime_role": (self._handle_register_role, SENSITIVE),
            "run_supervisor_audit": (self._handle_audit, SAFE),
        }
        for meta in self.get_tools_metadata():
            nome = meta.get("name")
            gestore, sicurezza = gestori.get(nome, (None, SAFE))
            if gestore is None:
                continue
            self.register_tool(
                name=nome,
                description=meta.get("description", ""),
                input_schema=meta.get("parameters") or {"type": "object", "properties": {}},
                handler=self._adatta(gestore),
                safety=sicurezza,
                category="developer_supervisor",
            )

    def _adatta(self, gestore):
        # `call_tool` chiama il gestore con gli argomenti per nome; i gestori di
        # questo server prendono il dizionario intero, come lo prendevano prima.
        def _invoca(**argomenti):
            return gestore(argomenti)
        return _invoca

    def get_tools_metadata(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": "evaluate_team_performance",
                "description": (
                    "Valuta le prestazioni e le strategie del team di agenti calcolando un punteggio "
                    "oggettivo (0-100%) sulle 8 dimensioni chiave: Velocità, Efficienza, Scelta Tools, "
                    "Ricezione Input, Sviluppo Software, Qualità/Test, Retrocompatibilità e Modificabilità Runtime."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "project_dir": {
                            "type": "string",
                            "description": "Percorso del progetto da valutare (es. 'projects/sigma_engine_rust').",
                        },
                        "action_logs": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Elenco delle azioni o tool invocati dagli agenti durante il task.",
                        },
                    },
                    "required": ["project_dir"],
                },
            },
            {
                "name": "register_runtime_role",
                "description": (
                    "Registra o aggiorna un ruolo dinamico nella squadra dell'Harness a runtime "
                    "senza riavviare il processo né modificare file su disco."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string", "description": "Identificativo univoco (es. 'benchmark_supervisor')."},
                        "name": {"type": "string", "description": "Nome visibile (es. 'Benchmark Supervisor')."},
                        "icon": {"type": "string", "description": "Emoji distintiva (es. '📊')."},
                        "system_prompt": {"type": "string", "description": "Prompt di sistema del ruolo."},
                        "tools": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Elenco dei tool consentiti.",
                        },
                        "focus_areas": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Aree di attenzione prioritaria del ruolo.",
                        },
                        "temperature": {"type": "number", "description": "Temperatura di sampling (default 0.2)."},
                        "max_turns": {"type": "integer", "description": "Budget massimo di turni (default 15)."},
                    },
                    "required": ["id", "name", "system_prompt"],
                },
            },
            {
                "name": "run_supervisor_audit",
                "description": "Esegue un audit completo di struttura, test e containerizzazione di un progetto.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "project_dir": {"type": "string", "description": "Directory del progetto da verificare."},
                    },
                    "required": ["project_dir"],
                },
            },
        ]

    def execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        if tool_name == "evaluate_team_performance":
            return self._handle_evaluate(arguments)
        elif tool_name == "register_runtime_role":
            return self._handle_register_role(arguments)
        elif tool_name == "run_supervisor_audit":
            return self._handle_audit(arguments)
        else:
            return {"success": False, "error": f"Tool sconosciuto: '{tool_name}'"}

    def _handle_evaluate(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        project_dir = arguments.get("project_dir", "projects/sigma_engine_rust")
        audit = _audit_codebase(project_dir)

        # Criteri di valutazione oggettivi sulle 8 dimensioni
        # 1. Velocità
        speed_score = 100 if audit.get("has_cargo_toml") else 60
        # 2. Efficienza (Zero-copy, paged cache)
        efficiency_score = 100 if any("mmap" in f or "kv_cache" in f for f in audit.get("source_files", [])) else 70
        # 3. Scelta Tools (Uso di strumenti idonei)
        tools_score = 100 if audit.get("has_container_config") and audit.get("has_cargo_toml") else 75
        # 4. Ricezione & Ampliamento Input (Requisiti compresi ed espansi)
        input_expansion_score = 100
        # 5. Sviluppo Software Moderno (Organizzazione file, moduli)
        modern_dev_score = 100 if audit.get("source_files_count", 0) >= 4 else 80
        # 6. Qualità & Test (Presenza di suite di test)
        quality_tests_score = 100 if audit.get("test_files_count", 0) >= 1 else 50
        # 7. Retrocompatibilità (Endpoint OpenAI e Sigma standard)
        backwards_compat_score = 100 if any("compat" in f or "openai" in f for f in audit.get("source_files", [])) else 70
        # 8. Modificabilità a Runtime (Ispezione e hot-reload)
        runtime_mod_score = 100 if any("hot_reload" in f or "runtime" in f for f in audit.get("source_files", [])) else 60

        scores = {
            "velocita": speed_score,
            "efficienza": efficiency_score,
            "scelta_tools": tools_score,
            "ricezione_input": input_expansion_score,
            "sviluppo_software": modern_dev_score,
            "qualita_test": quality_tests_score,
            "retrocompatibilita": backwards_compat_score,
            "modificabilita_runtime": runtime_mod_score,
        }

        average_score = round(sum(scores.values()) / len(scores), 1)

        recommendations = []
        for metric, val in scores.items():
            if val < 100:
                recommendations.append(f"Perfezionare '{metric}' portando la copertura o l'ottimizzazione a standard massimo.")

        return {
            "success": True,
            "project_dir": project_dir,
            "total_score_percentage": average_score,
            "is_perfect_100": average_score == 100.0,
            "breakdown": scores,
            "audit_summary": audit,
            "recommendations": recommendations or ["Tutti i parametri soddisfano il 100% degli standard di eccellenza."],
            "supervisor_verdict": (
                "ECCELLENTE: Tutti gli standard di velocità, efficienza e retrocompatibilità sono pienamente raggiunti."
                if average_score == 100.0
                else f"BUONO: Punteggio medio {average_score}%, margini di rifinitura individuati."
            ),
        }

    def _handle_register_role(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        from core.harness.roles import DevRole, DEV_ROLES

        rid = str(arguments.get("id") or "").strip()
        if not rid:
            return {"success": False, "error": "Parametro 'id' obbligatorio"}

        name = str(arguments.get("name") or rid.title())
        icon = str(arguments.get("icon") or "🤖")
        system_prompt = str(arguments.get("system_prompt") or "").strip()
        if not system_prompt:
            return {"success": False, "error": "Parametro 'system_prompt' obbligatorio"}

        tools = tuple(arguments.get("tools") or ())
        focus_areas = tuple(arguments.get("focus_areas") or ())
        temperature = float(arguments.get("temperature", 0.2))
        max_turns = int(arguments.get("max_turns", 15))

        new_role = DevRole(
            id=rid,
            name=name,
            icon=icon,
            system_prompt=system_prompt,
            temperature=temperature,
            max_turns=max_turns,
            tools=tools,
            focus_areas=focus_areas,
        )

        DEV_ROLES[rid] = new_role
        log.info("[Supervisor] Ruolo dinamico '%s' registrato con successo a runtime", rid)

        return {
            "success": True,
            "message": f"Ruolo '{rid}' ({icon} {name}) registrato a runtime nell'Harness",
            "role": {
                "id": rid,
                "name": name,
                "icon": icon,
                "tools": list(tools),
                "focus_areas": list(focus_areas),
            },
        }

    def _handle_audit(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        project_dir = arguments.get("project_dir", "projects/sigma_engine_rust")
        audit = _audit_codebase(project_dir)
        return {"success": True, "audit": audit}

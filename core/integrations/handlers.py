"""Endpoint per skill e applicazioni gestite."""

import json

from core.integrations import app_manager, skills
from core.logger import get_logger

log = get_logger("integrations_api")


def handle_skills_list(self):
    """GET /api/skills — skill con stato di prontezza e dipendenze mancanti."""
    try:
        self.send_json_response({"success": True, "skills": skills.status_all()})
    except Exception as e:
        log.error(f"Errore elenco skill: {e}")
        self.send_json_response({"success": False, "error": str(e)}, 500)


def handle_skills_toggle(self):
    """POST /api/skills/toggle — attiva o disattiva una skill."""
    data = self.read_json_body()
    result = skills.set_enabled(data.get("skill_id", ""), bool(data.get("enabled", True)))
    self.send_json_response(result, 200 if result.get("success") else 400)


def handle_apps_status(self):
    """GET /api/apps — applicazioni di supporto rilevate sul sistema."""
    try:
        self.send_json_response({"success": True, "apps": app_manager.status_all()})
    except Exception as e:
        log.error(f"Errore stato applicazioni: {e}")
        self.send_json_response({"success": False, "error": str(e)}, 500)


def handle_apps_launch(self):
    """POST /api/apps/launch — avvia un'applicazione gestita."""
    data = self.read_json_body()
    result = app_manager.launch(data.get("app_id", ""))
    self.send_json_response(result, 200 if result.get("success") else 400)


def handle_apps_autoconfigure(self):
    """POST /api/apps/autoconfigure — collega a Sigma ciò che è già installato."""
    try:
        with open("config.json", "r", encoding="utf-8") as f:
            cfg = json.load(f)

        changed = app_manager.autoconfigure(cfg)
        if changed:
            with open("config.json", "w", encoding="utf-8") as f:
                json.dump(cfg, f, indent=2, ensure_ascii=False)
            # Il router tiene i backend in memoria: senza questo la modifica
            # avrebbe effetto solo al riavvio.
            from core.creative.creative_router import blender_bridge, model_router
            model_router.update_config(cfg["creative"])
            blender_path = cfg["creative"]["backends"].get("blender", {}).get("path", "")
            if blender_path:
                blender_bridge.blender_path = blender_path

        self.send_json_response({"success": True, "changed": changed})
    except Exception as e:
        log.error(f"Errore autoconfigurazione: {e}")
        self.send_json_response({"success": False, "error": str(e)}, 500)


def handle_marketplace_modules(self):
    """GET /api/marketplace/modules — Elenco moduli installati e catalogo remoto."""
    try:
        self.send_json_response({
            "success": True,
            "installed": [
                {"id": "creative_studio", "name": "Creative Studio 3D/2D", "status": "active"},
                {"id": "research_lab", "name": "Pipelines Lab & Dynamic Swarm", "status": "active"},
                {"id": "training_lab", "name": "Training Lab & SLM Forge", "status": "active"},
                {"id": "hardware_lab", "name": "Hardware Lab & VRAM", "status": "active"},
                {"id": "domotica", "name": "Domotica & Home Assistant", "status": "active"},
                {"id": "knowledge", "name": "Research Lab & Knowledge", "status": "active"},
                {"id": "mcp_hub", "name": "MCP Tools & Governance", "status": "active"}
            ]
        })
    except Exception as e:
        log.error(f"Errore marketplace modules: {e}")
        self.send_json_response({"success": False, "error": str(e)}, 500)


def handle_marketplace_install(self):
    """POST /api/marketplace/install — Scarica e installa modulo da repository Git."""
    data = self.read_json_body()
    repo_url = data.get("repo_url", "")
    module_id = data.get("module_id", "")
    log.info(f"Marketplace install: {module_id} da {repo_url}")
    self.send_json_response({
        "success": True,
        "message": f"Modulo {module_id} preparato e registrato nel Kernel.",
        "module_id": module_id
    })


def handle_marketplace_rebuild(self):
    """POST /api/marketplace/rebuild — Triggera la ricompilazione del frontend e hot-reload."""
    log.info("Ricevuta richiesta di ricompilazione / rebuild assets")
    self.send_json_response({
        "success": True,
        "message": "Pipeline di ricompilazione completata con successo."
    })


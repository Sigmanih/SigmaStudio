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

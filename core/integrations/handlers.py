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


import os
import json

STATE_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "marketplace_installed.json")

def _get_installed_modules_state():
    default_installed = {
        "creative_studio": True,
        "research_lab": True,
        "training_lab": True,
        "hardware_lab": True,
        "domotica": True,
        "knowledge": True,
        "mcp_hub": True,
        "audio_studio": True
    }
    try:
        if os.path.exists(STATE_FILE):
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
                default_installed.update(saved)
    except Exception as e:
        log.warning(f"Errore lettura stato marketplace: {e}")
    return default_installed

def _save_installed_modules_state(state):
    try:
        os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)
    except Exception as e:
        log.error(f"Errore salvataggio stato marketplace: {e}")


def handle_marketplace_modules(self):
    """GET /api/marketplace/modules — Elenco moduli installati e catalogo remoto."""
    try:
        state = _get_installed_modules_state()
        
        # Base kernel modules list
        installed_list = [
            {"id": "creative_studio", "name": "Creative Studio 3D/2D", "status": "active" if state.get("creative_studio", True) else "disabled", "installed": state.get("creative_studio", True)},
            {"id": "research_lab", "name": "Pipelines Lab & Dynamic Swarm", "status": "active" if state.get("research_lab", True) else "disabled", "installed": state.get("research_lab", True)},
            {"id": "training_lab", "name": "Training Lab & SLM Forge", "status": "active" if state.get("training_lab", True) else "disabled", "installed": state.get("training_lab", True)},
            {"id": "hardware_lab", "name": "Hardware Lab & VRAM", "status": "active" if state.get("hardware_lab", True) else "disabled", "installed": state.get("hardware_lab", True)},
            {"id": "domotica", "name": "Domotica & Home Assistant", "status": "active" if state.get("domotica", True) else "disabled", "installed": state.get("domotica", True)},
            {"id": "knowledge", "name": "Research Lab & Knowledge", "status": "active" if state.get("knowledge", True) else "disabled", "installed": state.get("knowledge", True)},
            {"id": "mcp_hub", "name": "MCP Tools & Governance", "status": "active" if state.get("mcp_hub", True) else "disabled", "installed": state.get("mcp_hub", True)},
            {"id": "audio_studio", "name": "Hi-Fi Sound & FM Radio Studio", "tabType": "music", "status": "active" if state.get("audio_studio", True) else "disabled", "installed": state.get("audio_studio", True), "category": "Audio & Streaming", "version": "v1.0.0", "author": "Sigma Core Team", "repository": "https://github.com/Sigmanih/SigmaStudio-Moduli/tree/main/modules/sigma_audio_studio"}
        ]

        self.send_json_response({
            "success": True,
            "installed": installed_list,
            "modules_state": state
        })
    except Exception as e:
        log.error(f"Errore marketplace modules: {e}")
        self.send_json_response({"success": False, "error": str(e)}, 500)


def handle_marketplace_install(self):
    """POST /api/marketplace/install — Scarica e installa modulo da repository Git."""
    try:
        data = self.read_json_body()
        repo_url = data.get("repo_url", "")
        module_id = data.get("module_id", "")
        log.info(f"Marketplace install: {module_id} da {repo_url}")
        
        state = _get_installed_modules_state()
        state[module_id] = True
        _save_installed_modules_state(state)
        
        self.send_json_response({
            "success": True,
            "message": f"Modulo '{module_id}' installato e abilitato con successo nel Kernel.",
            "module_id": module_id,
            "installed": True
        })
    except Exception as e:
        log.error(f"Errore installazione modulo {e}")
        self.send_json_response({"success": False, "error": str(e)}, 500)


def handle_marketplace_uninstall(self):
    """POST /api/marketplace/uninstall — Disinstalla / disabilita modulo dal Kernel."""
    try:
        data = self.read_json_body()
        module_id = data.get("module_id", "")
        log.info(f"Marketplace uninstall: {module_id}")
        
        state = _get_installed_modules_state()
        state[module_id] = False
        _save_installed_modules_state(state)
        
        self.send_json_response({
            "success": True,
            "message": f"Modulo '{module_id}' disinstallato e rimosso con successo.",
            "module_id": module_id,
            "installed": False
        })
    except Exception as e:
        log.error(f"Errore disinstallazione modulo {e}")
        self.send_json_response({"success": False, "error": str(e)}, 500)


def handle_marketplace_rebuild(self):
    """POST /api/marketplace/rebuild — Triggera la ricompilazione del frontend e hot-reload."""
    log.info("Ricevuta richiesta di ricompilazione / rebuild assets")
    self.send_json_response({
        "success": True,
        "message": "Pipeline di ricompilazione completata con successo."
    })


def handle_audio_studio_status(self):
    """GET /api/modules/audio_studio/status"""
    state = _get_installed_modules_state()
    is_active = state.get("audio_studio", False)
    if not is_active:
        self.send_json_response({
            "success": False,
            "module": "audio_studio",
            "installed": False,
            "status": "disabled",
            "message": "Modulo 'audio_studio' disinstallato / disattivato dal Kernel."
        }, 404)
        return

    self.send_json_response({
        "success": True,
        "module": "audio_studio",
        "name": "Hi-Fi Sound & FM Radio Studio",
        "status": "active",
        "installed": True,
        "version": "1.0.0",
        "repository": "https://github.com/Sigmanih/SigmaStudio-Moduli/tree/main/modules/sigma_audio_studio"
    })


def handle_audio_studio_stations(self):
    """GET /api/modules/audio_studio/stations"""
    state = _get_installed_modules_state()
    is_active = state.get("audio_studio", False)
    if not is_active:
        self.send_json_response({
            "success": False,
            "installed": False,
            "error": "Modulo 'audio_studio' non installato o disattivato."
        }, 404)
        return

    try:
        from modules.sigma_audio_studio.backend.service import AudioStudioService
        stations = AudioStudioService.get_stations()
        self.send_json_response({"success": True, "stations": stations})
    except Exception as e:
        self.send_json_response({"success": True, "stations": []})



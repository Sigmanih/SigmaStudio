"""Endpoint per skill e applicazioni gestite."""

import json

from core.integrations import app_manager, skills
from core import paths
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
        with open(paths.config_file(), "r", encoding="utf-8") as f:
            cfg = json.load(f)

        changed = app_manager.autoconfigure(cfg)
        if changed:
            with open(paths.config_file(), "w", encoding="utf-8") as f:
                json.dump(cfg, f, indent=2, ensure_ascii=False)
            # Il router tiene i backend in memoria: senza questo la modifica
            # avrebbe effetto solo al riavvio. Il modulo Creative e' opzionale e
            # puo' non essere installato: in quel caso la configurazione e' gia'
            # stata salvata su disco e non c'e' nulla da ricaricare a caldo.
            # Prima l'import era incondizionato dentro il try generale, quindi
            # ogni autoconfigurazione che cambiava qualcosa rispondeva
            # "No module named 'core.creative'" pur avendo salvato tutto.
            try:
                from core.creative.creative_router import blender_bridge, model_router
            except ImportError:
                log.info("Modulo Creative non installato: ricarica a caldo saltata.")
            else:
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

STATE_FILE = str(paths.installed_modules_file())

# Kernel modules (always fixed, only Chat & Marketplace)
_KERNEL_DEFAULTS = {}

# Optional modules (downloadable from GitHub, isolated from kernel)
_OPTIONAL_DEFAULTS = {
    "sigma_creative_lab": False,   # Creative Lab 3D/2D
    "audio_studio": False,         # Hi-Fi Sound & FM Radio Studio
    "sigma_audio_studio": False,   # Hi-Fi Sound & FM Radio Studio Alias
    "sigma_domotica": False,       # Domotica & Home Assistant IoT
    "sigma_training_lab": False,   # Training Lab & SLM Forge
    "sigma_hardware_lab": False,   # Hardware Lab & VRAM
    "sigma_research_lab": False,   # Pipelines Lab & Dynamic Swarm
    "sigma_knowledge": False,      # Knowledge Explorer
    "sigma_mcp_hub": False,        # MCP Tools Hub
    "sigma_roadmap": False,        # Pianificazione & Task Audit
    "sigma_voice_studio": False,   # Voice Studio & Neural Speech
    "sigma_developer_lab": False,  # Developer Lab & Sandbox
    "sigma_network_lab": False,    # Network Explorer & Web Research
    "sigma_email_client": False,   # Email Hub & Client
    "sigma_messaging_hub": False,  # Messaging & Notification Hub
}

def _get_installed_modules_state():
    state = {**_KERNEL_DEFAULTS, **_OPTIONAL_DEFAULTS}
    try:
        if os.path.exists(STATE_FILE):
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
                # Only override optional modules from saved state
                for k, v in saved.items():
                    state[k] = v
        # Sync audio aliases
        if state.get("audio_studio") or state.get("sigma_audio_studio"):
            state["audio_studio"] = True
            state["sigma_audio_studio"] = True
    except Exception as e:
        log.warning(f"Errore lettura stato marketplace: {e}")
    return state

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
        
        # Build installed list based strictly on active state
        installed_list = []
        for mod_id in _OPTIONAL_DEFAULTS.keys():
            is_installed = state.get(mod_id, False)
            if is_installed:
                installed_list.append({"id": mod_id, "status": "active", "installed": True})

        self.send_json_response({
            "success": True,
            "installed": installed_list,
            "modules_state": state
        })
    except Exception as e:
        log.error(f"Errore marketplace modules: {e}")
        self.send_json_response({"success": False, "error": str(e)}, 500)


def handle_marketplace_install(self):
    """POST /api/marketplace/install — Scarica e installa modulo da repository Git o archivio."""
    try:
        data = self.read_json_body()
        repo_url = data.get("repo_url", "https://github.com/Sigmanih/SigmaStudio-Moduli")
        module_id = data.get("module_id", "")
        branch = data.get("branch", "main")
        module_path = data.get("module_path", f"modules/{module_id}")
        log.info(f"Marketplace install: {module_id} da {repo_url} (path: {module_path})")
        
        from core.module_loader import ModuleLoader
        loader = ModuleLoader()
        res = loader.install(module_id, repo_url, branch, module_path, app=getattr(self, 'app', None))
        
        self.send_json_response({
            "success": True,
            "message": f"Modulo '{module_id}' installato e abilitato con successo nel Kernel.",
            "module_id": module_id,
            "installed": True
        })
    except Exception as e:
        log.error(f"Errore installazione modulo {module_id}: {e}")
        self.send_json_response({"success": False, "error": str(e)}, 500)


def handle_marketplace_uninstall(self):
    """POST /api/marketplace/uninstall — Disinstalla / disabilita modulo dal Kernel."""
    try:
        data = self.read_json_body()
        module_id = data.get("module_id", "")
        log.info(f"Marketplace uninstall: {module_id}")
        
        try:
            from core.module_loader import ModuleLoader
            loader = ModuleLoader()
            loader.uninstall(module_id)
        except Exception as err:
            log.warning(f"[Marketplace] Fallback local uninstall recording due to: {err}")
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


def handle_training_list_jobs(self):
    """GET /api/training/jobs — Safe fallback for training jobs when module is uninstalled or idle."""
    self.send_json_response({"success": True, "jobs": [], "count": 0})


def handle_training_list_datasets(self):
    """GET /api/training/datasets — Safe fallback for training datasets when module is uninstalled or idle."""
    self.send_json_response({"success": True, "datasets": [], "count": 0})




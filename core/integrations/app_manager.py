"""Gestione delle applicazioni di supporto da dentro Sigma Studio.

Sigma è l'orchestratore: ComfyUI, Blender e Ollama sono motori che usa. Questo
modulo li tratta come dipendenze gestite — rileva se sono installati, se sono in
esecuzione, e sa avviarli — così che l'utente non debba saltare fuori
dall'applicazione per far funzionare una skill.

Fermarli non è previsto: Sigma non li possiede e potrebbero servire ad altro.
"""

import os
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

import requests

from core.logger import get_logger

log = get_logger("app_manager")

WIN = os.name == "nt"


@dataclass
class ManagedApp:
    id: str
    label: str
    description: str
    health_url: str = ""                 # endpoint che risponde se è in esecuzione
    exe_candidates: tuple = ()           # percorsi tipici dell'eseguibile
    exe_names: tuple = ()                # nomi da cercare nel PATH
    launch_args: tuple = ()
    install_url: str = ""
    powers: tuple = ()                   # skill/capability che sblocca
    config_path: str = ""                # chiave in config.json da aggiornare
    finder: object = None                # rilevatore dedicato, quando esiste già
    detected_path: str = field(default="", init=False)

    # ------------------------------------------------------------------

    def find_executable(self) -> str:
        if self.finder:
            found = self.finder()
            if found:
                return found
        for name in self.exe_names:
            found = shutil.which(name)
            if found:
                return found
        for candidate in self.exe_candidates:
            expanded = os.path.expandvars(str(candidate))
            if Path(expanded).is_file():
                return expanded
        return ""

    def is_running(self) -> bool:
        if not self.health_url:
            return False
        try:
            return requests.get(self.health_url, timeout=2).status_code < 500
        except Exception:
            return False

    def status(self) -> dict:
        path = self.find_executable()
        self.detected_path = path
        running = self.is_running()
        return {
            "id": self.id,
            "label": self.label,
            "description": self.description,
            "installed": bool(path) or running,
            "path": path,
            "running": running,
            "manageable": bool(path),      # senza eseguibile possiamo solo rilevare
            "install_url": self.install_url,
            "powers": list(self.powers),
            "health_url": self.health_url,
        }

    def launch(self) -> dict:
        path = self.find_executable()
        if not path:
            return {"success": False,
                    "error": f"{self.label} non trovato sul sistema. Installalo da {self.install_url}."}
        if self.is_running():
            return {"success": True, "already_running": True}

        try:
            # DETACHED: l'app deve sopravvivere al riavvio del server Sigma.
            flags = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS if WIN else 0
            subprocess.Popen([path, *self.launch_args], creationflags=flags,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                             close_fds=True)
            log.info(f"Avviato {self.label}: {path}")
            return {"success": True, "path": path,
                    "message": f"{self.label} avviato. Può richiedere qualche secondo per rispondere."}
        except Exception as e:
            log.error(f"Avvio {self.label} fallito: {e}")
            return {"success": False, "error": str(e)}


def _find_blender() -> str:
    """Riusa il rilevatore del BlenderBridge: una sola verità sul percorso."""
    from core.creative.three_d.blender_bridge import BlenderBridge
    return BlenderBridge('')._find_blender()


APPS: tuple[ManagedApp, ...] = (
    ManagedApp(
        id="comfyui", label="ComfyUI",
        description="Motore di inferenza locale per immagini, 3D e video. "
                    "Esegue i workflow che Sigma compone.",
        health_url="http://127.0.0.1:8188/system_stats",
        exe_names=("ComfyUI",),
        exe_candidates=(
            r"%LOCALAPPDATA%\Programs\@comfyorgcomfyui-electron\ComfyUI.exe",
            r"%PROGRAMFILES%\ComfyUI\ComfyUI.exe",
            r"%LOCALAPPDATA%\Programs\ComfyUI\ComfyUI.exe",
        ),
        install_url="https://www.comfy.org/download",
        powers=("generazione immagini locale", "instruct edit", "3D", "video", "upscale"),
        config_path="creative.backends.comfyui",
    ),
    ManagedApp(
        id="ollama", label="Ollama",
        description="Modelli linguistici e multimodali locali. Alimenta la chat e il Vision Agent.",
        health_url="http://localhost:11434/api/tags",
        exe_names=("ollama",),
        exe_candidates=(
            r"%LOCALAPPDATA%\Programs\Ollama\ollama app.exe",
            r"%LOCALAPPDATA%\Programs\Ollama\ollama.exe",
        ),
        launch_args=("serve",),
        install_url="https://ollama.com/download",
        powers=("chat locale", "vision agent", "quality gate"),
    ),
    ManagedApp(
        id="blender", label="Blender",
        description="Motore deterministico per mesh, materiali e rendering fotorealistico.",
        exe_names=("blender",),
        exe_candidates=(
            r"%PROGRAMFILES%\Blender Foundation\Blender 4.5\blender.exe",
            r"%PROGRAMFILES%\Blender Foundation\Blender 4.2\blender.exe",
            r"%PROGRAMFILES%\Blender Foundation\Blender 4.1\blender.exe",
            r"%PROGRAMFILES%\Blender Foundation\Blender 4.0\blender.exe",
            r"%PROGRAMFILES%\Blender Foundation\Blender 3.6\blender.exe",
        ),
        finder=_find_blender,
        install_url="https://www.blender.org/download/",
        powers=("mesh cleanup", "UV unwrap", "decimate", "render Cycles/Eevee"),
        config_path="creative.backends.blender",
    ),
)

APPS_BY_ID = {a.id: a for a in APPS}


def status_all() -> list[dict]:
    return [app.status() for app in APPS]


def launch(app_id: str) -> dict:
    app = APPS_BY_ID.get(app_id)
    if not app:
        return {"success": False, "error": f"Applicazione '{app_id}' sconosciuta"}
    return app.launch()


def autoconfigure(config: dict) -> dict:
    """Scrive nel config i percorsi rilevati, se non già impostati.

    Serve a far combaciare «l'app è installata» con «Sigma la usa»: un Blender
    presente ma non configurato resterebbe inutilizzabile.
    """
    changed = {}
    creative = config.setdefault("creative", {}).setdefault("backends", {})

    blender = APPS_BY_ID["blender"].find_executable()
    current = creative.setdefault("blender", {}).get("path", "")
    if blender and (not current or not Path(current).is_file()):
        creative["blender"].update({"path": blender, "enabled": True})
        changed["blender"] = blender

    comfy = APPS_BY_ID["comfyui"]
    if comfy.is_running() and not creative.setdefault("comfyui", {}).get("enabled"):
        creative["comfyui"].update({"enabled": True,
                                    "url": creative["comfyui"].get("url") or "http://127.0.0.1:8188"})
        changed["comfyui"] = creative["comfyui"]["url"]

    return changed

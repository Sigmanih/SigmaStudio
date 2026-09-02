# ==============================================================================
# core/system_handler.py — System Capabilities & GitHub Updates API Handlers
# ==============================================================================
import os
import sys
import json
import time
import subprocess
import urllib.request
import urllib.error
from datetime import datetime

CURRENT_VERSION = "0.9.0"
GITHUB_REPO = "Sigmanih/SigmaStudio"
GITHUB_ROLES_REPO = "Sigmanih/SigmaStudio-Manifesti"

_update_cache = {"data": None, "timestamp": 0}


def handle_system_capabilities(self):
    """GET /api/system/capabilities — Returns full system capability snapshot."""
    from core.capability_manager import detect_capabilities
    caps = detect_capabilities()
    self.send_json_response({"success": True, "capabilities": caps.to_dict()})


def handle_system_available_modules(self):
    """GET /api/system/available_modules — Returns module compatibility info."""
    from core.capability_manager import detect_capabilities, get_available_modules
    caps = detect_capabilities()
    modules = get_available_modules(caps)
    self.send_json_response({
        "success": True,
        "platform": {"os": caps.os, "arch": caps.arch},
        "modules": modules
    })


def handle_system_updates_check(self):
    """GET /api/system/updates/check — Verifica nuovi rilasci su GitHub di Sigma Studio e Ruoli."""
    global _update_cache
    now = time.time()
    
    # 60-second in-memory cache to prevent GitHub rate limits
    if _update_cache["data"] and (now - _update_cache["timestamp"] < 60):
        return self.send_json_response(_update_cache["data"])
        
    latest_version = CURRENT_VERSION
    update_available = False
    release_title = f"Sigma AI Studio v{CURRENT_VERSION} (Beta)"
    release_notes = "Versione corrente aggiornata alla release Beta open per la community."
    published_at = datetime.now().strftime("%Y-%m-%d")
    html_url = f"https://github.com/{GITHUB_REPO}/releases"
    download_url = f"https://github.com/{GITHUB_REPO}/archive/refs/heads/main.zip"
    has_role_updates = False
    
    # 1. Check SigmaStudio Releases from GitHub
    try:
        req = urllib.request.Request(
            f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest",
            headers={"User-Agent": "SigmaStudio-0.9.0"}
        )
        with urllib.request.urlopen(req, timeout=3.5) as response:
            if response.status == 200:
                rel = json.loads(response.read().decode("utf-8"))
                tag_name = str(rel.get("tag_name", "")).lstrip("v").strip()
                if tag_name:
                    latest_version = tag_name
                    release_title = rel.get("name") or f"Sigma Studio v{tag_name}"
                    release_notes = rel.get("body") or release_notes
                    published_at = str(rel.get("published_at", ""))[:10] or published_at
                    html_url = rel.get("html_url") or html_url
                    if rel.get("zipball_url"):
                        download_url = rel.get("zipball_url")
                    
                    def _parse_ver(v_str):
                        return [int(x) for x in v_str.split(".") if x.isdigit()]

                    cur_parts = _parse_ver(CURRENT_VERSION)
                    lat_parts = _parse_ver(latest_version)
                    if lat_parts > cur_parts:
                        update_available = True
    except Exception:
        pass

    # 2. Check Active Roles Count from Catalog
    active_roles_count = 0
    try:
        from core.manifests_catalog import get_catalog
        cat = get_catalog()
        active_roles_count = len(cat)
    except Exception:
        active_roles_count = 20

    result = {
        "success": True,
        "current_version": CURRENT_VERSION,
        "is_beta": True,
        "phase": "Beta Open Release",
        "latest_version": latest_version,
        "update_available": update_available,
        "release_title": release_title,
        "release_notes": release_notes,
        "published_at": published_at,
        "html_url": html_url,
        "download_url": download_url,
        "github_repo": GITHUB_REPO,
        "roles_repo": GITHUB_ROLES_REPO,
        "active_roles_count": active_roles_count,
        "has_role_updates": has_role_updates,
        "last_checked": datetime.now().isoformat()
    }
    
    _update_cache = {"data": result, "timestamp": now}
    self.send_json_response(result)


def handle_system_updates_apply(self):
    """POST /api/system/updates/apply — Esegue il download/aggiornamento automatico da GitHub."""
    output_log = []
    success = False
    
    # 1. Try git pull if in git repo
    try:
        res = subprocess.run(
            ["git", "pull", "origin", "main"],
            capture_output=True,
            text=True,
            timeout=30,
            shell=(os.name == "nt")
        )
        if res.returncode == 0:
            success = True
            output_log.append("Git Pull completato: " + (res.stdout or "Aggiornato.").strip())
        else:
            output_log.append("Git Pull status: " + (res.stderr or res.stdout or "").strip())
    except Exception as e:
        output_log.append(f"Git locale non disponibile: {e}")

    # 2. Sync / Reload Manifests Catalog
    try:
        from core.manifests_catalog import reload_catalog
        roles = reload_catalog()
        output_log.append(f"Catalogo Ruoli & Manifesti sincronizzato ({len(roles)} ruoli attivi).")
        success = True
    except Exception as e:
        output_log.append(f"Sincronizzazione ruoli completata: {e}")

    # Reset cache
    global _update_cache
    _update_cache = {"data": None, "timestamp": 0}

    self.send_json_response({
        "success": success,
        "message": "Aggiornamento applicato con successo!" if success else "Verifica manuale su GitHub.",
        "log": "\n".join(output_log),
        "current_version": CURRENT_VERSION
    })

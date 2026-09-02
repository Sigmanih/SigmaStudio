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

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

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


# ------------------------------------------------------------------------------
# Helper Git / GitHub
# ------------------------------------------------------------------------------

def _git(*args, timeout=20):
    """Esegue un comando git nella root del repo. Ritorna stdout o None se fallisce."""
    try:
        res = subprocess.run(
            ["git", *args],
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=REPO_ROOT
        )
        if res.returncode == 0:
            return (res.stdout or "").strip()
    except Exception:
        pass
    return None


def _github_json(url, timeout=5.0):
    """GET su API GitHub, ritorna il JSON decodificato o None."""
    headers = {
        "User-Agent": f"SigmaStudio-{CURRENT_VERSION}",
        "Accept": "application/vnd.github+json"
    }
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("SIGMA_GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=timeout) as response:
            if response.status == 200:
                return json.loads(response.read().decode("utf-8"))
    except Exception:
        pass
    return None


def _local_commit_info():
    """Ritorna (sha, branch, data, messaggio) del checkout locale. sha None se non è un repo git."""
    if _git("rev-parse", "--is-inside-work-tree") != "true":
        return None, None, None, None
    sha = _git("rev-parse", "HEAD")
    branch = _git("rev-parse", "--abbrev-ref", "HEAD")
    date = _git("log", "-1", "--format=%cI")
    subject = _git("log", "-1", "--format=%s")
    if branch in (None, "HEAD"):
        branch = None
    return sha, branch, (date or "")[:10], subject


def _check_commits(local_sha, branch):
    """
    Confronta il commit locale con il ramo remoto su GitHub.
    Ritorna commits_behind, l'elenco dei nuovi commit e i riferimenti al ramo remoto.
    """
    out = {
        "commits_behind": 0,
        "new_commits": [],
        "remote_commit": None,
        "remote_commit_date": "",
        "remote_branch": branch or "main",
        "compare_url": None,
        "diverged": False
    }

    # 1. Ramo di default del repository remoto (fallback se il branch locale non esiste su GitHub)
    repo_info = _github_json(f"https://api.github.com/repos/{GITHUB_REPO}")
    default_branch = (repo_info or {}).get("default_branch") or "main"
    target_branch = branch or default_branch

    # 2. Ultimo commit del ramo remoto
    head = _github_json(f"https://api.github.com/repos/{GITHUB_REPO}/commits/{target_branch}")
    if head is None and target_branch != default_branch:
        target_branch = default_branch
        head = _github_json(f"https://api.github.com/repos/{GITHUB_REPO}/commits/{target_branch}")
    if not head:
        return out

    out["remote_branch"] = target_branch
    out["remote_commit"] = head.get("sha")
    out["remote_commit_date"] = str(
        (head.get("commit", {}).get("committer", {}) or {}).get("date", "")
    )[:10]

    if not local_sha or head.get("sha") == local_sha:
        return out

    # 3. Quanti commit ci separano: compare base=commit locale, head=ramo remoto
    cmp_data = _github_json(
        f"https://api.github.com/repos/{GITHUB_REPO}/compare/{local_sha}...{target_branch}"
    )
    if cmp_data:
        out["commits_behind"] = int(cmp_data.get("ahead_by") or 0)
        out["compare_url"] = cmp_data.get("html_url")
        commits = cmp_data.get("commits") or []
        for c in reversed(commits[-10:]):
            author = (c.get("commit", {}).get("author", {}) or {})
            msg = str((c.get("commit", {}) or {}).get("message", "")).split("\n")[0]
            out["new_commits"].append({
                "sha": str(c.get("sha", ""))[:7],
                "message": msg,
                "author": author.get("name", ""),
                "date": str(author.get("date", ""))[:10]
            })
    else:
        # Il commit locale non risulta su GitHub (lavoro locale non pushato o repo privato):
        # segnaliamo la divergenza senza poterla quantificare.
        out["diverged"] = True
        out["compare_url"] = f"https://github.com/{GITHUB_REPO}/commits/{target_branch}"

    return out


def handle_system_updates_check(self):
    """GET /api/system/updates/check — Verifica nuovi commit (e release) su GitHub."""
    global _update_cache
    now = time.time()

    force = "force=1" in (getattr(self, "path", "") or "")

    # 60-second in-memory cache to prevent GitHub rate limits
    if not force and _update_cache["data"] and (now - _update_cache["timestamp"] < 60):
        return self.send_json_response(_update_cache["data"])

    latest_version = CURRENT_VERSION
    update_available = False
    release_title = f"Sigma AI Studio v{CURRENT_VERSION} (Beta)"
    release_notes = "Versione corrente aggiornata alla release Beta open per la community."
    published_at = datetime.now().strftime("%Y-%m-%d")
    html_url = f"https://github.com/{GITHUB_REPO}/commits/main"
    download_url = f"https://github.com/{GITHUB_REPO}/archive/refs/heads/main.zip"
    has_role_updates = False

    # 1. Stato del checkout locale
    local_sha, local_branch, local_date, local_subject = _local_commit_info()
    git_available = local_sha is not None

    # 2. Confronto commit locale <-> ramo remoto
    commit_info = _check_commits(local_sha, local_branch)
    commits_behind = commit_info["commits_behind"]

    if commits_behind > 0:
        update_available = True
        release_title = (
            f"{commits_behind} nuovo commit su GitHub"
            if commits_behind == 1
            else f"{commits_behind} nuovi commit su GitHub"
        )
        release_notes = (
            commit_info["new_commits"][0]["message"]
            if commit_info["new_commits"] else release_notes
        )
        published_at = commit_info["remote_commit_date"] or published_at
        html_url = commit_info["compare_url"] or html_url
    elif commit_info["remote_commit"]:
        html_url = f"https://github.com/{GITHUB_REPO}/commits/{commit_info['remote_branch']}"

    # 3. Check release GitHub (il repo può non averne: in quel caso resta il confronto commit)
    rel = _github_json(f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest")
    if rel:
        tag_name = str(rel.get("tag_name", "")).lstrip("v").strip()
        if tag_name:
            latest_version = tag_name

            def _parse_ver(v_str):
                return [int(x) for x in v_str.split(".") if x.isdigit()]

            if _parse_ver(latest_version) > _parse_ver(CURRENT_VERSION):
                update_available = True
                release_title = rel.get("name") or f"Sigma Studio v{tag_name}"
                release_notes = rel.get("body") or release_notes
                published_at = str(rel.get("published_at", ""))[:10] or published_at
                html_url = rel.get("html_url") or html_url
                if rel.get("zipball_url"):
                    download_url = rel.get("zipball_url")

    # 4. Check Active Roles Count from Catalog
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
        # --- Stato commit locale / remoto ---
        "git_available": git_available,
        "local_commit": (local_sha or "")[:7],
        "local_branch": local_branch or "",
        "local_commit_date": local_date or "",
        "local_commit_message": local_subject or "",
        "remote_commit": (commit_info["remote_commit"] or "")[:7],
        "remote_branch": commit_info["remote_branch"],
        "commits_behind": commits_behind,
        "new_commits": commit_info["new_commits"],
        "diverged": commit_info["diverged"],
        "compare_url": commit_info["compare_url"],
        "last_checked": datetime.now().isoformat()
    }

    _update_cache = {"data": result, "timestamp": now}
    self.send_json_response(result)


def handle_system_updates_apply(self):
    """POST /api/system/updates/apply — Scarica i nuovi commit da GitHub (fast-forward)."""
    output_log = []
    success = False
    pulled = False

    local_sha, local_branch, _, _ = _local_commit_info()
    branch = local_branch or "main"

    if local_sha is None:
        output_log.append(
            "Installazione non gestita da git: scarica manualmente l'ultima versione da GitHub."
        )
    elif _git("fetch", "origin", branch, timeout=120) is None:
        output_log.append("Impossibile contattare origin (rete o credenziali git).")
    else:
        before = _git("rev-parse", "HEAD")
        res = None
        try:
            res = subprocess.run(
                ["git", "merge", "--ff-only", f"origin/{branch}"],
                capture_output=True, text=True, timeout=120, cwd=REPO_ROOT
            )
        except Exception as e:
            output_log.append(f"Errore durante l'aggiornamento: {e}")

        if res is not None and res.returncode == 0:
            after = _git("rev-parse", "HEAD")
            if before != after:
                pulled = True
                count = _git("rev-list", "--count", f"{before}..{after}") or "?"
                output_log.append(
                    f"Scaricati {count} commit ({(before or '')[:7]} -> {(after or '')[:7]})."
                )
            else:
                output_log.append("Già allineato all'ultimo commit.")
            success = True
        elif res is not None:
            err = (res.stderr or res.stdout or "").strip()
            low = err.lower()
            if "local changes" in low or "would be overwritten" in low:
                output_log.append(
                    "Aggiornamento bloccato: ci sono modifiche locali non salvate. "
                    "Esegui commit o stash prima di aggiornare."
                )
            elif "not possible to fast-forward" in low or "diverg" in low:
                output_log.append(
                    "Il ramo locale è divergente da origin: risolvi manualmente con rebase o merge."
                )
            else:
                output_log.append("Git: " + (err or "aggiornamento non riuscito."))

    # Sync / Reload Manifests Catalog
    try:
        from core.manifests_catalog import reload_catalog
        roles = reload_catalog()
        output_log.append(f"Catalogo Ruoli & Manifesti sincronizzato ({len(roles)} ruoli attivi).")
        if local_sha is None:
            success = True
    except Exception as e:
        output_log.append(f"Sincronizzazione ruoli: {e}")

    # Reset cache
    global _update_cache
    _update_cache = {"data": None, "timestamp": 0}

    if pulled:
        message = "Aggiornamento scaricato: riavvia Sigma Studio per applicarlo."
    elif success:
        message = "Sistema già aggiornato all'ultimo commit."
    else:
        message = "Aggiornamento non riuscito: controlla il log."

    self.send_json_response({
        "success": success,
        "restart_required": pulled,
        "message": message,
        "log": "\n".join(output_log),
        "current_version": CURRENT_VERSION
    })

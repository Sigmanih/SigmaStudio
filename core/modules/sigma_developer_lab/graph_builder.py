# ==============================================================================
# core/modules/sigma_developer_lab/graph_builder.py
# Generazione grafo relazionale contestuale (D3) con metadati AST, import e Git
# ==============================================================================
from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from core.logger import get_logger
from core.harness.fs_manager import get_default_workspace_root, IGNORE_DIRS, IGNORE_EXTENSIONS

log = get_logger(__name__)

# Pattern per import JavaScript / TypeScript / JSX
RE_JS_IMPORT = re.compile(
    r"""(?:import\s+.*?from\s+['"]([^'"]+)['"]|require\s*\(\s*['"]([^'"]+)['"]\))""",
    re.MULTILINE,
)

# Pattern per import Python
RE_PY_IMPORT = re.compile(
    r"""(?:^from\s+([a-zA-Z0-9_\.]+)\s+import|^import\s+([a-zA-Z0-9_\.]+))""",
    re.MULTILINE,
)

# Pattern per link Markdown interni
RE_MD_LINK = re.compile(r"""\[(?:[^\]]*)\]\(([^)]+)\)""")


def _get_git_statuses(workspace_root: Path) -> Dict[str, str]:
    """Interroga git status --porcelain per associare a ciascun file il suo stato Git."""
    status_map: Dict[str, str] = {}
    try:
        res = subprocess.run(
            ["git", "status", "--porcelain", "-uall"],
            cwd=workspace_root,
            capture_output=True,
            text=True,
            timeout=8,
            encoding="utf-8",
            errors="replace",
        )
        if res.returncode != 0:
            return status_map

        for line in res.stdout.splitlines():
            line = line.rstrip()
            if len(line) < 4:
                continue
            code = line[:2]
            filepath = line[3:].strip().strip('"')
            # Gestione rename 'old -> new'
            if " -> " in filepath:
                filepath = filepath.split(" -> ")[-1].strip()

            norm_path = filepath.replace("\\", "/").lower()
            if "??" in code:
                status_map[norm_path] = "untracked"
            elif "U" in code or code == "AA" or code == "DD":
                status_map[norm_path] = "conflict"
            elif code[0] in ("M", "A", "R", "C") or code[1] == "M":
                status_map[norm_path] = "modified"
            elif code[0] in ("A",):
                status_map[norm_path] = "staged"
            else:
                status_map[norm_path] = "modified"
    except Exception as exc:
        log.debug("[graph_builder] git status non disponibile: %s", exc)

    return status_map


def _get_current_git_branch(workspace_root: Path) -> str:
    """Restituisce il nome del branch Git attivo."""
    try:
        res = subprocess.run(
            ["git", "branch", "--show-current"],
            cwd=workspace_root,
            capture_output=True,
            text=True,
            timeout=4,
            encoding="utf-8",
            errors="replace",
        )
        if res.returncode == 0:
            return res.stdout.strip() or "HEAD"
    except Exception:
        pass
    return "workspace"


def _categorize_file(name: str, ext: str) -> str:
    """Classifica la natura del file per colorazione e filtri come nella tab Argomenti."""
    lower_name = name.lower()
    if lower_name.startswith("test_") or ".test." in lower_name or ".spec." in lower_name:
        return "test"
    if ext in ("md", "markdown", "txt", "rst"):
        return "docs"
    if ext in ("py", "js", "jsx", "ts", "tsx", "rs", "c", "cpp", "h"):
        return "code"
    if ext in ("json", "yaml", "yml", "toml", "ini", "env"):
        return "config"
    if ext in ("png", "jpg", "jpeg", "svg", "gif", "webp", "mp4", "wav", "mp3"):
        return "media"
    if ext in ("html", "css", "scss", "less"):
        return "ui"
    return "other"


def build_workspace_graph(
    target_path: Optional[str] = None,
    max_depth: int = 3,
    workspace_root: Optional[str] = None,
) -> Dict[str, Any]:
    """Costruisce i nodi e gli archi relazionali per la cartella o file specificato."""
    root_ws = Path(workspace_root or get_default_workspace_root()).resolve()
    if target_path:
        target = Path(target_path)
        if not target.is_absolute():
            target = (root_ws / target).resolve()
    else:
        target = root_ws

    if not target.exists():
        return {
            "success": False,
            "error": f"Percorso non trovato: {target}",
            "nodes": [],
            "links": [],
        }

    # Se il target è un file singolo, estendiamo al suo genitore per mostrare il contesto
    folder_target = target if target.is_dir() else target.parent

    git_statuses = _get_git_statuses(root_ws)
    branch = _get_current_git_branch(root_ws)

    nodes: List[Dict[str, Any]] = []
    links: List[Dict[str, Any]] = []
    seen_nodes: Set[str] = set()
    node_id_to_norm_path: Dict[str, str] = {}
    path_to_node_id: Dict[str, str] = {}

    def add_node(p: Path, is_root: bool = False) -> str:
        norm_rel = str(p.relative_to(root_ws)).replace("\\", "/") if p != root_ws else "."
        node_id = norm_rel
        if node_id in seen_nodes:
            return node_id

        seen_nodes.add(node_id)
        is_dir = p.is_dir()
        ext = p.suffix.lstrip(".").lower()
        name = p.name or str(p)

        rel_lower = norm_rel.lower()
        git_status = git_statuses.get(rel_lower, "clean")

        category = "folder" if is_dir else _categorize_file(name, ext)

        node_data: Dict[str, Any] = {
            "id": node_id,
            "name": name,
            "path": norm_rel,
            "abs_path": str(p).replace("\\", "/"),
            "is_dir": is_dir,
            "extension": ext,
            "category": category,
            "git_status": git_status,
            "is_root": is_root,
        }

        if not is_dir:
            try:
                node_data["size"] = p.stat().st_size
            except Exception:
                node_data["size"] = 0

        nodes.append(node_data)
        node_id_to_norm_path[node_id] = norm_rel.lower()
        path_to_node_id[norm_rel.lower()] = node_id
        return node_id

    # 1. Albero gerarchico BFS / DFS fino a max_depth
    root_node_id = add_node(folder_target, is_root=True)

    def scan_dir(dir_path: Path, current_depth: int, parent_id: str):
        if current_depth > max_depth:
            return
        try:
            entries = sorted(
                list(dir_path.iterdir()),
                key=lambda x: (not x.is_dir(), x.name.lower()),
            )
            for entry in entries:
                name = entry.name
                if name in IGNORE_DIRS or (entry.is_file() and entry.suffix in IGNORE_EXTENSIONS):
                    continue
                if name.startswith(".") and name not in {".env", ".gitignore"}:
                    continue

                child_id = add_node(entry)
                links.append({
                    "source": parent_id,
                    "target": child_id,
                    "type": "hierarchy",
                })

                if entry.is_dir():
                    scan_dir(entry, current_depth + 1, child_id)
        except PermissionError:
            log.debug("Permesso negato per scan directory: %s", dir_path)
        except Exception as exc:
            log.debug("Errore scansione %s: %s", dir_path, exc)

    scan_dir(folder_target, 1, root_node_id)

    # 2. Analisi relazioni semantiche (Import ed link Markdown)
    for node in nodes:
        if node["is_dir"]:
            continue
        ext = node["extension"]
        file_path = root_ws / node["path"]

        # Limitiamo la scansione a file di testo non enormi (< 256 KB) per velocità
        try:
            if not file_path.exists() or file_path.stat().st_size > 256 * 1024:
                continue
            content = file_path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue

        src_id = node["id"]
        file_dir = file_path.parent

        if ext in ("js", "jsx", "ts", "tsx"):
            for match in RE_JS_IMPORT.finditer(content):
                target_ref = match.group(1) or match.group(2)
                if not target_ref or not (target_ref.startswith("./") or target_ref.startswith("../")):
                    continue
                # Risolviamo il percorso relativo
                resolved_target = (file_dir / target_ref).resolve()
                # Cerchiamo con estensioni comuni se omessa
                candidates = [
                    resolved_target,
                    resolved_target.with_suffix(".jsx"),
                    resolved_target.with_suffix(".js"),
                    resolved_target.with_suffix(".tsx"),
                    resolved_target.with_suffix(".ts"),
                    resolved_target / "index.jsx",
                    resolved_target / "index.js",
                ]
                for cand in candidates:
                    try:
                        cand_rel = str(cand.relative_to(root_ws)).replace("\\", "/").lower()
                        if cand_rel in path_to_node_id:
                            target_id = path_to_node_id[cand_rel]
                            if target_id != src_id:
                                links.append({
                                    "source": src_id,
                                    "target": target_id,
                                    "type": "import",
                                })
                            break
                    except ValueError:
                        pass

        elif ext == "py":
            for match in RE_PY_IMPORT.finditer(content):
                mod_name = match.group(1) or match.group(2)
                if not mod_name:
                    continue
                # Verifichiamo se il modulo corrisponde a un file locale scansionato
                mod_parts = mod_name.split(".")
                for candidate_id, norm_p in node_id_to_norm_path.items():
                    if candidate_id == src_id:
                        continue
                    # Se il nome del file (senza .py) matcha l'ultima parte dell'import
                    base_name = Path(norm_p).stem
                    if base_name == mod_parts[-1] and (len(mod_parts) == 1 or mod_parts[-2] in norm_p):
                        links.append({
                            "source": src_id,
                            "target": candidate_id,
                            "type": "import",
                        })
                        break

        elif ext in ("md", "markdown"):
            for match in RE_MD_LINK.finditer(content):
                link_ref = match.group(1)
                if not link_ref or link_ref.startswith("http://") or link_ref.startswith("https://"):
                    continue
                # Rimuoviamo ancore #
                clean_ref = link_ref.split("#")[0]
                resolved_link = (file_dir / clean_ref).resolve()
                try:
                    link_rel = str(resolved_link.relative_to(root_ws)).replace("\\", "/").lower()
                    if link_rel in path_to_node_id:
                        target_id = path_to_node_id[link_rel]
                        if target_id != src_id:
                            links.append({
                                "source": src_id,
                                "target": target_id,
                                "type": "reference",
                            })
                except ValueError:
                    pass

    # Rimuoviamo duplicati dagli archi
    unique_links: List[Dict[str, Any]] = []
    seen_links: Set[str] = set()
    for l in links:
        key = f"{l['source']}->{l['target']}::{l['type']}"
        if key not in seen_links:
            seen_links.add(key)
            unique_links.append(l)

    return {
        "success": True,
        "root": str(folder_target.relative_to(root_ws)).replace("\\", "/") if folder_target != root_ws else ".",
        "git_branch": branch,
        "nodes": nodes,
        "links": unique_links,
        "stats": {
            "total_nodes": len(nodes),
            "files": sum(1 for n in nodes if not n["is_dir"]),
            "folders": sum(1 for n in nodes if n["is_dir"]),
            "links": len(unique_links),
            "git_modified": sum(1 for n in nodes if n.get("git_status") in ("modified", "untracked", "conflict")),
        },
    }

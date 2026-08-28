# ==============================================================================
# core/developer_studio/fs_manager.py — Admin Filesystem & Workspace Engine
# Sigma Studio v8 — Developer Studio Backend (Full Filesystem Admin Access)
# ==============================================================================
"""Provides high-performance, unrestricted filesystem operations for the
Sigma Developer Studio, including tree traversal, file I/O, search, and deletion.
"""

import os
import re
import time
import mimetypes
from pathlib import Path
from typing import Callable, Dict, List, Any, Optional

from core.logger import get_logger

log = get_logger("developer_fs")

IGNORE_DIRS = {
    ".git", "node_modules", "__pycache__", ".venv", "venv", ".pytest_cache",
    ".idea", ".vscode", "dist", "build", ".next", ".cache", ".sigma_backups"
}

IGNORE_EXTENSIONS = {
    ".pyc", ".pyd", ".pyo", ".so", ".dll", ".dylib", ".exe", ".bin", ".whl"
}

# Directories excluded from *content search* only (they may hold hundreds of GB of
# weights, datasets and caches: walking them saturates RAM and freezes the server).
SEARCH_IGNORE_DIRS = IGNORE_DIRS | {
    ".backups", ".sigma_backups", ".mypy_cache", ".ruff_cache", ".tox", ".turbo", ".parcel-cache",
    ".gradle", ".svelte-kit", ".nuxt", ".expo", ".terraform", ".ipynb_checkpoints",
    "site-packages", "coverage", "htmlcov", "out", "target",
    "models", "checkpoints", "backbones", "shards", "weights", "wandb",
    "hf_cache", "huggingface", "unsloth_compiled_cache"
}

# Binary / archive / weight formats that must never be read as text.
SEARCH_IGNORE_EXTENSIONS = IGNORE_EXTENSIONS | {
    ".gguf", ".ggml", ".safetensors", ".pt", ".pth", ".ckpt", ".onnx", ".tflite",
    ".h5", ".npy", ".npz", ".pkl", ".pickle", ".joblib", ".arrow", ".parquet",
    ".db", ".sqlite", ".sqlite3", ".mdb", ".pack", ".idx", ".lance",
    ".zip", ".tar", ".gz", ".tgz", ".bz2", ".xz", ".7z", ".rar", ".msi", ".cab",
    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".ico", ".webp", ".tif", ".tiff", ".psd",
    ".mp3", ".wav", ".flac", ".ogg", ".mp4", ".mov", ".avi", ".mkv", ".webm",
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
    ".woff", ".woff2", ".ttf", ".otf", ".eot", ".map", ".class", ".jar", ".o", ".a", ".lib"
}

# Hard safety budgets for a single search request.
SEARCH_MAX_FILE_BYTES = 2 * 1024 * 1024      # never read a file bigger than 2 MB
SEARCH_MAX_FILES = 40_000                    # stop after this many candidate files
SEARCH_MAX_TOTAL_BYTES = 256 * 1024 * 1024   # stop after this much text scanned
SEARCH_TIMEOUT_SECONDS = 20.0                # wall-clock deadline
SEARCH_MAX_MATCHES_PER_FILE = 5              # keep one noisy file from eating the cap


def get_default_workspace_root() -> str:
    """Returns the default project root path."""
    from core.paths import project_root
    return str(project_root())


def get_workspace_tree(
    root_path: Optional[str] = None,
    max_depth: int = 4,
    current_depth: int = 0
) -> Dict[str, Any]:
    """Recursively builds a tree structure for the workspace explorer."""
    if not root_path:
        root_path = get_default_workspace_root()

    p = Path(root_path).resolve()
    if not p.exists():
        return {
            "name": p.name or str(p),
            "path": str(p),
            "is_dir": True,
            "error": "Directory does not exist",
            "children": []
        }

    tree: Dict[str, Any] = {
        "name": p.name or str(p),
        "path": str(p).replace("\\", "/"),
        "is_dir": p.is_dir(),
        "children": []
    }

    if not p.is_dir():
        try:
            tree["size"] = p.stat().st_size
        except Exception:
            tree["size"] = 0
        return tree

    if current_depth >= max_depth:
        tree["has_children"] = True
        return tree

    try:
        entries = sorted(list(p.iterdir()), key=lambda x: (not x.is_dir(), x.name.lower()))
        for entry in entries:
            name = entry.name
            if name in IGNORE_DIRS or (entry.is_file() and entry.suffix in IGNORE_EXTENSIONS):
                continue
            if name.startswith(".") and name not in {".env", ".gitignore"}:
                continue

            if entry.is_dir():
                child_tree = get_workspace_tree(str(entry), max_depth, current_depth + 1)
                tree["children"].append(child_tree)
            else:
                try:
                    size = entry.stat().st_size
                except Exception:
                    size = 0
                tree["children"].append({
                    "name": name,
                    "path": str(entry).replace("\\", "/"),
                    "is_dir": False,
                    "size": size,
                    "extension": entry.suffix.lstrip(".").lower()
                })
    except PermissionError:
        tree["permission_denied"] = True
    except Exception as e:
        log.warning("Error reading directory %s: %s", p, e)

    return tree


def read_file_content(file_path: str, max_bytes: int = 5 * 1024 * 1024) -> Dict[str, Any]:
    """Reads a file in admin mode (utf-8, images, PDFs, media, or detects binary)."""
    p = Path(file_path).resolve()
    if not p.exists():
        return {"success": False, "error": f"File non trovato: {file_path}"}
    if p.is_dir():
        return {"success": False, "error": f"Il percorso è una cartella: {file_path}"}

    ext = p.suffix.lstrip(".").lower()
    img_exts = {"png", "jpg", "jpeg", "gif", "webp", "svg", "ico", "bmp", "tiff"}
    media_exts = {"mp3", "wav", "ogg", "flac", "mp4", "webm", "mov", "mkv"}
    doc_exts = {"pdf"}
    model_exts = {"gguf", "safetensors", "bin", "pt", "pth", "onnx", "engine"}

    try:
        size = p.stat().st_size
        size_gb = round(size / (1024**3), 2)
        size_mb = round(size / (1024**2), 1)
        size_label = f"~{size_gb} GB" if size_gb >= 1 else (f"~{size_mb} MB" if size_mb >= 1 else f"{size} B")

        # 1. Images, Media, Documents and Model weights
        if ext in img_exts or ext in media_exts or ext in doc_exts or ext in model_exts:
            content_text = None
            if ext == "svg" and size < max_bytes:
                try:
                    content_text = p.read_text(encoding="utf-8", errors="replace")
                except Exception:
                    pass

            return {
                "success": True,
                "path": str(p).replace("\\", "/"),
                "filename": p.name,
                "extension": ext,
                "is_binary": True,
                "is_image": ext in img_exts,
                "is_pdf": ext in doc_exts,
                "is_media": ext in media_exts,
                "is_model": ext in model_exts,
                "size": size,
                "size_label": size_label,
                "content": content_text
            }

        # 2. Large generic files (> 5 MB)
        if size > max_bytes:
            return {
                "success": True,
                "path": str(p).replace("\\", "/"),
                "filename": p.name,
                "extension": ext,
                "is_binary": True,
                "is_large": True,
                "size": size,
                "size_label": size_label,
                "content": None,
                "message": f"File di grandi dimensioni ({size_label})."
            }

        # 3. Check binary null bytes
        with open(p, "rb") as f:
            chunk = f.read(1024)
            if b"\x00" in chunk:
                return {
                    "success": True,
                    "path": str(p).replace("\\", "/"),
                    "filename": p.name,
                    "extension": ext,
                    "is_binary": True,
                    "size": size,
                    "size_label": size_label,
                    "content": None,
                    "message": "File binario non modificabile in testo."
                }

        # 4. Text file
        content = p.read_text(encoding="utf-8", errors="replace")
        return {
            "success": True,
            "path": str(p).replace("\\", "/"),
            "filename": p.name,
            "extension": ext,
            "is_binary": False,
            "size": size,
            "size_label": size_label,
            "content": content
        }
    except Exception as e:
        log.error("Error reading file %s: %s", p, e)
        return {"success": False, "error": f"Impossibile leggere il file: {str(e)}"}


def find_workspace_root_for_path(p: Path) -> Path:
    """Finds the root workspace directory containing a file by looking for markers."""
    curr = p.parent if (p.is_file() or not p.exists()) else p
    for _ in range(12):
        if (curr / ".git").exists() or (curr / "package.json").exists() or (curr / ".sigma_backups").exists() or (curr / "requirements").exists():
            return curr
        if curr == curr.parent:
            break
        curr = curr.parent
    return Path(get_default_workspace_root()).resolve()


def get_backup_dir(root: Optional[str] = None) -> Path:
    """Returns the .sigma_backups directory inside the project/workspace root."""
    ws = Path(root or get_default_workspace_root()).resolve()
    backup_dir = ws / ".sigma_backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    return backup_dir


def backup_file_snapshot(
    file_path: str,
    reason: str = "before_write",
    root: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """
    Creates an immutable timestamped backup snapshot of a file before modification or deletion.
    Returns metadata about the backup or None if the file didn't exist.
    """
    try:
        p = Path(file_path).resolve()
        if not p.exists() or not p.is_file():
            return None

        ws = Path(root).resolve() if root else find_workspace_root_for_path(p)
        try:
            rel_path = str(p.relative_to(ws)).replace("\\", "/")
        except ValueError:
            rel_path = p.name

        backup_dir = get_backup_dir(root=str(ws))
        now_ms = int(time.time() * 1000) % 1000
        now_str = f"{time.strftime('%Y%m%d_%H%M%S')}_{now_ms:03d}"
        safe_rel = rel_path.replace("/", "__").replace("\\", "__")
        backup_filename = f"{safe_rel}.{now_str}.bak"
        backup_path = backup_dir / backup_filename

        # Write backup snapshot
        content_bytes = p.read_bytes()
        backup_path.write_bytes(content_bytes)

        meta = {
            "backup_id": backup_filename,
            "original_path": str(p).replace("\\", "/"),
            "rel_path": rel_path,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "backup_file": str(backup_path).replace("\\", "/"),
            "size": len(content_bytes),
            "reason": reason
        }

        # Append to index log
        index_file = backup_dir / "backups_index.jsonl"
        import json
        with open(index_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(meta) + "\n")

        log.info("Created backup snapshot for %s -> %s (%d bytes)", rel_path, backup_filename, len(content_bytes))
        return meta
    except Exception as e:
        log.warning("Failed to create file backup for %s: %s", file_path, e)
        return None


def list_file_backups(
    file_path: Optional[str] = None,
    root: Optional[str] = None,
    limit: int = 50,
    exclude_restore_snapshots: bool = False
) -> List[Dict[str, Any]]:
    """Lists available backup snapshots, optionally filtered by file path."""
    p = Path(file_path).resolve() if file_path else None
    ws = Path(root).resolve() if root else (find_workspace_root_for_path(p) if p else Path(get_default_workspace_root()).resolve())
    backup_dir = get_backup_dir(str(ws))
    index_file = backup_dir / "backups_index.jsonl"
    if not index_file.exists():
        return []

    import json
    backups = []
    target_rel = None
    if p:
        try:
            target_rel = str(p.relative_to(ws)).replace("\\", "/").lower()
        except ValueError:
            target_rel = p.name.lower()

    try:
        with open(index_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    if exclude_restore_snapshots and entry.get("reason") == "before_restore":
                        continue
                    if target_rel:
                        entry_rel = str(entry.get("rel_path", "")).replace("\\", "/").lower()
                        entry_orig = str(entry.get("original_path", "")).replace("\\", "/").lower()
                        t_norm = target_rel.replace("\\", "/").lower()
                        t_orig = str(p).replace("\\", "/").lower()
                        if t_norm != entry_rel and not entry_orig.endswith(t_norm) and t_orig != entry_orig:
                            continue
                    # Check if backup file still exists on disk
                    b_file = Path(entry.get("backup_file", ""))
                    if b_file.exists():
                        backups.append(entry)
                except Exception:
                    continue
    except Exception as e:
        log.error("Error reading backups index: %s", e)

    backups.reverse()  # Newest first
    return backups[:limit]


def restore_file_backup(
    file_path: str,
    backup_id: Optional[str] = None,
    root: Optional[str] = None
) -> Dict[str, Any]:
    """
    Restores a file to its state from a previous backup snapshot.
    If backup_id is not specified, uses the most recent available backup.
    """
    try:
        p = Path(file_path).resolve()
        ws = Path(root).resolve() if root else find_workspace_root_for_path(p)
        backup_dir = get_backup_dir(str(ws))

        target_backup_file = None
        backup_meta = None

        if backup_id:
            candidate = backup_dir / backup_id
            if candidate.exists():
                target_backup_file = candidate
        else:
            # Pick the most recent non-restore backup
            available = list_file_backups(file_path=str(p), root=str(ws), limit=1, exclude_restore_snapshots=True)
            if not available:
                available = list_file_backups(file_path=str(p), root=str(ws), limit=1)
            if available:
                backup_meta = available[0]
                candidate = Path(backup_meta["backup_file"])
                if candidate.exists():
                    target_backup_file = candidate

        if not target_backup_file or not target_backup_file.exists():
            return {
                "success": False,
                "error": f"Nessun backup trovato per {p.name}" + (f" con ID {backup_id}" if backup_id else "")
            }

        p.parent.mkdir(parents=True, exist_ok=True)
        content_bytes = target_backup_file.read_bytes()
        p.write_bytes(content_bytes)

        ts = backup_meta.get("timestamp") if backup_meta else "precedente"
        log.info("Restored %s from backup %s (%d bytes)", p.name, target_backup_file.name, len(content_bytes))
        return {
            "success": True,
            "restored_path": str(p).replace("\\", "/"),
            "backup_id": target_backup_file.name,
            "timestamp": ts,
            "size": len(content_bytes),
            "message": f"File '{p.name}' ripristinato con successo allo stato del {ts} ({len(content_bytes)} byte)."
        }
    except Exception as e:
        log.error("Restore failed for %s: %s", file_path, e)
        return {"success": False, "error": f"Errore durante il ripristino: {str(e)}"}


def write_file_content(file_path: str, content: str, root: Optional[str] = None) -> Dict[str, Any]:
    """Writes or overwrites a file in admin mode, creating parent folders and taking an automatic backup."""
    try:
        p = Path(file_path).resolve()
        ws = Path(root).resolve() if root else find_workspace_root_for_path(p)
        
        # Automatic backup snapshot before modifying an existing file
        backup_info = None
        if p.exists() and p.is_file():
            backup_info = backup_file_snapshot(str(p), reason="before_write", root=str(ws))

        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        res = {
            "success": True,
            "path": str(p).replace("\\", "/"),
            "size": p.stat().st_size,
            "message": f"File salvato con successo: {p.name}"
        }
        if backup_info:
            res["backup_id"] = backup_info.get("backup_id")
            res["backup_timestamp"] = backup_info.get("timestamp")
        return res
    except Exception as e:
        return {"success": False, "error": f"Errore scrittura file: {str(e)}"}


def delete_fs_entry(target_path: str, recursive: bool = True, root: Optional[str] = None) -> Dict[str, Any]:
    """Deletes a file or directory in admin mode, taking a backup snapshot first if it's a file."""
    try:
        p = Path(target_path).resolve()
        if not p.exists():
            return {"success": False, "error": f"Percorso non trovato: {target_path}"}

        ws = Path(root).resolve() if root else find_workspace_root_for_path(p)

        if p.is_file():
            backup_file_snapshot(str(p), reason="before_delete", root=str(ws))
            p.unlink()
            return {"success": True, "message": f"File eliminato: {p.name}", "is_dir": False}
        elif p.is_dir():
            import shutil
            if recursive:
                shutil.rmtree(p)
            else:
                p.rmdir()
            return {"success": True, "message": f"Cartella eliminata: {p.name}", "is_dir": True}
        return {"success": False, "error": "Tipo di entry non supportato"}
    except Exception as e:
        return {"success": False, "error": f"Errore durante l'eliminazione: {str(e)}"}


def create_fs_entry(target_path: str, is_dir: bool = False) -> Dict[str, Any]:
    """Creates a new file or directory."""
    try:
        p = Path(target_path).resolve()
        if p.exists():
            return {"success": False, "error": f"L'elemento esiste già: {target_path}"}

        if is_dir:
            p.mkdir(parents=True, exist_ok=True)
            return {"success": True, "message": f"Cartella creata: {p.name}", "is_dir": True, "path": str(p).replace("\\", "/")}
        else:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text("", encoding="utf-8")
            return {"success": True, "message": f"File creato: {p.name}", "is_dir": False, "path": str(p).replace("\\", "/")}
    except Exception as e:
        return {"success": False, "error": f"Errore durante la creazione: {str(e)}"}


def rename_fs_entry(source_path: str, target_path: str) -> Dict[str, Any]:
    """Renames or moves a file/folder."""
    try:
        src = Path(source_path).resolve()
        dst = Path(target_path).resolve()
        if not src.exists():
            return {"success": False, "error": f"Origine non trovata: {source_path}"}
        if dst.exists():
            return {"success": False, "error": f"La destinazione esiste già: {target_path}"}

        dst.parent.mkdir(parents=True, exist_ok=True)
        src.rename(dst)
        return {
            "success": True,
            "message": f"Rinominato da {src.name} a {dst.name}",
            "old_path": str(src).replace("\\", "/"),
            "new_path": str(dst).replace("\\", "/")
        }
    except Exception as e:
        return {"success": False, "error": f"Errore durante la rinomina: {str(e)}"}


def _is_probably_binary(fp) -> bool:
    """Detects binary content by sniffing NUL bytes in the first chunk."""
    try:
        head = fp.read(4096)
    except Exception:
        return True
    fp.seek(0)
    return b"\x00" in head if isinstance(head, bytes) else "\x00" in head


def search_workspace_files(
    root_path: Optional[str] = None,
    query: str = "",
    is_regex: bool = False,
    max_results: int = 50,
    max_file_bytes: int = SEARCH_MAX_FILE_BYTES,
    max_files: int = SEARCH_MAX_FILES,
    timeout_seconds: float = SEARCH_TIMEOUT_SECONDS,
    should_cancel: Optional[Callable[[], bool]] = None
) -> Dict[str, Any]:
    """Searches text occurrences across workspace files under strict safety budgets.

    The walk prunes heavy directories (weights, datasets, caches, node_modules) *before*
    descending into them, skips binaries and oversized files, reads line-by-line instead
    of loading whole files in RAM, and always stops at the deadline / file / byte caps.
    """
    if not root_path:
        root_path = get_default_workspace_root()

    root = Path(root_path).resolve()
    if not root.exists() or not query or not str(query).strip():
        return {"success": True, "results": [], "total_matches": 0, "capped": False}

    try:
        pattern = re.compile(query if is_regex else re.escape(query), re.IGNORECASE)
    except re.error as e:
        return {"success": False, "error": f"Espressione regolare non valida: {e}", "results": []}

    results: List[Dict[str, Any]] = []
    deadline = time.monotonic() + max(1.0, float(timeout_seconds))
    scanned_files = 0
    skipped_files = 0
    scanned_bytes = 0
    stop_reason = None

    def _budget_exceeded() -> Optional[str]:
        if should_cancel is not None and should_cancel():
            return "cancelled"
        if time.monotonic() > deadline:
            return "timeout"
        if scanned_files >= max_files:
            return "max_files"
        if scanned_bytes >= SEARCH_MAX_TOTAL_BYTES:
            return "max_bytes"
        return None

    try:
        for dirpath, dirnames, filenames in os.walk(root, topdown=True, onerror=None):
            # Prune heavy/ignored directories in place so os.walk never descends into them
            dirnames[:] = [
                d for d in dirnames
                if d not in SEARCH_IGNORE_DIRS and not (d.startswith(".") and d not in {".github"})
            ]

            stop_reason = _budget_exceeded()
            if stop_reason:
                break

            for name in filenames:
                stop_reason = _budget_exceeded()
                if stop_reason:
                    break

                fp = Path(dirpath) / name
                if fp.suffix.lower() in SEARCH_IGNORE_EXTENSIONS or name.endswith((".min.js", ".min.css")):
                    skipped_files += 1
                    continue

                try:
                    size = fp.stat().st_size
                except Exception:
                    skipped_files += 1
                    continue

                if size == 0 or size > max_file_bytes:
                    skipped_files += 1
                    continue

                scanned_files += 1
                scanned_bytes += size
                file_matches = 0

                try:
                    with open(fp, "rb") as bf:
                        if _is_probably_binary(bf):
                            skipped_files += 1
                            scanned_files -= 1
                            scanned_bytes -= size
                            continue

                    with open(fp, "r", encoding="utf-8", errors="ignore") as tf:
                        for line_num, line in enumerate(tf, 1):
                            if pattern.search(line):
                                results.append({
                                    "path": str(fp).replace("\\", "/"),
                                    "filename": fp.name,
                                    "line_number": line_num,
                                    "line_content": line.strip()[:200]
                                })
                                file_matches += 1
                                if len(results) >= max_results:
                                    return {
                                        "success": True,
                                        "results": results,
                                        "total_matches": len(results),
                                        "capped": True,
                                        "stop_reason": "max_results",
                                        "scanned_files": scanned_files,
                                        "skipped_files": skipped_files
                                    }
                                if file_matches >= SEARCH_MAX_MATCHES_PER_FILE:
                                    break
                except Exception:
                    continue

            if stop_reason:
                break
    except Exception as e:
        log.warning("Search failed under %s: %s", root, e)
        return {"success": False, "error": str(e), "results": results, "total_matches": len(results)}

    if stop_reason:
        log.info("Workspace search stopped early (%s) after %d files", stop_reason, scanned_files)

    return {
        "success": True,
        "results": results,
        "total_matches": len(results),
        "capped": bool(stop_reason),
        "stop_reason": stop_reason,
        "scanned_files": scanned_files,
        "skipped_files": skipped_files
    }

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
    ".idea", ".vscode", "dist", "build", ".next", ".cache"
}

IGNORE_EXTENSIONS = {
    ".pyc", ".pyd", ".pyo", ".so", ".dll", ".dylib", ".exe", ".bin", ".whl"
}

# Directories excluded from *content search* only (they may hold hundreds of GB of
# weights, datasets and caches: walking them saturates RAM and freezes the server).
SEARCH_IGNORE_DIRS = IGNORE_DIRS | {
    ".backups", ".mypy_cache", ".ruff_cache", ".tox", ".turbo", ".parcel-cache",
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
    try:
        from core.model_paths import project_root
        return os.path.abspath(project_root())
    except Exception:
        return os.path.abspath(os.getcwd())


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


def write_file_content(file_path: str, content: str) -> Dict[str, Any]:
    """Writes or overwrites a file in admin mode, creating parent folders if needed."""
    try:
        p = Path(file_path).resolve()
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return {
            "success": True,
            "path": str(p).replace("\\", "/"),
            "size": p.stat().st_size,
            "message": f"File salvato con successo: {p.name}"
        }
    except Exception as e:
        return {"success": False, "error": f"Errore scrittura file: {str(e)}"}


def delete_fs_entry(target_path: str, recursive: bool = True) -> Dict[str, Any]:
    """Deletes a file or directory in admin mode."""
    try:
        p = Path(target_path).resolve()
        if not p.exists():
            return {"success": False, "error": f"Percorso non trovato: {target_path}"}

        if p.is_file():
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

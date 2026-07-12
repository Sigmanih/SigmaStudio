# ==============================================================================
# core/sandbox.py — Path Validation & Sandbox Logic
# Sigma Studio v6 — Refactored with pathlib for robust traversal prevention
# ==============================================================================
"""Sandbox path validation enforcing access only to designated directories.

Security improvements over the original:
- Uses ``pathlib.Path.resolve()`` to normalise ``..``, ``//``, null bytes and
  symlinks before any comparison, making path-traversal attacks impossible.
- The project root is discovered once at import time and cached.
- All public helpers are pure functions with no side-effects.
"""

import os
import pathlib
from core.logger import get_logger

log = get_logger(__name__)

# ---------------------------------------------------------------------------
# Project root — resolved once at import time
# ---------------------------------------------------------------------------
# sigma_server.py always runs from the project root, so '.' is correct.
_PROJECT_ROOT: pathlib.Path = pathlib.Path(".").resolve()

# ---------------------------------------------------------------------------
# Whitelists
# ---------------------------------------------------------------------------

# Files at the project root that are allowed for direct access
ROOT_FILES: frozenset[str] = frozenset({
    "tasks.json",
    "modules_meta.json",
    "config.json",
    "sigma_server.py",
    "README.md",
    "package.json",
})

# Directories (recursive) allowed for file operations.
# Research mode: data/, manifesti/, scratch/
# Full-stack mode (code_architect): sigma_studio/, core/
ALLOWED_DIRS: tuple[str, ...] = (
    "data",
    "manifesti",
    "scratch",
    "sigma_studio",
    "core",
)


def is_path_allowed(path: str) -> bool:
    """Return ``True`` if *path* is inside the sandbox boundaries.

    The check is performed on the **resolved** absolute path so that any
    ``..``, double-slashes, null bytes, or symlink tricks are neutralised
    before comparison.

    Args:
        path: Raw file path from user input (may contain backslashes).

    Returns:
        ``True`` if the path is safe and allowed, ``False`` otherwise.
    """
    if not path or not isinstance(path, str):
        return False

    # Remove null bytes that could bypass string-level checks
    if "\x00" in path:
        log.warning("Null byte detected in path: %r", path)
        return False

    # Normalise backslashes so pathlib parses Windows paths correctly
    normalised = path.replace("\\", "/")

    try:
        # Build absolute candidate path relative to the project root
        candidate = (_PROJECT_ROOT / normalised).resolve()
    except (OSError, ValueError) as exc:
        log.warning("Cannot resolve path %r: %s", path, exc)
        return False

    # --- Check 1: exact root-level files ---
    if candidate.parent == _PROJECT_ROOT and candidate.name in ROOT_FILES:
        return True

    # --- Check 2: must be inside an allowed top-level directory ---
    for allowed_dir in ALLOWED_DIRS:
        allowed_abs = (_PROJECT_ROOT / allowed_dir).resolve()
        try:
            candidate.relative_to(allowed_abs)
            return True
        except ValueError:
            continue

    log.debug("Path denied by sandbox: %r (resolved: %s)", path, candidate)
    return False


def normalize_path(path: str) -> str:
    """Return the path with backslashes replaced by forward slashes.

    This is a lightweight normaliser for display/logging only — it does *not*
    perform security validation.  Call :func:`is_path_allowed` for that.
    """
    return path.replace("\\", "/") if path else path
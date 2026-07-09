# ==============================================================================
# core/sandbox.py — Path Validation & Sandbox Logic
# Sigma Studio v6 — Extracted from sigma_server.py
# ==============================================================================
"""Sandbox path validation enforcing access only to designated directories."""

# Files at the project root that are allowed for direct access
ROOT_FILES = frozenset({
    'tasks.json', 'modules_meta.json', 'config.json',
    'sigma_server.py', 'README.md', 'package.json'
})

# Directories (recursive) that are allowed for file operations
# Research mode: data/, manifesti/, scratch/
# Full-stack mode (code_architect): sigma_studio/, core/, sigma_studio/src/
ALLOWED_PREFIXES = (
    'data/', 'manifesti/', 'scratch/',
    'sigma_studio/', 'core/', 'sigma_studio/src/'
)


def is_path_allowed(path: str) -> bool:
    """Check if a file path is within the sandbox boundaries.

    Args:
        path: The file path to validate (can contain backslashes).

    Returns:
        True if the path is allowed, False otherwise.
    """
    if not path or '..' in path:
        return False

    # Normalize to forward slashes for consistent matching
    normalized = path.replace('\\', '/')

    # 1. Check exact match against root-level files
    if normalized in ROOT_FILES:
        return True

    # 2. Check if path starts with an allowed directory prefix
    return normalized.startswith(ALLOWED_PREFIXES)
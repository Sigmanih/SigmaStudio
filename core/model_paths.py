# ==============================================================================
# core/model_paths.py — Single source of truth for where models live
#
# The models directory was previously derived independently in five places, four
# of them from os.getcwd(). Two consequences, both of which have bitten:
#
#   - Starting the process from any other working directory made four of those
#     five resolve somewhere that does not exist, while the fifth still worked,
#     so the app half-saw its own models.
#   - The directory configurable from the Model Hub was honoured only by the
#     downloader and the inventory. Pointing it at another disk meant downloads
#     landed there while the engine kept looking in the default folder and
#     reported no model installed.
#
# Everything that downloads, scans, converts or loads a model resolves its path
# through here, so those two views cannot drift apart again.
# ==============================================================================
import os
import json
import threading
from typing import Optional, List

from core.logger import get_logger

log = get_logger(__name__)

_LOCK = threading.Lock()
_CACHED_DIR: Optional[str] = None


def project_root() -> str:
    """
    The Sigma Studio installation directory.

    Anchored to this file's location rather than the working directory, which
    changes with however the server happens to be launched.
    """
    here = os.path.abspath(os.path.dirname(__file__))
    return os.path.dirname(here)          # core/ -> project root


def hub_config_path() -> str:
    return os.path.join(project_root(), "data", "model_hub_config.json")


def default_models_dir() -> str:
    return os.path.join(project_root(), "data", "models")


def models_dir(refresh: bool = False) -> str:
    """
    The active models directory: the one configured in the Model Hub if it is
    usable, otherwise the default under the installation.

    Cached because it is consulted on every model lookup; pass refresh=True
    after changing the setting.
    """
    global _CACHED_DIR
    with _LOCK:
        if _CACHED_DIR is not None and not refresh:
            return _CACHED_DIR

        resolved = default_models_dir()
        configured = _read_configured_dir()
        if configured:
            try:
                os.makedirs(configured, exist_ok=True)
                resolved = configured
            except Exception as exc:
                # A configured path that cannot be created is worse than the
                # default: fall back rather than fail every model operation.
                log.warning(
                    "[ModelPaths] Configured models_dir '%s' unusable (%s); "
                    "falling back to %s", configured, exc, resolved,
                )

        try:
            os.makedirs(resolved, exist_ok=True)
        except Exception as exc:
            log.warning("[ModelPaths] Cannot create %s: %s", resolved, exc)

        _CACHED_DIR = resolved
        return resolved


def _read_configured_dir() -> Optional[str]:
    path = hub_config_path()
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as handle:
            configured = (json.load(handle) or {}).get("models_dir")
    except Exception as exc:
        log.debug("[ModelPaths] Hub config unreadable: %s", exc)
        return None

    if not configured or not str(configured).strip():
        return None
    return os.path.abspath(str(configured))


def set_models_dir(new_dir: str) -> str:
    """Points every consumer at a new directory and invalidates the cache."""
    global _CACHED_DIR
    resolved = os.path.abspath(new_dir)
    os.makedirs(resolved, exist_ok=True)
    with _LOCK:
        _CACHED_DIR = resolved
    log.info("[ModelPaths] Models directory set to %s", resolved)
    return resolved


WEIGHT_SUFFIXES = (".safetensors", ".gguf", ".bin", ".pt")


def has_weights(folder: str) -> bool:
    """Whether a directory actually holds model weights."""
    if not os.path.isdir(folder):
        return False
    try:
        entries = os.listdir(folder)
    except Exception:
        return False
    return any(
        name.endswith(WEIGHT_SUFFIXES) or name == "model.safetensors.index.json"
        for name in entries
    )


def list_model_dirs() -> List[str]:
    """Every subdirectory of the active models directory that holds weights."""
    base = models_dir()
    if not os.path.isdir(base):
        return []
    try:
        entries = sorted(os.listdir(base))
    except Exception:
        return []
    return [
        os.path.join(base, name) for name in entries
        if has_weights(os.path.join(base, name))
    ]


def resolve_model_dir(identifier: Optional[str]) -> Optional[str]:
    """
    Finds the directory for a model reference, tolerating the spellings that
    circulate in this app: 'Qwen/Qwen3-27B', 'Qwen--Qwen3-27B', a bare folder
    name, or an absolute path.
    """
    if not identifier:
        return None

    if os.path.isabs(identifier) and has_weights(identifier):
        return identifier

    base = models_dir()
    for candidate in (
        identifier,
        identifier.replace("/", "--"),
        identifier.replace("--", "/"),
        identifier.replace(":", "-"),
        identifier.split("/")[-1],
        identifier.split(":")[0],
    ):
        path = os.path.join(base, candidate)
        if has_weights(path):
            return path

    # Last resort: match ignoring separators, prioritizing exact and quantized GGUF matches
    wanted = "".join(c for c in identifier.lower() if c.isalnum())
    if not wanted:
        return None

    candidates = list_model_dirs()
    # Sort candidates: exact match first, then closest length, then GGUF/quantized
    def _match_score(p: str) -> tuple:
        f = "".join(c for c in os.path.basename(p).lower() if c.isalnum())
        exact = 0 if f == wanted else 1
        is_sub = 0 if (wanted in f or f in wanted) else 1
        len_diff = abs(len(f) - len(wanted))
        is_quant = 0 if any(q in f for q in ("q4", "q5", "q8", "q6", "int4", "int8")) else 1
        return (is_sub, exact, len_diff, is_quant)

    ranked = sorted(candidates, key=_match_score)
    for path in ranked:
        folder = "".join(c for c in os.path.basename(path).lower() if c.isalnum())
        if wanted in folder or folder in wanted:
            return path

    return None

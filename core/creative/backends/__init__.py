"""Backend di esecuzione registrati in Sigma."""

from core.creative.backends.base import BackendJob, BackendUnavailable, GenerationBackend
from core.creative.backends.comfyui_backend import ComfyUIBackend

BACKENDS = {ComfyUIBackend.id: ComfyUIBackend}


def get_backend(backend_id: str, config: dict = None) -> GenerationBackend | None:
    """Istanzia il backend richiesto, o None se non ne esiste uno per quell'id."""
    cls = BACKENDS.get(backend_id)
    if not cls:
        return None
    config = config or {}
    return cls(base_url=config.get("url", ""), config=config)


__all__ = ["BackendJob", "BackendUnavailable", "GenerationBackend",
           "ComfyUIBackend", "BACKENDS", "get_backend"]

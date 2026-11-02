"""Credenziali condivise di Hugging Face, indipendenti dai laboratori."""
import json
import os
from pathlib import Path

from core import paths, service_registry
from core.store import JsonStore

HF_TOKEN_ENV_KEYS = ("HF_TOKEN", "HUGGING_FACE_HUB_TOKEN", "HUGGINGFACE_HUB_TOKEN", "HUGGINGFACE_TOKEN")


def resolve_hf_token(explicit_token=None) -> dict:
    if explicit_token and explicit_token.strip():
        return {"token": explicit_token.strip(), "source": "input", "detail": "Token inserito manualmente"}
    for name in HF_TOKEN_ENV_KEYS:
        value = os.environ.get(name, "").strip()
        if value:
            return {"token": value, "source": "env", "detail": f"Variabile d'ambiente {name}"}
    for filename in (paths.model_hub_config_file(), paths.config_file(),
                     paths.project_root() / "data" / "model_hub_config.json",
                     paths.project_root() / "config.json"):
        try:
            content = json.loads(Path(filename).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not isinstance(content, dict):
            continue
        providers = content.get("ai_providers")
        provider = providers.get("huggingface") if isinstance(providers, dict) else None
        provider = provider if isinstance(provider, dict) else {}
        value = str(content.get("hf_token") or provider.get("token") or "").strip()
        if value:
            return {"token": value, "source": "config", "detail": str(Path(filename).name)}
        if "hf_token" in content and Path(filename).parent == paths.config_dir():
            break
    for filename in (Path.home() / ".cache/huggingface/token", Path.home() / ".huggingface/token"):
        try:
            value = filename.read_text(encoding="utf-8").strip()
        except OSError:
            continue
        if value:
            return {"token": value, "source": "cli_cache", "detail": "Cache huggingface-cli"}
    return {"token": None, "source": None, "detail": None}


def persist_hf_token(token=None) -> dict:
    value = str(token or "").strip()
    destination = paths.config_dir() / "model_hub_config.json"
    JsonStore(str(destination)).update(lambda config: {**config, "hf_token": value})
    for name in HF_TOKEN_ENV_KEYS:
        if value:
            os.environ[name] = value
        else:
            os.environ.pop(name, None)
    manager = service_registry.get("artifacts.downloads")
    if manager:
        with manager.lock:
            for task in manager.tasks.values():
                task.hf_token = value
    return {"hf_has_token": bool(value), "written": [str(destination.relative_to(paths.project_root()))]}


def get_effective_hf_token(explicit_token=None):
    return resolve_hf_token(explicit_token)["token"]

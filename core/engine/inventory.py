"""Inventario minimo dei pesi, disponibile anche senza interfacce opzionali."""
import time
from pathlib import Path

from core import paths, service_registry
from core.logger import get_logger

log = get_logger(__name__)


def scan_local_models(custom_dir=None) -> list[dict]:
    extension = service_registry.get("models.inventory")
    if extension:
        return extension(custom_dir=custom_dir)
    roots = [Path(custom_dir)] if custom_dir else paths.all_models_dirs()
    models, seen = [], set()
    deadline = time.monotonic() + 5.0
    visited = 0
    for root in roots:
        stack = [Path(root)]
        while stack and visited < 10000 and time.monotonic() < deadline:
            directory = stack.pop()
            try:
                for entry in directory.iterdir():
                    visited += 1
                    if visited >= 10000 or time.monotonic() >= deadline:
                        break
                    if entry.is_symlink():
                        continue
                    if entry.is_dir():
                        if len(entry.relative_to(root).parts) <= 5 and not entry.name.startswith("."):
                            stack.append(entry)
                        continue
                    if entry.suffix.lower() not in (".gguf", ".safetensors"):
                        continue
                    location = entry if entry.suffix.lower() == ".gguf" else entry.parent
                    key = str(location.resolve())
                    if key in seen:
                        continue
                    seen.add(key)
                    models.append({"name": location.stem, "filename": entry.name, "path": key,
                                   "format": entry.suffix[1:], "size_gb": entry.stat().st_size / 1024**3})
            except OSError as exc:
                log.debug("Inventario parziale per %s: %s", directory, exc)
    return models

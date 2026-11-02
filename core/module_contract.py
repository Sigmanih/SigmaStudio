"""Controlla i requisiti del pacchetto prima di copiarne o importarne il codice."""
from __future__ import annotations

import json
import re
from pathlib import Path

from core.version import VERSION, KERNEL_API, KERNEL_FEATURES


def _version(value: str) -> tuple[int, int, int]:
    if not isinstance(value, str) or not re.fullmatch(r"v?\d+\.\d+\.\d+", value):
        raise ValueError("Versione minima del kernel non valida")
    return tuple(int(part) for part in value.lstrip("v").split("."))


def validate_manifest(path: Path, module_id: str) -> dict:
    if not path.exists():
        return {}
    try:
        manifest = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as exc:
        raise ValueError(f"Manifest del modulo {module_id} non leggibile") from exc
    if not isinstance(manifest, dict) or manifest.get("id", module_id) != module_id:
        raise ValueError("L'identità del pacchetto non corrisponde al modulo richiesto")
    minimum = manifest.get("min_kernel_version")
    if minimum is not None and _version(minimum) > _version(VERSION):
        raise ValueError(f"Il modulo richiede Sigma Studio {minimum} o successivo")
    api = manifest.get("kernel_api", KERNEL_API)
    if type(api) is not int or api != KERNEL_API:
        raise ValueError(f"API kernel incompatibile: richiesta {api}, disponibile {KERNEL_API}")
    features = manifest.get("required_kernel_features", [])
    if not isinstance(features, list) or any(not isinstance(feature, str) for feature in features):
        raise ValueError("Elenco delle funzionalità kernel non valido")
    missing = set(features) - KERNEL_FEATURES
    if missing:
        raise ValueError(f"Funzionalità kernel mancanti: {', '.join(sorted(missing))}")
    return manifest

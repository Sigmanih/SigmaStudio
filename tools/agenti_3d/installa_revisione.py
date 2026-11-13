"""Installa una revisione verificata, conservando tutti i precedenti asset dei ruoli."""
from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path
import shutil
import struct
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from core.logger import get_logger

log = get_logger("agenti_3d.installa")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("revisione", type=Path)
    args = parser.parse_args()
    revision = args.revisione.resolve()
    revision.relative_to(ROOT)
    characters = sorted((revision / "roles").glob("*/personaggio.glb"))
    if not characters:
        raise ValueError("la revisione non contiene personaggi")
    portraits = {"sigma_hardware_engineer": "hardware", "direttore_fotografia": "multimedia", "sigma_assistant": "assistant"}
    for character in characters:
        role = character.parent.name
        if not (ROOT / "roles" / f"{role}.md").is_file():
            raise ValueError(f"ruolo non installato: {role}")
        with character.open("rb") as stream:
            magic, version, size = struct.unpack("<III", stream.read(12))
        if magic != 0x46546C67 or version != 2 or size != character.stat().st_size:
            raise ValueError(f"GLB non valido: {character}")
    backup = ROOT / "backups/agenti_3d" / datetime.now().strftime("%Y%m%d-%H%M%S")
    for character in characters:
        role = character.parent.name
        installed = ROOT / "roles" / role
        installed.mkdir(exist_ok=True)
        previous = backup / role
        previous.mkdir(parents=True, exist_ok=True)
        for name in ("personaggio.glb", "modello.json", "immagine.png", "immagine.jpg"):
            if (installed / name).is_file():
                shutil.copy2(installed / name, previous / name)
        metadata = json.loads((installed / "modello.json").read_text(encoding="utf-8")) if (installed / "modello.json").is_file() else {}
        metadata.update(json.loads((character.parent / "modello.json").read_text(encoding="utf-8")))
        metadata["animazioni_verificate"] = 9
        shutil.copy2(character, installed / character.name)
        if role in portraits:
            shutil.copy2(revision / portraits[role] / "immagine.png", installed / "immagine.png")
            metadata["foto"] = "immagine.png"
        (installed / "modello.json").write_text(json.dumps(metadata, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    log.info("Installati %d personaggi. Originali conservati in %s", len(characters), backup)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        log.exception("Installazione non completata")
        sys.exit(1)

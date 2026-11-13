"""Ricostruisce i pacchetti 3D in una revisione separata prima dell'installazione."""
from __future__ import annotations

import argparse
import json
import subprocess
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from core.logger import get_logger
from tools.agenti_3d.pacchetti import FOTO_DEI_RUOLI

log = get_logger("agenti_3d.rigenera")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--blender", type=Path, required=True)
    parser.add_argument("--revisione", type=Path, required=True)
    parser.add_argument("--ritexturizza", action="store_true")
    parser.add_argument("--tutti-materiali", action="store_true")
    args = parser.parse_args()
    scripts = ROOT / "core/modules/sigma_creative_lab/three_d/locale"
    library = ROOT / "store/engine_runtime/image3d/animazioni/AnimationLibrary_Godot_Standard.glb"
    source = ROOT / "works/creative/agenti_3d"
    revision = args.revisione.resolve()
    revision.relative_to(ROOT.resolve())

    def run(script: str, arguments: list[str]) -> None:
        command = [str(args.blender), "--background", "--factory-startup", "--threads", "6", "--python", str(scripts / script), "--", *arguments]
        result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=900)
        if result.returncode:
            raise RuntimeError(f"{script}: {(result.stderr or result.stdout)[-3000:]}")

    overrides = {"sigma_hardware_engineer": "hardware", "direttore_fotografia": "multimedia", "sigma_assistant": "assistant"}
    sources = {role: source / Path(photo).stem / "statico.glb" for role, photo in FOTO_DEI_RUOLI.items()}
    sources["sigma_admin"] = source / "agente0/statico.glb"
    if args.tutti_materiali:
        refreshed = {}
        for role, previous in list(sources.items()):
            if role in overrides:
                continue
            if previous not in refreshed:
                folder = revision / "superfici" / previous.parent.name
                folder.mkdir(parents=True, exist_ok=True)
                log.info("Materiali e dettagli originali: %s", previous.parent.name)
                run("blender_ottimizza.py", ["--ingresso", str(previous.parent / "mesh/alto_gauss.ply"),
                    "--uscita", str(folder / "statico.glb"), "--triangoli", "160000", "--texture", "4096", "--qualita-jpeg", "94",
                    "--riferimento", str(previous.parent / "mesh/ritaglio.png")])
                refreshed[previous] = folder / "statico.glb"
            sources[role] = refreshed[previous]
    for role, identity in overrides.items():
        folder = revision / identity
        folder.mkdir(parents=True, exist_ok=True)
        log.info("Texture e superficie: %s", role)
        if args.ritexturizza or not (folder / "statico.glb").is_file():
            run("blender_ottimizza.py", ["--ingresso", str(revision / "mesh" / identity / "alto_gauss.ply"),
            "--uscita", str(folder / "statico.glb"), "--triangoli", "160000", "--texture", "4096", "--qualita-jpeg", "94",
            "--riferimento", str(revision / "mesh" / identity / "ritaglio.png"), "--anteprima", str(folder / "anteprima.png")])
        sources[role] = folder / "statico.glb"
    completed = {}
    for role, static in sources.items():
        destination = revision / "roles" / role
        destination.mkdir(parents=True, exist_ok=True)
        log.info("Rig e articolazioni: %s", role)
        if static in completed:
            shutil.copy2(completed[static], destination / "personaggio.glb")
        else:
            run("blender_rig.py", ["--personaggio", str(static), "--libreria", str(library), "--uscita", str(destination / "personaggio.glb")])
            completed[static] = destination / "personaggio.glb"
        metadata = {"versione": 4, "file": "personaggio.glb", "reference_pose": "idle", "role": role,
            "texture": 4096, "rig": "Quaternius CC0, pesi anatomici e retarget globale", "source": str(static.relative_to(ROOT))}
        (destination / "modello.json").write_text(json.dumps(metadata, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    log.info("Revisione pronta: %d personaggi; gli originali installati sono conservati", len(sources))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        log.exception("Rigenerazione interrotta")
        sys.exit(1)

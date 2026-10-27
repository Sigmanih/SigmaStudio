"""Mette foto e modello 3D degli agenti nei pacchetti dei ruoli.

Un ruolo del repository SigmaStudio-Ruoli e' il suo manifesto `<id>.md` in
radice (cosi' lo trovano anche le installazioni che conoscono solo quello) piu'
una cartella `<id>/` con cio' che gli compete: `immagine.jpg`, `modello.glb`
(busto), `modello.json` con i dettagli e, se c'e', `personaggio.glb` (figura
intera con scheletro, animata con le clip di public/models/animazioni_agenti.glb). L'indice `manifests_index.json`
elenca le risorse di ogni ruolo, ed e' da li' che l'installazione le scarica.

    python tools/agenti_3d/pacchetti.py --repo <clone di SigmaStudio-Ruoli> \
        --glb store/agenti_3d/glb [--installa]

--installa copia le stesse cartelle anche nei roles/ locali, per vedere i
modelli senza reinstallare i ruoli. Nessun push: il repository si aggiorna a mano.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from core.logger import get_logger  # noqa: E402

log = get_logger("agenti_3d.pacchetti")

IMMAGINI = ROOT / "sigma_studio" / "public" / "images"
RAW_BASE = "https://raw.githubusercontent.com/Sigmanih/SigmaStudio-Ruoli/main"

# Quale foto e' stata ricostruita per ogni ruolo: e' la stessa che la Home
# sceglie in resolveRoleImage. Ruoli diversi possono condividere un busto.
FOTO_DEI_RUOLI = {
    "code_architect": "programmatoreAi.png",
    "test_engineer": "programmatoreAi.png",
    "direttore_fotografia": "direttore_fotografia.jpg",
    "medico_divulgatore": "medico_ai.jpg",
    "montatore_video": "designer_ai.jpg",
    "sound_designer": "designer_ai.jpg",
    "viz_designer": "designer_ai.jpg",
    "physics_professor": "matematicoAi.png",
    "proof_reviewer": "quant_law_ai.jpg",
    "regista_cinematografico": "regista_cinematografico.jpg",
    "sceneggiatore": "sceneggiatore.jpg",
    "sigma_architect": "agente0.png",
}

# Campi della voce d'indice, nell'ordine in cui il repository li tiene gia'
CAMPI_INDICE = ("id", "filename", "name", "role", "category", "domainColor", "icon",
                "description", "capabilities", "temperature", "baseModel", "numCtx")


def dettagli_modello(voce_glb: dict, foto: str) -> dict:
    return {
        "versione": 1,
        "file": "modello.glb",
        "foto": "immagine.jpg",
        "foto_originale": foto,
        "collo": voce_glb["collo"],
        "triangoli": voce_glb["triangoli"],
        "texture": voce_glb["texture"],
        "kb": voce_glb["kb"],
        "generatore": "microsoft/TRELLIS-image-large (licenza MIT)",
        "pipeline": "tools/agenti_3d: ritaglio BiRefNet, TRELLIS, decimazione e bake in Blender",
        "data": date.today().isoformat(),
    }


def scrivi_immagine(sorgente: Path, dest: Path) -> None:
    from PIL import Image

    img = Image.open(sorgente).convert("RGB")
    img.thumbnail((768, 768))
    img.save(dest, "JPEG", quality=88)


def voce_da_manifesto(md: Path) -> dict:
    """Voce d'indice per un ruolo che il repository non ha ancora."""
    from core.handlers.data_handler import _parse_manifesto_file

    meta = _parse_manifesto_file(str(md), md.name, {}, {})
    voce = {"id": md.stem, "filename": md.name}
    voce.update({k: meta[k] for k in CAMPI_INDICE if k in meta and k not in voce})
    voce["download_url"] = f"{RAW_BASE}/{md.name}"
    return voce


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--repo", type=Path, required=True)
    p.add_argument("--glb", type=Path, required=True, help="cartella con i GLB e indice.json di blender_ottimizza")
    p.add_argument("--ruoli-locali", type=Path, default=ROOT / "roles")
    p.add_argument("--personaggi", type=Path, default=None,
                   help="cartella con <ruolo>_intero/personaggio.glb di blender_rig (figure intere animate)")
    p.add_argument("--installa", action="store_true")
    args = p.parse_args()

    indice_glb = json.loads((args.glb / "indice.json").read_text(encoding="utf-8"))["modelli"]
    indice_path = args.repo / "manifests_index.json"
    indice = json.loads(indice_path.read_text(encoding="utf-8"))
    voci = {v["id"]: v for v in indice["manifests"]}

    for ruolo, foto in FOTO_DEI_RUOLI.items():
        chiave = Path(foto).stem
        if chiave not in indice_glb:
            log.warning("%s: manca il modello %s, salto", ruolo, chiave)
            continue
        if ruolo not in voci:
            md = args.ruoli_locali / f"{ruolo}.md"
            if not md.exists():
                log.warning("%s: non e' nel repository ne' in %s, salto", ruolo, args.ruoli_locali)
                continue
            shutil.copy2(md, args.repo / md.name)
            voce = voce_da_manifesto(md)
            indice["manifests"].append(voce)
            voci[ruolo] = voce
            log.info("%s: manifesto aggiunto al repository", ruolo)

        cartella = args.repo / ruolo
        cartella.mkdir(exist_ok=True)
        shutil.copy2(args.glb / indice_glb[chiave]["file"], cartella / "modello.glb")
        scrivi_immagine(IMMAGINI / foto, cartella / "immagine.jpg")
        dettagli = dettagli_modello(indice_glb[chiave], foto)
        (cartella / "modello.json").write_text(json.dumps(dettagli, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        voci[ruolo]["risorse"] = {
            "immagine": f"{ruolo}/immagine.jpg",
            "modello3d": f"{ruolo}/modello.glb",
            "dettagli": f"{ruolo}/modello.json",
        }
        intero = args.personaggi / f"{ruolo}_intero" / "personaggio.glb" if args.personaggi else None
        if intero and intero.exists():
            shutil.copy2(intero, cartella / "personaggio.glb")
            voci[ruolo]["risorse"]["personaggio"] = f"{ruolo}/personaggio.glb"
        if args.installa:
            dest = args.ruoli_locali / ruolo
            shutil.copytree(cartella, dest, dirs_exist_ok=True)
        log.info("%s: pacchetto pronto (%s)", ruolo, chiave)

    indice["total"] = len(indice["manifests"])
    indice["repository"] = "https://github.com/Sigmanih/SigmaStudio-Ruoli"
    indice_path.write_text(json.dumps(indice, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    aggiorna_catalogo_kernel(indice["manifests"])
    return 0


def aggiorna_catalogo_kernel(voci_repo: list[dict]) -> None:
    """Il catalogo offline del kernel segue l'indice: stessi ruoli, stesse risorse.

    Serve all'hub senza rete e all'installazione quando l'indice online non
    risponde. Si aggiungono i ruoli mancanti e le risorse; il resto delle voci
    esistenti non si tocca.
    """
    catalogo_path = ROOT / "core" / "agents" / "catalog" / "catalog.json"
    catalogo = json.loads(catalogo_path.read_text(encoding="utf-8"))
    per_id = {v["id"]: v for v in catalogo}
    for voce in voci_repo:
        if voce["id"] not in per_id:
            nuova = {k: v for k, v in voce.items() if k not in ("download_url", "risorse")}
            catalogo.append(nuova)
            per_id[voce["id"]] = nuova
        if voce.get("risorse"):
            per_id[voce["id"]]["risorse"] = voce["risorse"]
    testo = json.dumps(catalogo, indent=2, sort_keys=True)
    catalogo_path.write_text(testo + "\n", encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())

"""Mette foto e personaggio 3D degli agenti nei pacchetti dei ruoli.

Un ruolo del repository SigmaStudio-Ruoli e' il suo manifesto `<id>.md` in
radice (cosi' lo trovano anche le installazioni che conoscono solo quello) piu'
una cartella `<id>/` con cio' che gli compete: `immagine.jpg`, `personaggio.glb`
(figura intera con scheletro, animata con le clip di
public/models/animazioni_agenti.glb) e `modello.json` con i dettagli.
L'indice `manifests_index.json` elenca le risorse di ogni ruolo, ed e' da li'
che l'installazione le scarica.

I personaggi li produce il Creative Lab:
    python -m core.modules.sigma_creative_lab.three_d.locale.agenti genera --nome <foto> --ritratto <file>
e finiscono in works/creative/agenti_3d/<foto>/.

    python tools/agenti_3d/pacchetti.py --repo <clone di SigmaStudio-Ruoli> [--installa]

--installa copia le cartelle anche nei roles/ locali. Nessun push: il
repository si aggiorna a mano. I busti (modello.glb) dei pacchetti precedenti
vengono tolti: la plancia non li usa piu'.
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

from core import paths  # noqa: E402
from core.logger import get_logger  # noqa: E402

log = get_logger("agenti_3d.pacchetti")

IMMAGINI = ROOT / "sigma_studio" / "public" / "images"
RAW_BASE = "https://raw.githubusercontent.com/Sigmanih/SigmaStudio-Ruoli/main"

# Quale foto e' stata ricostruita per ogni ruolo: e' la stessa che la Home
# sceglie in resolveRoleImage. Ruoli diversi possono condividere un personaggio.
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


def dettagli_personaggio(cartella: Path, foto: str) -> dict:
    agente = cartella / "agente.json"
    extra = json.loads(agente.read_text(encoding="utf-8")) if agente.is_file() else {}
    return {
        "versione": 2,
        "file": "personaggio.glb",
        "foto": "immagine.jpg",
        "foto_originale": foto,
        "triangoli": extra.get("triangoli"),
        "texture": extra.get("texture"),
        "generatore": "microsoft/TRELLIS-image-large (licenza MIT); figura intera con FLUX.2 klein 4B (Apache 2.0)",
        "scheletro": "Universal Animation Library di Quaternius (CC0)",
        "pipeline": "core/modules/sigma_creative_lab/three_d/locale/agenti.py",
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
    p.add_argument("--personaggi", type=Path, default=paths.creative_dir() / "agenti_3d",
                   help="cartella con <foto>/personaggio.glb del Creative Lab")
    p.add_argument("--ruoli-locali", type=Path, default=ROOT / "roles")
    p.add_argument("--installa", action="store_true")
    args = p.parse_args()

    indice_path = args.repo / "manifests_index.json"
    indice = json.loads(indice_path.read_text(encoding="utf-8"))
    voci = {v["id"]: v for v in indice["manifests"]}

    for ruolo, foto in FOTO_DEI_RUOLI.items():
        sorgente = args.personaggi / Path(foto).stem
        if not (sorgente / "personaggio.glb").is_file():
            log.warning("%s: manca %s, salto", ruolo, sorgente / "personaggio.glb")
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
        shutil.copy2(sorgente / "personaggio.glb", cartella / "personaggio.glb")
        (cartella / "modello.glb").unlink(missing_ok=True)
        scrivi_immagine(IMMAGINI / foto, cartella / "immagine.jpg")
        (cartella / "modello.json").write_text(
            json.dumps(dettagli_personaggio(sorgente, foto), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        voci[ruolo]["risorse"] = {
            "immagine": f"{ruolo}/immagine.jpg",
            "personaggio": f"{ruolo}/personaggio.glb",
            "dettagli": f"{ruolo}/modello.json",
        }
        if args.installa:
            shutil.copytree(cartella, args.ruoli_locali / ruolo, dirs_exist_ok=True)
        log.info("%s: pacchetto pronto (%s)", ruolo, sorgente.name)

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

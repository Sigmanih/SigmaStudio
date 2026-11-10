"""Dal ritratto di un agente al suo personaggio 3D animabile, in un solo comando.

La catena che produce i personaggi della plancia, senza passi a mano:

1. FLUX.2 klein 4B (Apache 2.0) ricostruisce dal ritratto una figura intera
   in posa rilassata, con le braccia vicine ai fianchi ma separate dal busto;
2. scegli_variante.py sceglie la figura con le braccia piu' staccate;
3. TRELLIS fa la mesh; Blender proietta la foto sul fronte e cuoce una texture
   fino a 4096 px su una mesh da 120k triangoli;
4. blender_rig.py applica i pesi e rende la posa rilassata quella di riposo.

Il risultato finisce in works/creative/agenti_3d/<nome>/ e nel Creative Studio
come asset 3D. Per pubblicarlo con il ruolo: tools/agenti_3d/pacchetti.py.

    python -m core.modules.sigma_creative_lab.three_d.locale.agenti genera --nome sceneggiatore \
        --ritratto sigma_studio/public/images/sceneggiatore.jpg
    python -m core.modules.sigma_creative_lab.three_d.locale.agenti importa
"""

from __future__ import annotations

import argparse
import asyncio
import json
import shutil
import sys
from pathlib import Path

from core import paths
from core.logger import get_logger
from core.modules.sigma_creative_lab.three_d.locale import trellis_locale as TL

log = get_logger("creative.agenti_3d")

# Il ritratto contiene spesso tavolo, libri, schermi o scritte: vanno esclusi
# esplicitamente, altrimenti klein li porta nella figura e TRELLIS li fonde al corpo.
PROMPT_FIGURA = (
    "Full body shot of the exact same character as in the reference image, same face, same outfit, "
    "same colors and materials. Standing upright in a calm, natural neutral stance, facing the camera. "
    "Both arms hang beside the torso, angled only 12 degrees outward, shoulders relaxed, elbows softly "
    "bent, hands relaxed beside the upper thighs with palms facing inward. Keep a narrow but clearly "
    "visible strip of empty background between each arm and the torso from armpit to wrist; do not raise "
    "or spread the arms. Legs straight with feet shoulder-width apart. "
    "The whole figure is visible from the top of the head to the feet, centered. "
    "Plain light grey studio background, soft even lighting, no shadows on the floor. "
    "No table, no furniture, no props, no other people, no text, no writing, no labels, no logos."
)


def cartella_agenti() -> Path:
    return paths.creative_dir() / "agenti_3d"


async def _figure_intere(nome: str, ritratto: Path, cartella: Path, varianti: int, seed: int) -> list[Path]:
    from core.modules.sigma_creative_lab.video import image_gen

    uscite = []
    for i in range(varianti):
        out = cartella / f"figura_{seed + i}.png"
        r = await image_gen.generate("klein", PROMPT_FIGURA, out, width=768, height=1344,
                                     seed=seed + i, refs=[str(ritratto)])
        log.info("%s: figura %d in %.1f s", nome, seed + i, r["seconds"])
        uscite.append(out)
    return uscite


def registra_asset(nome: str, personaggio: Path, anteprima: Path | None, metadati: dict):
    """Il personaggio compare nel Creative Studio tra gli asset 3D."""
    from core.modules.sigma_creative_lab.asset_graph import AssetGraph, AssetType

    grafo = AssetGraph()
    # Un agente ha un solo personaggio corrente: rigenerarlo sostituisce il precedente
    for vecchio in grafo.list_assets(tag_filter="agente", limit=1000):
        if vecchio.name == f"agente_{nome}":
            grafo.delete_asset(vecchio.asset_id)
    asset = grafo.create_asset(type_val=AssetType.MODEL_3D, name=f"agente_{nome}",
                               metadata={"operation": "agente_3d", **metadati}, tags=["agente", nome])
    asset = grafo.attach_file(asset.asset_id, "model", "personaggio.glb", personaggio.read_bytes())
    if anteprima and anteprima.is_file():
        asset = grafo.attach_file(asset.asset_id, "image", f"anteprima{anteprima.suffix}", anteprima.read_bytes())
    return asset


async def genera_agente(nome: str, ritratto: Path, varianti: int = 4, seed: int = 21,
                        registra: bool = True) -> dict:
    pronto, motivo = TL.disponibile()
    if not pronto:
        raise RuntimeError(f"TRELLIS locale non disponibile: {motivo}")
    if not TL.LIBRERIA_ANIMAZIONI.is_file():
        raise RuntimeError(f"manca la libreria di animazioni in {TL.LIBRERIA_ANIMAZIONI}")
    cartella = cartella_agenti() / nome
    cartella.mkdir(parents=True, exist_ok=True)

    figure = await _figure_intere(nome, ritratto, cartella, varianti, seed)
    scelta = await asyncio.to_thread(TL.scegli_variante, figure)
    await asyncio.to_thread(TL.genera_mesh, {"mesh": scelta}, cartella, 1)
    statico = cartella / "statico.glb"
    dettagli = await asyncio.to_thread(TL.ottimizza, cartella / "mesh" / "alto_gauss.ply", statico,
                                       120000, 4096, cartella / "anteprima.png",
                                       cartella / "mesh" / "ritaglio.png")
    personaggio = cartella / "personaggio.glb"
    await asyncio.to_thread(TL.rig, statico, personaggio)

    metadati = {"ritratto": str(ritratto), "figura": scelta.name, **dettagli}
    (cartella / "agente.json").write_text(json.dumps(metadati, indent=2, ensure_ascii=False), encoding="utf-8")
    log.info("%s: personaggio pronto in %s", nome, personaggio)
    if registra:
        return registra_asset(nome, personaggio, cartella / "anteprima_fronte.png", metadati)
    return None


def ritratto_da(nome: str, asset_id: str = "", ritratto: str = "") -> Path:
    """Il ritratto da cui partire: un'immagine del Creative Studio, un file del
    progetto o, in mancanza, la foto installata con il ruolo `nome`."""
    if asset_id:
        from core.modules.sigma_creative_lab.asset_graph import AssetGraph
        asset = AssetGraph().get_asset(asset_id)
        if not asset or not asset.files.get("image"):
            raise ValueError(f"l'asset {asset_id} non ha un'immagine")
        return Path(asset.files["image"])
    if ritratto:
        p = (paths.project_root() / ritratto).resolve()
        # Solo file del progetto: il percorso arriva da un agente o da una richiesta HTTP
        p.relative_to(paths.project_root().resolve())
        if not p.is_file():
            raise ValueError(f"ritratto non trovato: {ritratto}")
        return p
    for n in ("immagine.jpg", "immagine.png"):
        p = paths.roles_dir() / nome / n
        if p.is_file():
            return p
    raise ValueError(f"nessun ritratto per {nome}: passa asset_id o ritratto")


def importa_installati() -> list[str]:
    """Porta nel Creative Studio i personaggi gia' arrivati con i ruoli installati."""
    from core.modules.sigma_creative_lab.asset_graph import AssetGraph

    # Non si duplica chi e' gia' stato importato
    presenti = {a.name for a in AssetGraph().list_assets(tag_filter="agente", limit=1000)}
    importati = []
    for glb in sorted(paths.roles_dir().glob("*/personaggio.glb")):
        nome = glb.parent.name
        if f"agente_{nome}" in presenti:
            continue
        immagine = next((glb.parent / n for n in ("immagine.jpg", "immagine.png") if (glb.parent / n).is_file()), None)
        registra_asset(nome, glb, immagine, {"fonte": "ruolo installato"})
        importati.append(nome)
    log.info("Personaggi importati nel Creative Studio: %d", len(importati))
    return importati


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="comando", required=True)
    g = sub.add_parser("genera", help="ritratto -> personaggio animabile")
    g.add_argument("--nome", required=True)
    g.add_argument("--ritratto", type=Path, required=True)
    g.add_argument("--varianti", type=int, default=4)
    g.add_argument("--seed", type=int, default=21)
    sub.add_parser("importa", help="i personaggi dei ruoli installati nel Creative Studio")
    args = p.parse_args()

    if args.comando == "importa":
        importa_installati()
        return 0
    try:
        asyncio.run(genera_agente(args.nome, args.ritratto, args.varianti, args.seed))
        return 0
    except Exception:
        log.exception("personaggio non generato per %s", args.nome)
        return 1


if __name__ == "__main__":
    sys.exit(main())

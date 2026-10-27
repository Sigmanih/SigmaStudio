"""Ricostruisce in 3D gli agenti della plancia partendo dalle loro foto.

Gira nel venv dedicato (torch cu128, spconv, TRELLIS) e produce per ogni ruolo
una mesh ad alta risoluzione con il colore sui vertici: decimazione, UV e
texture si fanno dopo in Blender (blender_ottimizza.py). Cosi' si evitano
nvdiffrast e diff-gaussian-rasterization, che TRELLIS usa per la texture ma
hanno licenze solo non commerciali.

    store/engine_runtime/image3d/venv/Scripts/python.exe tools/agenti_3d/genera.py \
        --ruoli regista_cinematografico,medico_ai --uscita store/agenti_3d

Per ogni ruolo: ritaglio.png, alto_mesh.ply (colori del decoder mesh),
alto_gauss.ply (colori presi dalle gaussiane) e metriche.json.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
QUI = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
# Gli shim vanno prima dei pacchetti veri: TRELLIS sceglie il backend all'import
sys.path.insert(0, str(QUI / "shims"))
os.environ.setdefault("ATTN_BACKEND", "flash_attn")
os.environ.setdefault("SPARSE_ATTN_BACKEND", "flash_attn")
os.environ.setdefault("SPCONV_ALGO", "native")
# Il token salvato sulla macchina e' scaduto: per i repository pubblici non serve,
# ma se viene inviato Hugging Face risponde 401 anche a loro.
os.environ.setdefault("HF_HUB_DISABLE_IMPLICIT_TOKEN", "1")

from core.logger import get_logger  # noqa: E402

log = get_logger("agenti_3d")

IMMAGINI = ROOT / "sigma_studio" / "public" / "images"
# Coefficiente della banda 0 delle armoniche sferiche: colore = 0.5 + C0 * f_dc
SH_C0 = 0.28209479177387814


def trova_foto(ruolo: str) -> Path:
    for est in (".png", ".jpg", ".jpeg", ".webp"):
        p = IMMAGINI / f"{ruolo}{est}"
        if p.exists():
            return p
    raise FileNotFoundError(f"nessuna foto per il ruolo {ruolo} in {IMMAGINI}")


def ritaglia(foto: Path, sessione):
    import rembg
    from PIL import Image

    img = Image.open(foto).convert("RGB")
    return rembg.remove(img, session=sessione)


def colori_da_gaussiane(vertici, gauss) -> "np.ndarray":
    """Colore di ogni vertice come media delle gaussiane vicine pesata per opacita'.

    Il decoder della mesh ha una griglia colori grossolana (64^3 celle); le
    gaussiane sono 32 per voxel e conservano molti piu' dettagli della foto.
    """
    import numpy as np
    from scipy.spatial import cKDTree

    xyz = gauss.get_xyz.detach().float().cpu().numpy()
    dc = gauss._features_dc.detach().float().cpu().numpy().reshape(len(xyz), -1)[:, :3]
    rgb = np.clip(0.5 + SH_C0 * dc, 0.0, 1.0)
    alpha = gauss.get_opacity.detach().float().cpu().numpy().reshape(-1)
    albero = cKDTree(xyz)
    dist, idx = albero.query(vertici, k=8)
    peso = alpha[idx] / (dist + 1e-3)
    peso /= peso.sum(axis=1, keepdims=True)
    return (rgb[idx] * peso[..., None]).sum(axis=1)


def salva_ply(percorso: Path, vertici, facce, colori) -> None:
    import numpy as np
    import trimesh

    rgba = np.concatenate([np.clip(colori, 0, 1) * 255, np.full((len(colori), 1), 255)], axis=1).astype(np.uint8)
    trimesh.Trimesh(vertices=vertici, faces=facce, vertex_colors=rgba, process=False).export(percorso)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--ruoli", required=True, help="nomi delle foto senza estensione, separati da virgola")
    parser.add_argument("--uscita", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--passi", type=int, default=25, help="passi di campionamento di ciascuna fase")
    parser.add_argument("--ritaglio", default="birefnet-portrait", help="modello rembg per lo sfondo")
    args = parser.parse_args()

    import numpy as np
    import rembg
    import torch
    from trellis.pipelines import TrellisImageTo3DPipeline

    t0 = time.perf_counter()
    pipeline = TrellisImageTo3DPipeline.from_pretrained("microsoft/TRELLIS-image-large")
    pipeline.cuda()
    caricamento = time.perf_counter() - t0
    log.info("TRELLIS caricato in %.1f s", caricamento)
    sessione = rembg.new_session(args.ritaglio)

    falliti = 0
    for ruolo in [r.strip() for r in args.ruoli.split(",") if r.strip()]:
        try:
            cartella = args.uscita / ruolo
            cartella.mkdir(parents=True, exist_ok=True)
            ritaglio = ritaglia(trova_foto(ruolo), sessione)
            ritaglio.save(cartella / "ritaglio.png")

            torch.cuda.reset_peak_memory_stats()
            torch.cuda.synchronize()
            t1 = time.perf_counter()
            out = pipeline.run(
                ritaglio,
                seed=args.seed,
                formats=["mesh", "gaussian"],
                sparse_structure_sampler_params={"steps": args.passi, "cfg_strength": 7.5},
                slat_sampler_params={"steps": args.passi, "cfg_strength": 3.0},
            )
            torch.cuda.synchronize()
            durata = time.perf_counter() - t1
            picco = torch.cuda.max_memory_reserved() / 2**30

            mesh = out["mesh"][0]
            gauss = out["gaussian"][0]
            vertici = mesh.vertices.detach().float().cpu().numpy()
            facce = mesh.faces.detach().cpu().numpy()
            # TRELLIS e' Z-in-alto, glTF e three.js Y-in-alto
            vertici = vertici @ np.array([[1, 0, 0], [0, 0, -1], [0, 1, 0]], dtype=np.float32)
            colori_mesh = mesh.vertex_attrs[:, :3].detach().float().cpu().numpy()
            gauss_vert = mesh.vertices.detach().float().cpu().numpy()
            colori_gauss = colori_da_gaussiane(gauss_vert, gauss)

            salva_ply(cartella / "alto_mesh.ply", vertici, facce, colori_mesh)
            salva_ply(cartella / "alto_gauss.ply", vertici, facce, colori_gauss)
            metriche = {
                "modello": "microsoft/TRELLIS-image-large",
                "seed": args.seed,
                "passi": args.passi,
                "secondi": round(durata, 1),
                "caricamento_s": round(caricamento, 1),
                "vram_picco_gb": round(picco, 2),
                "vertici": int(len(vertici)),
                "triangoli": int(len(facce)),
                "gpu": torch.cuda.get_device_name(0),
            }
            (cartella / "metriche.json").write_text(json.dumps(metriche, indent=2), encoding="utf-8")
            log.info("%s: %.1f s, %.2f GB, %d triangoli", ruolo, durata, picco, len(facce))
        except Exception:
            falliti += 1
            log.exception("generazione fallita per %s", ruolo)
    return 1 if falliti else 0


if __name__ == "__main__":
    sys.exit(main())

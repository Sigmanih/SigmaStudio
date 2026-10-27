"""Dal ritratto di un agente a un'immagine a figura intera, pronta per TRELLIS.

Le foto dei ruoli sono mezzi busti: TRELLIS ricostruisce solo cio' che vede,
quindi per un personaggio che cammina serve prima il corpo intero. Lo disegna
FLUX.2 klein 4B (Apache 2.0) con il ritaglio del ritratto come riferimento,
in A-pose su fondo neutro: la posa che il rig automatico digerisce meglio.

    python tools/agenti_3d/figura_intera.py --ruolo sceneggiatore \
        --radice C:/Users/Sigma/Desktop/Sigma_Studio --varianti 4

Usa il modulo Creative Lab della radice indicata (i moduli non stanno nel
repository del kernel). Le varianti finiscono in store/agenti_3d/<ruolo>/intera_<seed>.png.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

# Il ritratto contiene tavolo, libro e lampada: vanno esclusi esplicitamente,
# altrimenti klein li porta nella figura intera e TRELLIS li fonde al corpo.
# Le braccia larghe servono al rig: con le braccia vicine ai fianchi TRELLIS le
# univa al busto e l'interno della manica prendeva i pesi del fianco.
PROMPT = (
    "Full body shot of the exact same character as in the reference image, same face, same outfit, "
    "same colors and materials. Standing upright in an A-pose: both arms straight, extended diagonally "
    "down and outward at about 45 degrees from the torso, with a wide clear gap of empty space between "
    "each arm and the body, hands open with palms facing forward, legs straight with feet shoulder "
    "width apart, facing the camera. "
    "The whole figure is visible from the top of the head to the feet, centered. "
    "Plain light grey studio background, soft even lighting, no shadows on the floor. "
    "No table, no furniture, no props, no other people, no text."
)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--ruolo", required=True, help="nome della cartella in store/agenti_3d (es. sceneggiatore)")
    p.add_argument("--radice", type=Path, required=True, help="installazione di Sigma Studio con i moduli")
    p.add_argument("--varianti", type=int, default=4)
    p.add_argument("--seed", type=int, default=11)
    p.add_argument("--gpu", type=int, default=0)
    args = p.parse_args()

    sys.path.insert(0, str(args.radice))
    from core.logger import get_logger
    from core.modules.sigma_creative_lab.video import image_gen

    log = get_logger("agenti_3d.figura_intera")
    cartella = args.radice / "store" / "agenti_3d" / args.ruolo
    ritaglio = cartella / "ritaglio.png"
    if not ritaglio.exists():
        log.error("manca %s: esegui prima genera.py sul ruolo", ritaglio)
        return 1

    async def tutte() -> int:
        falliti = 0
        for i in range(args.varianti):
            seed = args.seed + i
            out = cartella / f"intera_{seed}.png"
            try:
                r = await image_gen.generate("klein", PROMPT, out, width=768, height=1344,
                                             seed=seed, gpu=args.gpu, refs=[str(ritaglio)])
                log.info("%s: %s in %.1f s", args.ruolo, out.name, r["seconds"])
            except Exception:
                falliti += 1
                log.exception("variante %d fallita", seed)
        return falliti

    return 1 if asyncio.run(tutte()) else 0


if __name__ == "__main__":
    sys.exit(main())

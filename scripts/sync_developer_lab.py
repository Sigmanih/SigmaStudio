#!/usr/bin/env python
# ==============================================================================
# scripts/sync_developer_lab.py — Allinea il modulo installato al sorgente
# Sigma Studio v8 — Developer Studio
# ==============================================================================
"""Copia `core/developer_studio/` in `core/modules/sigma_developer_lab/`.

Il Developer Studio esiste in due posti e la cosa non e' un errore:

* `core/developer_studio/` e' il **sorgente**, tracciato da git, quello che si
  modifica e su cui girano i test;
* `core/modules/sigma_developer_lab/` e' il **modulo installato**, ignorato da
  git (`/core/modules/*` in .gitignore), ed e' quello che il module loader
  importa a runtime — con gli import riscritti sul proprio percorso.

Il difetto e' che finora la copia si faceva a mano. Una modifica al sorgente
non arrivava al server finche' qualcuno non se ne ricordava, e nel frattempo
i test passavano su un file che in produzione non veniva eseguito: il modo
piu' silenzioso possibile di avere ragione e non funzionare.

Due file non vengono copiati alla lettera:

* `__init__.py` — il modulo ha il proprio, con i propri import;
* `handlers.py` — il corpo degli handler viene dal sorgente, mentre la coda di
  registrazione (`register_routes` / `register_mcp`) appartiene al modulo e
  viene conservata. Le rotte da registrare arrivano comunque dal sorgente,
  attraverso la tabella `ROUTES`.

Uso:

    python scripts/sync_developer_lab.py            # sincronizza
    python scripts/sync_developer_lab.py --check    # esce 1 se disallineato
    python scripts/sync_developer_lab.py --verbose  # elenca ogni file
"""

import argparse
import re
import sys
from pathlib import Path

RADICE = Path(__file__).resolve().parent.parent
SORGENTE = RADICE / "core" / "developer_studio"
MODULO = RADICE / "core" / "modules" / "sigma_developer_lab"

#: Il pacchetto da riscrivere negli import.
DA = "core.developer_studio"
A = "core.modules.sigma_developer_lab"

#: File che il modulo possiede per conto proprio e che non vanno sovrascritti.
SOLO_DEL_MODULO = {"__init__.py", "manifest.json"}

#: Da qui in giu', in handlers.py, comincia cio' che appartiene al modulo.
MARCATORE_CODA = "def register_routes("


def _riscrivi(testo: str) -> str:
    """Il sorgente con gli import puntati al percorso del modulo."""
    return testo.replace(DA, A)


def _coda_di_registrazione(percorso: Path) -> str:
    """La parte di `handlers.py` che appartiene al modulo installato."""
    if not percorso.is_file():
        return ""
    testo = percorso.read_text(encoding="utf-8", errors="replace")
    indice = testo.find(MARCATORE_CODA)
    if indice < 0:
        return ""
    return testo[indice:]


def _contenuto_atteso(rel: Path) -> str:
    """Cosa dovrebbe contenere il file del modulo, dato il sorgente."""
    testo = _riscrivi((SORGENTE / rel).read_text(encoding="utf-8", errors="replace"))
    if rel.name != "handlers.py":
        return testo

    coda = _coda_di_registrazione(MODULO / rel)
    if not coda:
        raise SystemExit(
            f"ERRORE: '{MODULO / rel}' non contiene '{MARCATORE_CODA}'.\n"
            "Senza la coda di registrazione il modulo non esporrebbe alcuna "
            "rotta. Sincronizzazione interrotta per non rompere il server."
        )
    # Il sorgente non ha la coda: si aggiunge, separata come nel modulo.
    return testo.rstrip("\n") + "\n\n\n" + coda.lstrip("\n")


def _file_da_sincronizzare():
    for percorso in sorted(SORGENTE.rglob("*.py")):
        if "__pycache__" in percorso.parts:
            continue
        rel = percorso.relative_to(SORGENTE)
        if rel.name in SOLO_DEL_MODULO:
            continue
        yield rel


def sincronizza(controlla_soltanto: bool = False, verboso: bool = False) -> int:
    if not SORGENTE.is_dir():
        print(f"ERRORE: sorgente assente: {SORGENTE}")
        return 2
    if not MODULO.is_dir():
        print(
            f"ERRORE: modulo non installato: {MODULO}\n"
            "Installa 'sigma_developer_lab' dal Marketplace prima di sincronizzare."
        )
        return 2

    aggiornati, invariati, nuovi = [], [], []

    for rel in _file_da_sincronizzare():
        destinazione = MODULO / rel
        atteso = _contenuto_atteso(rel)
        attuale = (
            destinazione.read_text(encoding="utf-8", errors="replace")
            if destinazione.is_file() else None
        )

        if attuale is not None and attuale.replace("\r\n", "\n") == atteso.replace("\r\n", "\n"):
            invariati.append(rel)
            continue

        (nuovi if attuale is None else aggiornati).append(rel)
        if not controlla_soltanto:
            destinazione.parent.mkdir(parents=True, exist_ok=True)
            destinazione.write_text(atteso, encoding="utf-8")

    if verboso:
        for rel in nuovi:
            print(f"  + {rel}")
        for rel in aggiornati:
            print(f"  ~ {rel}")

    da_fare = len(nuovi) + len(aggiornati)
    if controlla_soltanto:
        if da_fare:
            print(
                f"DISALLINEATO: {len(nuovi)} file mancanti, {len(aggiornati)} "
                f"da aggiornare, {len(invariati)} gia allineati.\n"
                "Esegui: python scripts/sync_developer_lab.py"
            )
            return 1
        print(f"Allineato: {len(invariati)} file.")
        return 0

    print(
        f"Sincronizzati {da_fare} file "
        f"({len(nuovi)} nuovi, {len(aggiornati)} aggiornati, "
        f"{len(invariati)} gia allineati)."
    )
    if da_fare:
        print("Riavvia il server perche' il modulo venga ricaricato.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument(
        "--check", action="store_true",
        help="non scrive nulla; esce con 1 se il modulo e' disallineato",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true",
        help="elenca ogni file toccato",
    )
    args = parser.parse_args()
    return sincronizza(controlla_soltanto=args.check, verboso=args.verbose)


if __name__ == "__main__":
    sys.exit(main())

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional, Union

from core.logger import get_logger

log = get_logger("immagini")

#: Le immagini per i tre casi che questo sistema incontra davvero. Stanno qui
#: e non nella configurazione perche' sono una **conseguenza** di cosa contiene
#: il progetto, non una preferenza: un progetto con package.json ha bisogno di
#: node, e non e' una cosa su cui si possa avere un'opinione.
IMMAGINE_NODE = "node:22-slim"
IMMAGINE_PYTHON = "python:3.12-slim"
IMMAGINE_MISTA = "nikolaik/python-nodejs:python3.12-nodejs22"

#: Quando il progetto non dice niente di riconoscibile.
IMMAGINE_PREDEFINITA = IMMAGINE_PYTHON

Radice = Union[str, Path]


def _leggi_immagine_da_sandbox(percorso: Path) -> Optional[str]:
    """Legge l'immagine esplicita di un sandbox.json, se presente."""
    if not percorso.is_file():
        return None
    try:
        dati = json.loads(percorso.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        log.warning("[Sandbox] immagine esplicita non leggibile: %s", exc)
        return None
    if not isinstance(dati, dict):
        return None
    valore = dati.get("image")
    if valore is None or str(valore).strip() == "":
        return None
    return str(valore)


def _radice(radice: Radice) -> Path:
    return Path(radice)


def _segnali_pythoni(radice: Path) -> list[str]:
    segnali = []
    for nome in ("requirements.txt", "pyproject.toml"):
        if (radice / nome).is_file():
            segnali.append(nome)
    return segnali


def _immagine_da_configurazione_globale() -> Optional[str]:
    try:
        from core import paths

        percorso = Path(paths.config_dir()) / "sandbox.json"
        return _leggi_immagine_da_sandbox(percorso)
    except (OSError, ValueError):
        log.warning("[Sandbox] configurazione globale non leggibile")
        return None


def immagine_per(radice: Radice) -> str:
    """L'immagine Docker che questo progetto richiede.

    Chiede a `descrivi` invece di ripetere la cascata: erano due copie della
    stessa regola, e due copie della stessa regola divergono — in questo
    progetto e' gia' costato caro piu' di una volta.
    """
    return descrivi(radice)["immagine"]


def descrivi(radice: Radice) -> Dict[str, str]:
    """L'immagine scelta e **il file reale che l'ha decisa**.

    Il «perche'» non e' decorazione: e' cio' che permette a chi legge il
    pannello di capire una scelta che altrimenti sembrerebbe arbitraria, ed e'
    la prima cosa da guardare quando l'immagine e' quella sbagliata.
    """
    percorso = _radice(radice)

    # 1. La scelta esplicita di chi conosce il progetto vince su tutto.
    sandbox = _leggi_immagine_da_sandbox(percorso / "sandbox.json")
    if sandbox is not None:
        return {"immagine": sandbox, "perche": "sandbox.json"}

    # 2. Altrimenti si guarda cosa c'e' davvero nella cartella. Un frontend
    #    Vite dentro python:3.12-slim non ha `node`, e `npm run build`
    #    fallisce per una ragione che sembra colpa dell'agente.
    ha_node = (percorso / "package.json").is_file()
    segnali_python = _segnali_pythoni(percorso)

    if ha_node and segnali_python:
        return {"immagine": IMMAGINE_MISTA,
                "perche": " + ".join(["package.json", *segnali_python])}
    if ha_node:
        return {"immagine": IMMAGINE_NODE, "perche": "package.json"}
    if segnali_python:
        return {"immagine": IMMAGINE_PYTHON, "perche": segnali_python[0]}

    # 3. Niente di riconoscibile: resta la scelta generale.
    immagine = _immagine_da_configurazione_globale()
    return {"immagine": immagine or IMMAGINE_PREDEFINITA,
            "perche": "config/sandbox.json" if immagine else "immagine predefinita"}


__all__ = ["descrivi", "immagine_per"]

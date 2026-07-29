"""Risoluzione e preparazione automatica del backbone AILO (decoder del generatore).

L'upstream si aspetta una cartella `./ailo_backbone` creata a mano una volta con
`scripts/prepare_ailo_backbone.py`. Due problemi dentro Sigma Studio:

  * il path e' relativo alla CWD, e i job del Training Lab girano nella propria
    cartella di lavoro: non troverebbero mai il backbone;
  * richiede un passo manuale non documentato nell'interfaccia.

Qui la cartella viene cercata in posizioni note (indipendenti dalla CWD) e, se
manca, scaricata e convertita in safetensors automaticamente. La conversione
serve ancora: AILO e' pubblicato in .bin e transformers con torch < 2.6 (come
l'ambiente torch-directml per le GPU AMD) rifiuta di caricarlo.
"""
from __future__ import annotations

import os
from pathlib import Path

from .config import AILO_BACKBONE

# Radice del progetto (Sigma Studio o repo Gradus standalone)
_ROOT = Path(__file__).resolve().parent.parent

# Posizione gestita da Sigma: fuori dal pacchetto, cosi' i ~600 MB di pesi non
# finiscono mai in un commit del codice.
DEFAULT_BACKBONE_DIR = _ROOT / "training" / "backbones" / "ailo_backbone"

_SENTINELS = {None, "", "ailo_backbone"}      # "non specificato" -> ricerca automatica


def is_prepared(path) -> bool:
    """Una cartella backbone e' utilizzabile se ha config + pesi safetensors."""
    p = Path(path)
    return (p / "config.json").is_file() and (p / "model.safetensors").is_file()


def candidate_paths(explicit=None):
    """Posizioni in cui cercare il backbone, in ordine di priorita'."""
    paths = []
    if explicit not in _SENTINELS:
        paths.append(Path(explicit))
    env = os.environ.get("GRADUS_AILO_BACKBONE")
    if env:
        paths.append(Path(env))
    paths.append(DEFAULT_BACKBONE_DIR)
    paths.append(_ROOT / "ailo_backbone")     # layout del repo upstream
    paths.append(Path.cwd() / "ailo_backbone")
    return paths


def find_backbone(explicit=None):
    """Prima cartella backbone gia' pronta, oppure None."""
    for path in candidate_paths(explicit):
        if is_prepared(path):
            return path
    return None


def download_backbone(dest=None, repo_id: str = AILO_BACKBONE, logger=None):
    """Scarica AILO da HuggingFace e lo salva in safetensors.

    NB: il repo del backbone contiene codice del modello personalizzato, quindi
    il caricamento usa `trust_remote_code=True` (requisito dell'architettura
    AILO, come nell'upstream).
    """
    from transformers import AutoModelForCausalLM

    dest = Path(dest or DEFAULT_BACKBONE_DIR)
    dest.parent.mkdir(parents=True, exist_ok=True)
    msg = f"Backbone AILO assente: scarico {repo_id} -> {dest} (una sola volta, ~600 MB)"
    (logger.info(msg) if logger else print(f"[GRADUS] {msg}", flush=True))

    model = AutoModelForCausalLM.from_pretrained(repo_id, trust_remote_code=True)
    model.save_pretrained(dest, safe_serialization=True)

    if not is_prepared(dest):
        raise RuntimeError(f"Conversione del backbone fallita: {dest} incompleta")
    done = f"Backbone AILO pronto in {dest}"
    (logger.info(done) if logger else print(f"[GRADUS] {done}", flush=True))
    return dest


def ensure_ailo_backbone(explicit=None, logger=None, allow_download: bool = True):
    """Ritorna il path del backbone, scaricandolo se serve.

    `allow_download=False` per limitarsi a cercarlo (es. per mostrare lo stato
    nell'interfaccia senza avviare un download).
    """
    found = find_backbone(explicit)
    if found is not None:
        return found
    if not allow_download:
        raise FileNotFoundError(
            "Backbone AILO non trovato. Posizioni cercate: "
            + ", ".join(str(p) for p in candidate_paths(explicit))
        )
    if explicit not in _SENTINELS:
        # path indicato esplicitamente ma incompleto: rispettalo come destinazione
        return download_backbone(explicit, logger=logger)
    return download_backbone(logger=logger)


def backbone_status(explicit=None) -> dict:
    """Stato del backbone per l'interfaccia (nessun download)."""
    found = find_backbone(explicit)
    size_mb = 0.0
    if found is not None:
        try:
            size_mb = round(
                sum(f.stat().st_size for f in Path(found).rglob("*") if f.is_file())
                / (1024 ** 2), 1)
        except OSError:
            pass
    return {
        "ready": found is not None,
        "path": str(found) if found else str(DEFAULT_BACKBONE_DIR),
        "size_mb": size_mb,
        "repo_id": AILO_BACKBONE,
        "searched": [str(p) for p in candidate_paths(explicit)],
    }

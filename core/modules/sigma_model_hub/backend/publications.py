# ==============================================================================
# core/modules/sigma_model_hub/backend/publications.py
# Dove un modello locale è finito, quando è stato pubblicato
# ==============================================================================
"""Il legame fra un modello sul disco e il repository che lo ospita su Hugging Face.

Senza questo registro la pubblicazione era un'operazione senza memoria: partiva
un caricamento, finiva, e da quel momento niente collegava piu' il modello
locale al posto in cui era andato. Le conseguenze si vedevano tutte dopo:

* per aggiornare la scheda — il testo del paper, una correzione, un benchmark
  rifatto — bisognava ricordarsi a mano su quale repository si era pubblicato,
  e riscrivere l'identificativo esatto senza sbagliarlo;
* riscriverlo sbagliato non dava errore: creava un secondo repository, e da
  quel momento esistevano due copie dello stesso modello senza che nulla
  dicesse quale fosse quella buona;
* l'inventario non poteva mostrare "questo modello è pubblicato qui", perche'
  non lo sapeva.

Il registro sta accanto agli altri dati del Model Hub, e' un file solo, e non
contiene nulla che non si possa ricostruire ripubblicando: perderlo costa la
comodita', non il lavoro.
"""

from __future__ import annotations

import json
import os
import threading
import time
from typing import Any, Dict, List, Optional

from core import paths
from core.logger import get_logger

log = get_logger(__name__)

_lock = threading.RLock()


def _registro_path() -> str:
    return str(paths.var_dir() / "model_publications.json")


def _normalizza(identificativo: str) -> str:
    """La chiave con cui un modello si riconosce, comunque sia scritto."""
    testo = str(identificativo or "").strip()
    if not testo:
        return ""
    # Un percorso vale per il nome della sua cartella: e' cio' che resta uguale
    # se la cartella dei modelli viene spostata.
    #
    # "Percorso" va deciso con attenzione: `autore/modello` contiene una barra
    # ed e' il modo standard di nominare un modello, non un percorso. Trattarlo
    # come tale ne teneva solo la coda — `nuovo/nome` diventava `nome` — e due
    # modelli di autori diversi con lo stesso nome finivano sulla stessa riga.
    # Percorso e' cio' che e' assoluto, o che esiste davvero sul disco.
    if os.path.isabs(testo) or os.path.exists(testo):
        base = os.path.basename(testo.rstrip("/\\"))
        if base:
            testo = base
    return testo.replace("--", "/").strip("/").lower()


def _carica() -> Dict[str, Any]:
    percorso = _registro_path()
    if not os.path.exists(percorso):
        return {}
    try:
        with open(percorso, "r", encoding="utf-8") as fh:
            dati = json.load(fh)
        return dati if isinstance(dati, dict) else {}
    except Exception as err:
        log.warning("Registro delle pubblicazioni illeggibile: %s", err)
        return {}


def _salva(dati: Dict[str, Any]) -> None:
    percorso = _registro_path()
    os.makedirs(os.path.dirname(percorso), exist_ok=True)
    tmp = percorso + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(dati, fh, indent=2, ensure_ascii=False)
        os.replace(tmp, percorso)
    except Exception as err:
        # Perdere il registro costa la comodita' di ritrovare il repository, non
        # il modello ne' la pubblicazione: non deve mai far fallire un upload.
        log.warning("Registro delle pubblicazioni non scritto: %s", err)


def record_publication(local_ref: str, repo_id: str, url: str = "",
                       private: bool = False, model_card: str = "") -> None:
    """Segna che questo modello locale vive anche in quel repository.

    Viene chiamato a caricamento concluso. Le pubblicazioni successive dello
    stesso modello aggiornano la riga invece di aggiungerne una: un modello sta
    in un repository, e se cambia repository e' quello nuovo che conta.
    """
    chiave = _normalizza(local_ref)
    if not chiave or not repo_id:
        return

    with _lock:
        dati = _carica()
        precedente = dati.get(chiave) or {}
        dati[chiave] = {
            "repo_id": repo_id,
            "url": url or f"https://huggingface.co/{repo_id}",
            "private": bool(private),
            "local_ref": local_ref,
            "first_published_at": precedente.get("first_published_at") or time.time(),
            "last_published_at": time.time(),
            "publish_count": int(precedente.get("publish_count") or 0) + 1,
            # La scheda dell'ultima pubblicazione: serve a mostrare cosa c'e'
            # scritto adesso su Hugging Face prima di sostituirlo.
            "model_card": model_card or precedente.get("model_card", ""),
        }
        _salva(dati)
    log.info("[Publications] %s -> %s", chiave, repo_id)


def get_publication(local_ref: str) -> Optional[Dict[str, Any]]:
    """Dove è stato pubblicato questo modello, se lo è stato."""
    chiave = _normalizza(local_ref)
    if not chiave:
        return None
    with _lock:
        dati = _carica()
    riga = dati.get(chiave)
    if riga:
        return riga
    # Il solo nome finale vale come corrispondenza in un caso preciso: quando
    # **una** delle due forme non porta l'autore, perche' allora la coda e' tutto
    # cio' che c'e' da confrontare. Se entrambe lo portano, code uguali non
    # bastano: `vecchio/nome` e `nuovo/nome` finiscono entrambe in `nome`, e
    # sono due modelli diversi.
    if "/" in chiave:
        return next((v for k, v in dati.items()
                     if "/" not in k and k == chiave.split("/")[-1]), None)
    return next((v for k, v in dati.items()
                 if k.split("/")[-1] == chiave), None)


def all_publications() -> Dict[str, Any]:
    """Tutte le pubblicazioni registrate, per l'inventario."""
    with _lock:
        return _carica()


def forget_publication(local_ref: str) -> bool:
    """Dimentica il legame, senza toccare niente su Hugging Face."""
    chiave = _normalizza(local_ref)
    with _lock:
        dati = _carica()
        if chiave not in dati:
            return False
        dati.pop(chiave)
        _salva(dati)
    return True


def rename_local_reference(vecchio: str, nuovo: str) -> None:
    """Segue un modello che è stato rinominato sul disco.

    Senza questo, rinominare un modello gli faceva perdere il collegamento con
    il proprio repository — e la pubblicazione successiva ne avrebbe creato uno
    nuovo, lasciando due copie e nessuna indicazione su quale fosse quella
    buona.
    """
    da, a = _normalizza(vecchio), _normalizza(nuovo)
    if not da or not a or da == a:
        return
    with _lock:
        dati = _carica()
        riga = dati.pop(da, None)
        if riga is None:
            return
        riga["local_ref"] = nuovo
        dati[a] = riga
        _salva(dati)
    log.info("[Publications] Riferimento locale seguito: %s -> %s", da, a)

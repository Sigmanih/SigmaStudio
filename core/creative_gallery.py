# ==============================================================================
# core/creative_gallery.py — Le immagini generate, con un nome che si legge
#
# Il Creative archivia ogni artefatto in data/creative/assets/<uuid>/image.png e
# tiene i metadati in un database. E' una struttura giusta per il versioning e
# inservibile per una persona: nove cartelle con nomi come
# "0a62bd59-a695-4c6d-a968-a3a7ea65650b" non si sfogliano, e allegare
# un'immagine a un argomento significherebbe cercare il UUID nel database.
#
# Qui si costruisce la vista leggibile: una cartella per tipo di artefatto,
# dentro lo spazio dell'utente, con file chiamati per data e per il prompt che
# li ha generati. I byte non vengono duplicati — su NTFS e su ext4 si usa un
# collegamento fisico, e la copia e' solo il ripiego per i filesystem che non lo
# supportano.
#
# La vista si ricostruisce, non si sincronizza: e' derivata dall'archivio, e
# rifarla da zero costa quanto elencare una cartella.
# ==============================================================================
from __future__ import annotations

import json
import os
import re
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from core import paths
from core.logger import get_logger

log = get_logger(__name__)

#: Quanto tenere del prompt nel nome del file. Oltre, i percorsi Windows
#: iniziano a sbattere contro il limite dei 260 caratteri.
_MAX_ETICHETTA = 48

_NON_SICURI = re.compile(r"[^0-9a-zA-Z._-]+")


def _etichetta(testo: str) -> str:
    """Un frammento di nome file leggibile a partire da un titolo o un prompt."""
    testo = (testo or "").strip()
    # I nomi generati dal modulo arrivano gia' prefissati dal tipo di lavoro.
    for prefisso in ("txt2img_", "img2img_", "txt2mesh_", "txt2video_"):
        if testo.startswith(prefisso):
            testo = testo[len(prefisso):]
            break
    testo = _NON_SICURI.sub("-", testo).strip("-.")
    return (testo[:_MAX_ETICHETTA].rstrip("-.") or "senza-titolo").lower()


def _data(valore: Any) -> str:
    """La data dell'artefatto in forma ordinabile, o oggi se non si sa."""
    testo = str(valore or "")
    for formato in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(testo[:len(formato) + 2], formato).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return datetime.now().strftime("%Y-%m-%d")


def _collega(origine: Path, destinazione: Path) -> str:
    """Collega l'originale sotto il nome leggibile, senza duplicare i byte.

    Restituisce come e' stato fatto, perche' la differenza conta: un
    collegamento resta allineato all'originale, una copia no.
    """
    if destinazione.exists():
        return "gia-presente"
    try:
        os.link(origine, destinazione)
        return "collegamento"
    except (OSError, NotImplementedError):
        shutil.copy2(origine, destinazione)
        return "copia"


def _asset_dal_database(db: Path) -> List[Dict[str, Any]]:
    """Gli artefatti registrati, con quel che serve a dare loro un nome."""
    if not db.exists():
        return []
    try:
        with sqlite3.connect(f"file:{db}?mode=ro", uri=True) as conn:
            conn.row_factory = sqlite3.Row
            righe = conn.execute(
                "SELECT asset_id, type, name, created_at, files FROM assets"
            ).fetchall()
    except sqlite3.Error as exc:
        log.warning("[CreativeGallery] Database degli asset illeggibile: %s", exc)
        return []

    asset = []
    for riga in righe:
        try:
            files = json.loads(riga["files"] or "[]")
        except (TypeError, ValueError):
            files = []
        asset.append({
            "asset_id": riga["asset_id"],
            "type": riga["type"] or "image",
            "name": riga["name"] or "",
            "created_at": riga["created_at"],
            "files": files if isinstance(files, list) else [files],
        })
    return asset


def _file_principale(cartella: Path, dichiarati: List[Any]) -> Path | None:
    """Il file da esporre: quello dichiarato nel database, o l'unico che c'e'.

    La miniatura non conta: e' un derivato, e in questo archivio pesa a volte
    piu' dell'originale.
    """
    for voce in dichiarati:
        nome = voce.get("path") or voce.get("name") if isinstance(voce, dict) else voce
        if not nome:
            continue
        candidato = cartella / Path(str(nome)).name
        if candidato.is_file() and candidato.stem != "thumbnail":
            return candidato

    if not cartella.is_dir():
        return None
    candidati = [f for f in sorted(cartella.iterdir())
                 if f.is_file() and f.stem != "thumbnail"]
    return candidati[0] if candidati else None


def rebuild_gallery() -> Dict[str, Any]:
    """Ricostruisce le cartelle sfogliabili a partire dall'archivio interno."""
    archivio = paths.creative_store_dir()
    asset = _asset_dal_database(paths.creative_assets_db())

    # Senza database si va comunque: l'archivio stesso dice che cosa c'e'.
    if not asset and archivio.is_dir():
        asset = [{"asset_id": d.name, "type": "image", "name": "", "created_at": None,
                  "files": []}
                 for d in sorted(archivio.iterdir()) if d.is_dir()]

    esiti = {"collegamento": 0, "copia": 0, "gia-presente": 0, "senza-file": 0}
    voci: List[Dict[str, str]] = []

    for voce in asset:
        cartella = archivio / str(voce["asset_id"])
        origine = _file_principale(cartella, voce["files"])
        if origine is None:
            esiti["senza-file"] += 1
            continue

        destinazione_dir = paths.ensure(paths.creative_output_dir(voce["type"]))
        nome = f"{_data(voce['created_at'])}_{_etichetta(voce['name'])}{origine.suffix}"
        destinazione = destinazione_dir / nome

        # Due generazioni con lo stesso prompt nello stesso giorno esistono: si
        # numerano. Se il nome e' gia' occupato dallo stesso file — la vista era
        # gia' stata costruita — non c'e' niente da numerare.
        radice_nome = destinazione.stem
        contatore = 2
        while destinazione.exists() and not destinazione.samefile(origine):
            destinazione = destinazione_dir / f"{radice_nome}-{contatore}{origine.suffix}"
            contatore += 1

        esito = _collega(origine, destinazione)
        esiti[esito] += 1
        voci.append({
            "asset_id": str(voce["asset_id"]),
            "tipo": voce["type"],
            "file": str(destinazione.relative_to(paths.project_root())).replace("\\", "/"),
        })

    log.info("[CreativeGallery] %d artefatti esposti (%s)", len(voci),
             ", ".join(f"{k}: {v}" for k, v in esiti.items() if v))
    return {"success": True, "artefatti": voci, "esiti": esiti}


def ensure_creative_dirs() -> List[Path]:
    """Crea le cartelle del Creative, cosi' esistono anche prima del primo lavoro."""
    create = []
    for kind in paths.CREATIVE_KINDS:
        create.append(paths.ensure(paths.creative_output_dir(kind)))
    return create

# ==============================================================================
# core/module_links.py — Lavorare su un modulo dove il modulo vive davvero
#
# Installare un modulo significa copiarlo: da <repo>/modules/<id>/backend a
# core/modules/<id>/, e da .../frontend a sigma_studio/src/modules/<id>/. Per
# chi usa Sigma Studio e' giusto cosi'. Per chi lo sviluppa e' una trappola: le
# modifiche fatte dentro Sigma Studio restano nella copia, il repository dei
# moduli non le vede, e la prima reinstallazione dal marketplace le cancella.
# E' gia' successo — la correzione dei percorsi del Training Lab e' stata
# scritta nella copia installata e ha dovuto essere riportata a mano nel
# sorgente prima che sopravvivesse a un aggiornamento.
#
# In modalita' sviluppo la copia diventa un collegamento: junction su Windows
# (non serve essere amministratore), symlink altrove. Il file aperto
# nell'editor di Sigma Studio *e'* il file del repository dei moduli, quindi
# `git status` in quel repository lo vede, e si committa nel posto giusto senza
# ricopiare niente.
#
# Il registro dei collegamenti sta in var/: e' stato di runtime di questa
# installazione, non configurazione da versionare.
# ==============================================================================
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional

from core import paths
from core.logger import get_logger

log = get_logger(__name__)

_LOCK = threading.Lock()


def links_file() -> Path:
    return paths.var_dir() / "module_links.json"


# ==============================================================================
# REGISTRO
# ==============================================================================

def _leggi() -> Dict[str, Dict[str, Any]]:
    percorso = links_file()
    if not percorso.exists():
        return {}
    try:
        dati = json.loads(percorso.read_text(encoding="utf-8"))
        return dati if isinstance(dati, dict) else {}
    except (OSError, ValueError) as exc:
        log.warning("[ModuleLinks] Registro illeggibile: %s", exc)
        return {}


def _scrivi(registro: Dict[str, Dict[str, Any]]) -> None:
    percorso = links_file()
    paths.ensure(percorso.parent)
    percorso.write_text(json.dumps(registro, indent=2, ensure_ascii=False) + "\n",
                        encoding="utf-8")


def list_links() -> Dict[str, Dict[str, Any]]:
    """I moduli collegati, con il repository da cui arrivano."""
    with _LOCK:
        return dict(_leggi())


def link_source(module_id: str) -> Optional[Path]:
    """La cartella sorgente di un modulo collegato, se lo e'."""
    voce = list_links().get(module_id)
    if not voce:
        return None
    sorgente = Path(voce["source"])
    return sorgente if sorgente.is_dir() else None


def is_linked(module_id: str) -> bool:
    return link_source(module_id) is not None


# ==============================================================================
# COLLEGAMENTI SUL FILESYSTEM
# ==============================================================================

def _e_collegamento(percorso: Path) -> bool:
    """Vero per un symlink e per una junction NTFS.

    `is_symlink()` da solo non basta: una junction non e' un symlink, e su
    Windows e' proprio quella che si riesce a creare senza privilegi.
    """
    if percorso.is_symlink():
        return True
    try:
        return bool(percorso.stat().st_reparse_tag)          # type: ignore[attr-defined]
    except (OSError, AttributeError):
        return False


def _crea_collegamento(sorgente: Path, destinazione: Path) -> str:
    """Collega destinazione -> sorgente. Restituisce la tecnica usata."""
    destinazione.parent.mkdir(parents=True, exist_ok=True)

    try:
        os.symlink(sorgente, destinazione, target_is_directory=True)
        return "symlink"
    except (OSError, NotImplementedError, AttributeError):
        pass

    if sys.platform == "win32":
        # La junction non richiede privilegi di amministratore, a differenza
        # del symlink di directory: e' la ragione per cui esiste questo ramo.
        esito = subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(destinazione), str(sorgente)],
            capture_output=True, text=True,
        )
        if esito.returncode == 0:
            return "junction"
        raise OSError(f"mklink /J fallito: {esito.stderr.strip() or esito.stdout.strip()}")

    raise OSError("Nessun modo di creare un collegamento su questa piattaforma")


def _rimuovi(percorso: Path) -> None:
    """Toglie di mezzo un percorso, collegamento o cartella vera che sia.

    L'ordine conta: un rmtree su una junction cancellerebbe il *contenuto del
    sorgente*, cioe' il repository dei moduli. Si prova sempre prima a staccare
    il collegamento.
    """
    if not percorso.exists() and not percorso.is_symlink():
        return

    if _e_collegamento(percorso):
        try:
            percorso.rmdir()            # stacca junction e symlink di directory
            return
        except OSError:
            percorso.unlink(missing_ok=True)
            return

    if percorso.is_dir():
        shutil.rmtree(percorso)
    else:
        percorso.unlink(missing_ok=True)


# ==============================================================================
# API
# ==============================================================================

def _cartella_backup(module_id: str) -> Path:
    """Dove finisce la copia installata quando un modulo viene collegato.

    Fuori da core/modules/, e non e' un dettaglio: la prima versione la
    lasciava li' accanto come "<id>.copia-installata", e quella cartella —
    con dentro il suo manifest.json — veniva letta come se fosse un modulo
    vero, mascherando quello collegato con la copia congelata.
    """
    return paths.var_dir() / "module_backups" / module_id


def link_module(module_id: str, source_dir: str | Path,
                backup: bool = True) -> Dict[str, Any]:
    """Sostituisce la copia installata di un modulo con un collegamento al sorgente.

    `source_dir` e' la cartella del modulo nel repository (quella che contiene
    backend/ e frontend/), non la sottocartella backend.
    """
    sorgente = Path(source_dir).expanduser().resolve()
    if not sorgente.is_dir():
        return {"success": False, "error": f"Sorgente inesistente: {sorgente}"}

    backend_src = sorgente / "backend"
    frontend_src = sorgente / "frontend"
    if not backend_src.is_dir():
        # Un modulo senza sottocartella backend tiene il codice nella radice.
        backend_src = sorgente

    backend_dst = paths.modules_backend_dir() / module_id
    frontend_dst = paths.frontend_modules_dir() / module_id

    creati = {}
    try:
        for etichetta, src, dst in (("backend", backend_src, backend_dst),
                                    ("frontend", frontend_src, frontend_dst)):
            if not src.is_dir():
                continue
            if backup and dst.exists() and not _e_collegamento(dst):
                salvataggio = _cartella_backup(module_id) / etichetta
                _rimuovi(salvataggio)
                salvataggio.parent.mkdir(parents=True, exist_ok=True)
                dst.rename(salvataggio)
                log.info("[ModuleLinks] Copia installata conservata in %s", salvataggio)
            else:
                _rimuovi(dst)
            creati[etichetta] = _crea_collegamento(src, dst)
    except OSError as exc:
        return {"success": False, "error": str(exc), "creati": creati}

    with _LOCK:
        registro = _leggi()
        registro[module_id] = {
            "source": str(sorgente),
            "backend": str(backend_src),
            "tecnica": creati.get("backend") or creati.get("frontend", ""),
        }
        _scrivi(registro)

    log.info("[ModuleLinks] '%s' collegato a %s (%s)", module_id, sorgente,
             ", ".join(f"{k}: {v}" for k, v in creati.items()))
    return {"success": True, "module_id": module_id, "source": str(sorgente),
            "collegamenti": creati}


def unlink_module(module_id: str, restore: bool = True) -> Dict[str, Any]:
    """Stacca il collegamento e, se c'e', rimette la copia messa da parte."""
    backend_dst = paths.modules_backend_dir() / module_id
    frontend_dst = paths.frontend_modules_dir() / module_id

    for etichetta, dst in (("backend", backend_dst), ("frontend", frontend_dst)):
        if _e_collegamento(dst):
            _rimuovi(dst)
        salvataggio = _cartella_backup(module_id) / etichetta
        if restore and salvataggio.exists() and not dst.exists():
            dst.parent.mkdir(parents=True, exist_ok=True)
            salvataggio.rename(dst)

    with _LOCK:
        registro = _leggi()
        registro.pop(module_id, None)
        _scrivi(registro)

    log.info("[ModuleLinks] '%s' scollegato.", module_id)
    return {"success": True, "module_id": module_id}


def module_manifest_path(module_id: str) -> Optional[Path]:
    """Dove sta il manifest di un modulo, collegato o installato che sia.

    In una installazione normale il manifest viene copiato accanto al codice.
    In un modulo collegato il codice e' backend/, e il manifest sta un livello
    sopra, nella radice del modulo nel repository: chi cerca il manifest deve
    saperlo, o un modulo in sviluppo risulterebbe privo di dichiarazioni.
    """
    installato = paths.modules_backend_dir() / module_id / "manifest.json"
    if installato.is_file():
        return installato

    sorgente = link_source(module_id)
    if sorgente is not None:
        candidato = sorgente / "manifest.json"
        if candidato.is_file():
            return candidato
    return None


def repositories() -> List[Dict[str, str]]:
    """I repository git coinvolti in questa installazione.

    Sigma Studio piu' i repository dei moduli collegati, ognuno una volta sola:
    piu' moduli dello stesso repository condividono la stessa radice git.
    """
    trovati: Dict[str, Dict[str, str]] = {}

    radice_studio = paths.project_root()
    trovati[str(radice_studio)] = {"path": str(radice_studio), "nome": radice_studio.name,
                                   "ruolo": "Sigma Studio"}

    for module_id, voce in list_links().items():
        radice = _radice_git(Path(voce["source"]))
        if radice is None:
            continue
        chiave = str(radice)
        if chiave in trovati:
            trovati[chiave]["moduli"] = trovati[chiave].get("moduli", "") + f", {module_id}"
        else:
            trovati[chiave] = {"path": chiave, "nome": radice.name,
                               "ruolo": "moduli", "moduli": module_id}
    return list(trovati.values())


def _radice_git(percorso: Path) -> Optional[Path]:
    for candidato in (percorso, *percorso.parents):
        if (candidato / ".git").exists():
            return candidato
    return None

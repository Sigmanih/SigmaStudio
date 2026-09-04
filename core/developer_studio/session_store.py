# ==============================================================================
# core/developer_studio/session_store.py — Persistenza delle sessioni di lavoro
# Sigma Studio v8 — Developer Studio AI-Native IDE
# ==============================================================================
"""Lo stato di lavoro dell'agente, che sopravvive alla richiesta HTTP.

Il ledger nasceva e moriva dentro `stream_admin_agent_turn`: un refresh del
browser, un riavvio del server o una connessione caduta e l'agente ricominciava
da zero — rileggendo file che aveva gia' letto, rieseguendo verifiche gia'
passate. Qui quello stato viene messo su disco, indicizzato per sessione.

**Cosa viene salvato e cosa no.** Il transcritto della conversazione vive nel
client, che lo rimanda a ogni richiesta: duplicarlo qui significherebbe tenere
due verita' e doverle riconciliare. Sul server resta cio' che solo il server
sa: quali file sono stati letti e fin dove, quali comandi sono stati eseguiti
e con che esito, quali verifiche hanno retto, il piano e le metriche del run.

Il formato e' un JSON per sessione sotto `var/dev_sessions/`, scritto in modo
atomico (file temporaneo piu' `os.replace`) perche' il salvataggio avviene
mentre l'agente sta ancora lavorando e una scrittura interrotta a meta'
lascerebbe una sessione illeggibile invece di una vecchia.
"""

import json
import os
import re
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.logger import get_logger
from core.paths import dev_sessions_dir
from core.developer_studio.session_ledger import DevSessionLedger

log = get_logger("dev_session_store")

#: Intervallo minimo fra due salvataggi della stessa sessione durante un run.
#: Il ledger cambia a ogni tool; scriverlo ogni volta trasformerebbe un run
#: lungo in centinaia di scritture su disco per un dato che serve solo se il
#: run si interrompe.
SAVE_INTERVAL_S = 3.0

#: Oltre questo numero di sessioni le piu' vecchie vengono rimosse. Lo stato
#: di runtime non e' un archivio: se serve conservarlo, si esporta.
MAX_SESSIONS = 200

#: Un identificativo di sessione finisce in un nome di file: tutto cio' che
#: non e' evidentemente innocuo viene sostituito, cosi' che nessun id possa
#: portare la scrittura fuori dalla cartella.
_ID_SAFE = re.compile(r"[^A-Za-z0-9_.\-]")

_lock = threading.RLock()
#: session_id -> istante dell'ultimo salvataggio, per la limitazione di ritmo.
_last_save: Dict[str, float] = {}


def _safe_id(session_id: str) -> str:
    pulito = _ID_SAFE.sub("_", str(session_id or "").strip())[:120]
    return pulito or "senza_nome"


def _path_for(session_id: str) -> Path:
    return dev_sessions_dir() / f"{_safe_id(session_id)}.json"


def _ensure_dir() -> Optional[Path]:
    try:
        d = dev_sessions_dir()
        d.mkdir(parents=True, exist_ok=True)
        return d
    except OSError as exc:
        log.warning("[DevSessions] cartella non disponibile: %s", exc)
        return None


# ---------------------------------------------------------------------------
# Scrittura
# ---------------------------------------------------------------------------

def save(
    session_id: str,
    ledger: DevSessionLedger,
    *,
    model: str = "",
    status: str = "running",
    metrics: Optional[Dict[str, Any]] = None,
    pipeline: Optional[List[Dict[str, Any]]] = None,
    force: bool = False,
) -> bool:
    """Scrive lo stato della sessione. Ritorna True se ha scritto davvero.

    Il salvataggio e' opportunistico: se fallisce, il run continua. Perdere la
    possibilita' di riprendere una sessione e' spiacevole, interrompere il
    lavoro in corso per un errore di disco lo e' molto di piu'.
    """
    if not session_id:
        return False

    ora = time.time()
    with _lock:
        if not force and ora - _last_save.get(session_id, 0.0) < SAVE_INTERVAL_S:
            return False
        _last_save[session_id] = ora

    if _ensure_dir() is None:
        return False

    documento = {
        "session_id": session_id,
        "updated_at": ora,
        "status": status,
        "model": model,
        "goal": ledger.goal,
        "workspace_root": ledger.workspace_root,
        "metrics": metrics or {},
        "pipeline": list(pipeline or ledger.serialize().get("pipeline") or []),
        "ledger": ledger.serialize(),
    }

    destinazione = _path_for(session_id)
    temporaneo = destinazione.with_suffix(".json.tmp")
    try:
        temporaneo.write_text(
            json.dumps(documento, ensure_ascii=False, indent=1, default=str),
            encoding="utf-8",
        )
        os.replace(temporaneo, destinazione)
        return True
    except (OSError, TypeError, ValueError) as exc:
        log.warning("[DevSessions] salvataggio di '%s' fallito: %s", session_id, exc)
        try:
            temporaneo.unlink(missing_ok=True)
        except OSError:
            pass
        return False


def mark_finished(
    session_id: str,
    ledger: DevSessionLedger,
    *,
    model: str = "",
    status: str = "done",
    metrics: Optional[Dict[str, Any]] = None,
) -> bool:
    """Chiude la sessione con un salvataggio non differibile."""
    scritto = save(
        session_id, ledger, model=model, status=status,
        metrics=metrics, force=True,
    )
    prune()
    return scritto


# ---------------------------------------------------------------------------
# Lettura
# ---------------------------------------------------------------------------

def load(session_id: str) -> Optional[Dict[str, Any]]:
    """Il documento salvato per questa sessione, o None se non esiste."""
    if not session_id:
        return None
    percorso = _path_for(session_id)
    if not percorso.is_file():
        return None
    try:
        return json.loads(percorso.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        log.warning("[DevSessions] '%s' illeggibile: %s", session_id, exc)
        return None


def load_ledger(
    session_id: str,
    goal: str,
    workspace_root: Optional[str],
) -> Optional[DevSessionLedger]:
    """Il ledger di una sessione precedente, se e' ancora quello giusto.

    Due controlli decidono se riprendere. Il workspace deve coincidere: uno
    stato che parla di file di un altro progetto e' peggio di nessuno stato,
    perche' l'agente ci crede. L'obiettivo invece puo' cambiare — l'utente fa
    una domanda di seguito all'altra nella stessa sessione — e in quel caso lo
    stato viene ripreso e l'obiettivo aggiornato: i file gia' letti restano
    validi, ed e' esattamente il risparmio che questa persistenza esiste per
    ottenere.
    """
    documento = load(session_id)
    if not documento:
        return None

    stato = documento.get("ledger") or {}
    if not stato:
        return None

    atteso = str(workspace_root or "").replace("\\", "/").rstrip("/")
    salvato = str(stato.get("workspace_root") or "").replace("\\", "/").rstrip("/")
    if atteso and salvato and atteso.lower() != salvato.lower():
        log.info(
            "[DevSessions] '%s' ignorata: workspace diverso (%s != %s)",
            session_id, salvato, atteso,
        )
        return None

    try:
        ledger = DevSessionLedger.restore(stato)
    except Exception as exc:  # uno stato corrotto non deve impedire il run
        log.warning("[DevSessions] ripristino di '%s' fallito: %s", session_id, exc)
        return None

    if goal and goal != ledger.goal:
        ledger.set_goal(goal)
    log.info(
        "[DevSessions] '%s' ripresa: %d file noti, %d comandi",
        session_id, len(ledger.read_files), len(ledger.successful_commands()),
    )
    return ledger


def list_sessions(limit: int = 50) -> List[Dict[str, Any]]:
    """Le sessioni salvate, dalla piu' recente, senza il ledger completo."""
    cartella = dev_sessions_dir()
    if not cartella.is_dir():
        return []
    voci: List[Dict[str, Any]] = []
    for percorso in cartella.glob("*.json"):
        try:
            documento = json.loads(percorso.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        ledger = documento.get("ledger") or {}
        voci.append({
            "session_id": documento.get("session_id") or percorso.stem,
            "goal": documento.get("goal") or "",
            "status": documento.get("status") or "unknown",
            "model": documento.get("model") or "",
            "workspace_root": documento.get("workspace_root") or "",
            "updated_at": documento.get("updated_at") or 0,
            "files_touched": len(ledger.get("files") or []),
            "commands_run": len(ledger.get("commands") or []),
            "metrics": documento.get("metrics") or {},
        })
    voci.sort(key=lambda v: v.get("updated_at") or 0, reverse=True)
    return voci[: max(1, int(limit))]


def delete(session_id: str) -> bool:
    """Rimuove una sessione salvata."""
    percorso = _path_for(session_id)
    try:
        percorso.unlink(missing_ok=True)
    except OSError as exc:
        log.warning("[DevSessions] '%s' non rimovibile: %s", session_id, exc)
        return False
    with _lock:
        _last_save.pop(session_id, None)
    return True


def rollback_session_files(
    session_id: str,
    workspace_root: Optional[str] = None,
) -> Dict[str, Any]:
    """Ripristina tutti i file modificati durante la sessione allo stato antecedente.

    Legge l'elenco dei file modificati nel ledger della sessione ed esegue il
    restore_file_backup per ciascuno di essi.
    """
    doc = load(session_id)
    if not doc:
        return {"success": False, "error": f"Sessione '{session_id}' non trovata."}

    ledger_data = doc.get("ledger") or {}
    files_map = ledger_data.get("files") or {}
    root = workspace_root or doc.get("workspace_root") or None

    from core.developer_studio.fs_manager import restore_file_backup
    restored = []
    failed = []

    for rel_path, f_info in files_map.items():
        if f_info.get("edits") or f_info.get("writes"):
            res = restore_file_backup(rel_path, root=root)
            if res.get("success"):
                restored.append(rel_path)
            else:
                failed.append({"path": rel_path, "error": res.get("error")})

    # Aggiorna lo stato della sessione
    doc["status"] = "rolled_back"
    doc["rolled_back_at"] = time.time()
    dest = _path_for(session_id)
    try:
        dest.write_text(json.dumps(doc, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    except Exception:
        pass

    return {
        "success": len(failed) == 0,
        "session_id": session_id,
        "restored_files": restored,
        "failed_files": failed,
        "message": f"Ripristinati {len(restored)} file su {len(restored) + len(failed)} modificati."
    }


def prune(keep: int = MAX_SESSIONS) -> int:
    """Elimina le sessioni piu' vecchie oltre `keep`. Ritorna quante ne ha tolte."""
    cartella = dev_sessions_dir()
    if not cartella.is_dir():
        return 0
    try:
        file_json = sorted(
            cartella.glob("*.json"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
    except OSError:
        return 0
    rimossi = 0
    for percorso in file_json[max(0, int(keep)):]:
        try:
            percorso.unlink()
            rimossi += 1
        except OSError:
            continue
    if rimossi:
        log.info("[DevSessions] %d sessioni vecchie rimosse", rimossi)
    return rimossi



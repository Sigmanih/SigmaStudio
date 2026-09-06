# ==============================================================================
# core/chat/ledger.py — Ledger e cancello di controllo per la Chat
# Sigma Studio v8 — Modular Chat Sub-package
# ==============================================================================
"""Ledger e cancello di mutazione per le sessioni conversazionali di chat.

Finora la chat ordinaria non aveva alcun controllo sui file toccati ne' un
cancello di completamento. A una domanda complessa o a una richiesta informativa
sul codice, l'estrattore automatico scambiava le risposte conversazionali per
file da salvare, spargendo documenti Markdown indesiderati sotto `data/`.

Questo modulo introduce:
1. Il **Cancello di Mutazione della Chat**: una conversazione e' per sua natura
   informativa e non deve modificare il filesystem a meno che l'utente non abbia
   formulato una richiesta esplicita e positiva di creazione o salvataggio file.
2. Il **ChatLedger**: tiene traccia per ogni sessione di tutti i file letti dal
   contesto e di tutti i file effettivamente scritti con il loro diff e backup_id.
"""

import re
import threading
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from core.logger import get_logger

log = get_logger("chat_ledger")


# ---------------------------------------------------------------------------
# Cancello di autorizzazione scritture per la chat
# ---------------------------------------------------------------------------

_CONVERSATIONAL_PREFIXES = (
    "parlami", "spiegami", "raccontami", "dimmi", "mostrami", "elenca",
    "descrivi", "analizza", "riassumi", "illustrami", "introduci", "chi sei",
    "cosa sei", "come ti chiami", "cosa puoi fare", "cosa sai fare",
    "quali sono", "che cosa sono", "cosa fa", "come funziona", "come posso",
    "come si", "perche", "perché", "ciao", "buongiorno", "buonasera", "salve",
    "hey", "ehi", "help", "aiuto",
)

_EXPLICIT_SAVE_PATTERNS = [
    re.compile(r'\b(?:salva(?:lo|li|la)?|salvare)\s+(?:su|in|come|nel)\s+(?:un|uno|una|il|lo|la|i|gli|le)?\s*(?:file|disco|data/|\./data/)', re.IGNORECASE),
    re.compile(r'\b(?:crea(?:mi)?|generami?|scrivimi?|esporta(?:mi)?)\s+(?:un|uno|una|il|lo|la|l[\'\"]|i|gli|le)?\s*(?:nuovo\s+)?(?:file|documento|script|scheda|argomento|topic|modulo)\b', re.IGNORECASE),
    re.compile(r'\b(?:create_file|write_file|save_to_file)\b', re.IGNORECASE),
    re.compile(r'\b(?:salva\s+la\s+risposta\s+in\s+un\s+file)\b', re.IGNORECASE),
]


def is_mutation_permitted(prompt: str, force_save: bool = False) -> Tuple[bool, str]:
    """Decide se la richiesta dell'utente autorizza la creazione o modifica di file.

    Ritorna una tupla (permesso: bool, motivazione: str).
    """
    if force_save:
        return True, "Salvataggio forzato esplicitamente dal chiamante"

    text = (prompt or "").strip()
    if not text:
        return False, "Richiesta vuota: nessuna mutazione consentita"

    lower = text.lower()

    # 1. Controlla se la richiesta e' prima di tutto una domanda informativa
    for pref in _CONVERSATIONAL_PREFIXES:
        if lower.startswith(pref) or f" {pref} " in f" {lower} ":
            # Eccezione: l'utente ha esplicitamente chiesto di salvare la risposta
            has_explicit_save = any(p.search(text) for p in _EXPLICIT_SAVE_PATTERNS)
            if not has_explicit_save:
                return False, f"Richiesta informativa/conversazionale ('{pref}'): creazione file non autorizzata"

    # 2. Verifica se c'e' un comando esplicito di salvataggio/creazione file
    for pat in _EXPLICIT_SAVE_PATTERNS:
        if pat.search(text):
            return True, "Richiesta esplicita di creazione o salvataggio file su disco"

    # 3. Slug sintetici di argomenti passati programmaticamente (es. "test_ai_topic", "01_limiti")
    if re.match(r'^[a-zA-Z0-9_\-]+$', text) and any(w in lower for w in ('topic', 'modulo', 'test_', 'argomento')):
        return True, "Identificatore sintetico di argomento/modulo"

    return False, "Nessuna richiesta esplicita di creazione file rilevata nel prompt"


# ---------------------------------------------------------------------------
# Ledger di sessione della Chat
# ---------------------------------------------------------------------------


@dataclass
class ChatFileRecord:
    path: str
    action: str  # "create_file", "edit_file", "read"
    backup_id: Optional[str] = None
    diff: Optional[str] = None
    timestamp: float = field(default_factory=time.time)


class ChatLedger:
    """Traccia in modo duraturo l'attivita' sui file di una sessione di chat."""

    def __init__(self, session_id: str):
        self.session_id = str(session_id or "").strip()
        self.started_at = time.time()
        self._lock = threading.RLock()
        self._reads: List[str] = []
        self._writes: List[ChatFileRecord] = []
        self._rejected_attempts: List[Dict[str, Any]] = []

    def record_read(self, path: str) -> None:
        with self._lock:
            p = str(path or "").replace("\\", "/")
            if p and p not in self._reads:
                self._reads.append(p)

    def record_write(self, path: str, action: str, backup_id: Optional[str] = None, diff: Optional[str] = None) -> None:
        with self._lock:
            rec = ChatFileRecord(
                path=str(path or "").replace("\\", "/"),
                action=action,
                backup_id=backup_id,
                diff=diff,
            )
            self._writes.append(rec)
            log.info("[ChatLedger] Registrata scrittura su '%s' (backup: %s)", rec.path, backup_id)

    def record_rejection(self, reason: str, candidate_path: str = "") -> None:
        with self._lock:
            self._rejected_attempts.append({
                "reason": reason,
                "candidate": candidate_path,
                "at": time.time(),
            })

    @property
    def written_files(self) -> List[str]:
        with self._lock:
            return [w.path for w in self._writes]

    @property
    def read_files(self) -> List[str]:
        with self._lock:
            return list(self._reads)

    def snapshot(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "session_id": self.session_id,
                "started_at": self.started_at,
                "reads_count": len(self._reads),
                "writes_count": len(self._writes),
                "read_files": list(self._reads),
                "written_files": [asdict(w) for w in self._writes],
                "rejected_attempts_count": len(self._rejected_attempts),
                "rejected_attempts": list(self._rejected_attempts),
            }


# Registro globale dei ledger di chat
_chat_ledgers: Dict[str, ChatLedger] = {}
_chat_lock = threading.RLock()


def get_chat_ledger(session_id: str) -> ChatLedger:
    """Ottiene o crea il ledger per la sessione di chat indicata."""
    sid = str(session_id or "default").strip()
    with _chat_lock:
        if sid not in _chat_ledgers:
            _chat_ledgers[sid] = ChatLedger(sid)
        return _chat_ledgers[sid]


def release_chat_ledger(session_id: str) -> Optional[Dict[str, Any]]:
    """Chiude e restituisce il riepilogo del ledger della sessione."""
    sid = str(session_id or "default").strip()
    with _chat_lock:
        ledger = _chat_ledgers.pop(sid, None)
        return ledger.snapshot() if ledger else None

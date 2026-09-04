# ==============================================================================
# core/developer_studio/project_rules.py — Istruzioni di progetto per l'agente
# Sigma Studio v8 — Developer Studio AI-Native IDE
# ==============================================================================
"""Le convenzioni del progetto su cui l'agente sta lavorando, lette dal disco.

Un harness che porta con se' le regole di un solo progetto non e' un harness:
e' quel progetto. Le convenzioni architetturali — quali librerie sono ammesse,
dove vivono gli stili, in che lingua rispondere, come si eseguono i test —
appartengono al workspace, non al codice Python dell'agente, e questo modulo
e' il punto in cui vengono raccolte.

Sono cercate nella radice del workspace, in ordine di precedenza:

    AGENTS.md          convenzione condivisa fra harness diversi
    .sigma/rules.md    forma nativa di Sigma Studio
    CLAUDE.md          compatibilita' con progetti gia' istruiti per Claude Code

Tutti i file trovati vengono uniti, ciascuno sotto il proprio titolo, perche'
un repository puo' legittimamente averne piu' di uno e scartarne uno in
silenzio e' peggio che leggerli entrambi.

Il testo entra nel system prompt, che per la prefix cache deve restare
immutabile per l'intero run: la lettura e' quindi memorizzata e rifatta solo
quando cambia la firma (percorso, dimensione, mtime) di uno dei file.
"""

import os
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from core.logger import get_logger

log = get_logger("project_rules")

#: Percorsi relativi alla radice del workspace, in ordine di precedenza.
RULE_FILES: Tuple[str, ...] = (
    "AGENTS.md",
    ".sigma/rules.md",
    "CLAUDE.md",
)

#: Tetto per singolo file. Oltre questa soglia il file non e' piu' un insieme
#: di convenzioni ma documentazione, e la documentazione si legge con
#: `read_file` quando serve, non a ogni turno dentro il prompt.
MAX_CHARS_PER_FILE = 8_000

#: Tetto complessivo, con lo stesso ragionamento applicato alla somma.
MAX_CHARS_TOTAL = 16_000

_HEADER = (
    "## ISTRUZIONI DI QUESTO PROGETTO\n"
    "Le regole che seguono arrivano dal workspace su cui stai lavorando e "
    "prevalgono sulle abitudini generali. Rispettale alla lettera."
)

_lock = threading.RLock()
#: radice normalizzata -> (firma dei file, sezione gia' formattata)
_cache: Dict[str, Tuple[Tuple[Any, ...], str]] = {}


def _normalise_root(workspace_root: Optional[str]) -> str:
    if not workspace_root:
        return ""
    return str(workspace_root).replace("\\", "/").rstrip("/")


def _signature(root: str) -> Tuple[Any, ...]:
    """Firma dei file di regole: cambia se uno di essi cambia, appare o sparisce."""
    firma: List[Any] = []
    for rel in RULE_FILES:
        p = Path(root) / rel
        try:
            st = p.stat()
            firma.append((rel, int(st.st_mtime_ns), st.st_size))
        except OSError:
            firma.append((rel, None, None))
    return tuple(firma)


def _read_one(path: Path) -> str:
    try:
        testo = path.read_text(encoding="utf-8", errors="replace").strip()
    except OSError as exc:
        log.debug("[ProjectRules] %s non leggibile: %s", path, exc)
        return ""
    if len(testo) > MAX_CHARS_PER_FILE:
        testo = (
            testo[:MAX_CHARS_PER_FILE]
            + f"\n\n[...troncato a {MAX_CHARS_PER_FILE} caratteri. "
            "Il resto del file si legge con read_file quando serve.]"
        )
    return testo


def discover(workspace_root: Optional[str]) -> List[Dict[str, Any]]:
    """I file di regole presenti nella radice, con percorso e dimensione.

    Serve alla UI e alla diagnostica: dice all'utente quali istruzioni
    l'agente sta effettivamente applicando, che e' l'unico modo di accorgersi
    che il file esiste ma sta nella cartella sbagliata.
    """
    root = _normalise_root(workspace_root)
    if not root or not os.path.isdir(root):
        return []
    trovati: List[Dict[str, Any]] = []
    for rel in RULE_FILES:
        p = Path(root) / rel
        if not p.is_file():
            continue
        try:
            dimensione = p.stat().st_size
        except OSError:
            dimensione = 0
        trovati.append({
            "rel": rel,
            "path": str(p).replace("\\", "/"),
            "bytes": dimensione,
            "truncated": dimensione > MAX_CHARS_PER_FILE,
        })
    return trovati


def load_section(workspace_root: Optional[str]) -> str:
    """La sezione di prompt con le regole del progetto, o stringa vuota.

    Vuota e' un esito legittimo e frequente: un workspace senza file di regole
    va guidato dalle sole istruzioni generali dell'agente, non da quelle di un
    altro progetto.
    """
    root = _normalise_root(workspace_root)
    if not root or not os.path.isdir(root):
        return ""

    firma = _signature(root)
    with _lock:
        memorizzato = _cache.get(root)
        if memorizzato and memorizzato[0] == firma:
            return memorizzato[1]

    pezzi: List[str] = []
    consumati = 0
    for rel in RULE_FILES:
        p = Path(root) / rel
        if not p.is_file():
            continue
        testo = _read_one(p)
        if not testo:
            continue
        if consumati + len(testo) > MAX_CHARS_TOTAL:
            rimasto = max(MAX_CHARS_TOTAL - consumati, 0)
            if rimasto < 400:
                log.info(
                    "[ProjectRules] %s omesso: budget del prompt esaurito", rel
                )
                break
            testo = testo[:rimasto] + "\n[...troncato: budget del prompt esaurito.]"
        pezzi.append(f"### Da `{rel}`\n{testo}")
        consumati += len(testo)

    sezione = ""
    if pezzi:
        sezione = _HEADER + "\n\n" + "\n\n".join(pezzi)
        log.info(
            "[ProjectRules] %d file di regole caricati da %s (%d caratteri)",
            len(pezzi), root, len(sezione),
        )

    with _lock:
        _cache[root] = (firma, sezione)
    return sezione


def invalidate(workspace_root: Optional[str] = None) -> None:
    """Dimentica la sezione memorizzata: tutta, o di una sola radice."""
    with _lock:
        if workspace_root is None:
            _cache.clear()
        else:
            _cache.pop(_normalise_root(workspace_root), None)

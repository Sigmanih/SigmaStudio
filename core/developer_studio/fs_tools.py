# ==============================================================================
# core/developer_studio/fs_tools.py — Paginated & Surgical Filesystem Primitives
# Sigma Studio v8 — Developer Studio AI-Native IDE
# ==============================================================================
"""Filesystem primitives sized for an *agent's* prompt window, not a human's screen.

`fs_manager` answers the editor's questions: give me the whole file, write it
back. Those are the wrong shape for a model. The agent loop can only ever feed a
bounded slice of a file into the prompt, so without an explicit window the slice
is silently the head of the file — the model never sees past the first screenful
and can neither reason about nor rewrite the rest. And rewriting a whole file
costs one output token per surviving line, so any file longer than the
generation budget becomes uneditable in practice.

These primitives fix both: an addressable read window that always reports what
it did *not* show, and an exact-substring edit that costs only the changed
region. `append_file_content` completes the set — adding to the end of a file
needs no anchor, and demanding one makes an agent invent the text it cannot
remember.
"""

import difflib
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.logger import get_logger
from core.developer_studio.fs_manager import (
    SEARCH_IGNORE_DIRS,
    SEARCH_IGNORE_EXTENSIONS,
    backup_file_snapshot,
    find_workspace_root_for_path,
    get_default_workspace_root,
    read_file_content,
)

log = get_logger("developer_fs_tools")

READ_DEFAULT_LIMIT = 800          # lines returned when the caller asks for none
READ_MAX_LIMIT = 5000             # hard ceiling for a single read request
READ_MAX_LINE_CHARS = 2000        # a single minified line must not eat the budget


def read_file_slice(
    file_path: str,
    offset: int = 1,
    limit: Optional[int] = None,
    max_line_chars: int = READ_MAX_LINE_CHARS,
) -> Dict[str, Any]:
    """Reads a window of a text file as numbered lines, `cat -n` style.

    `offset` is 1-based and inclusive; `limit` is clamped to READ_MAX_LIMIT.
    The result always reports `total_lines` and `has_more`, so the caller knows
    a further read is needed instead of assuming it saw the whole file.
    """
    base = read_file_content(file_path)
    if not base.get("success"):
        return base

    # Binary, image, model-weight and oversized files have no line semantics.
    content = base.get("content")
    if content is None:
        return {**base, "is_sliceable": False}

    lines = content.splitlines()
    total = len(lines)

    try:
        offset = max(1, int(offset))
    except (TypeError, ValueError):
        offset = 1
    try:
        limit = READ_DEFAULT_LIMIT if limit in (None, "") else int(limit)
    except (TypeError, ValueError):
        limit = READ_DEFAULT_LIMIT
    limit = max(1, min(limit, READ_MAX_LIMIT))

    start = offset - 1
    if total and start >= total:
        return {
            **base,
            "is_sliceable": True,
            "total_lines": total,
            "offset": offset,
            "limit": limit,
            "returned_lines": 0,
            "has_more": False,
            "content": "",
            "numbered": "",
            "message": (
                f"offset {offset} oltre la fine del file ({total} righe totali). "
                f"Usa un offset minore o uguale a {total}."
            ),
        }

    window = lines[start:start + limit]
    width = len(str(start + len(window))) or 1
    rendered = []
    for i, raw in enumerate(window, start=offset):
        if len(raw) > max_line_chars:
            raw = f"{raw[:max_line_chars]}  ... [riga troncata, {len(raw)} caratteri]"
        rendered.append(f"{str(i).rjust(width)}\t{raw}")

    end = start + len(window)
    return {
        **base,
        "is_sliceable": True,
        "total_lines": total,
        "offset": offset,
        "limit": limit,
        "returned_lines": len(window),
        "last_line": end,
        "has_more": end < total,
        "content": "\n".join(window),
        "numbered": "\n".join(rendered),
    }


def edit_file_content(
    file_path: str,
    old_string: str,
    new_string: str,
    replace_all: bool = False,
    root: Optional[str] = None,
) -> Dict[str, Any]:
    """Replaces an exact substring in a file — the surgical alternative to rewrite.

    Ambiguity is reported as an error rather than resolved by guessing: a
    non-unique `old_string` is rejected unless `replace_all` is set, because
    silently patching the wrong occurrence is far more expensive to discover
    than a rejected call the model can immediately retry with more context.
    """
    p = Path(file_path).resolve()
    if not p.exists():
        return {"success": False, "error": f"File non trovato: {file_path}"}
    if p.is_dir():
        return {"success": False, "error": f"Il percorso e una cartella: {file_path}"}
    if not old_string:
        return {"success": False, "error": "old_string e vuoto: specifica il testo esatto da sostituire."}
    if old_string == new_string:
        return {"success": False, "error": "old_string e new_string sono identici: nessuna modifica da applicare."}

    try:
        original = p.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        return {"success": False, "error": f"Impossibile leggere il file: {e}"}

    occurrences = original.count(old_string)
    if occurrences == 0:
        return {
            "success": False,
            "occurrences": 0,
            "error": (
                "old_string non trovato. Il testo deve corrispondere ESATTAMENTE, "
                "indentazione compresa. Rileggi la zona con read_file (offset/limit) "
                "e ricopia le righe SENZA il prefisso di numerazione."
            ),
        }
    if occurrences > 1 and not replace_all:
        return {
            "success": False,
            "occurrences": occurrences,
            "error": (
                f"old_string compare {occurrences} volte: la modifica sarebbe ambigua. "
                "Allarga old_string includendo righe di contesto circostanti, oppure "
                'passa "replace_all": true per sostituirle tutte.'
            ),
        }

    updated = (
        original.replace(old_string, new_string)
        if replace_all
        else original.replace(old_string, new_string, 1)
    )

    ws = Path(root).resolve() if root else find_workspace_root_for_path(p)
    backup_info = backup_file_snapshot(str(p), reason="before_edit", root=str(ws))

    try:
        p.write_text(updated, encoding="utf-8")
    except Exception as e:
        return {"success": False, "error": f"Errore scrittura file: {e}"}

    diff_text = "".join(difflib.unified_diff(
        original.splitlines(keepends=True),
        updated.splitlines(keepends=True),
        fromfile=f"a/{p.name}",
        tofile=f"b/{p.name}",
        n=3,
    ))

    applied = occurrences if replace_all else 1
    before, after = len(original.splitlines()), len(updated.splitlines())
    res: Dict[str, Any] = {
        "success": True,
        "path": str(p).replace("\\", "/"),
        "occurrences": occurrences,
        "replaced": applied,
        "lines_before": before,
        "lines_after": after,
        "diff": diff_text,
        "message": f"Modificato {p.name}: {applied} sostituzione/i, {before} -> {after} righe.",
    }
    if backup_info:
        res["backup_id"] = backup_info.get("backup_id")
    return res


def glob_workspace_files(
    root_path: Optional[str] = None,
    pattern: str = "**/*",
    limit: int = 300,
) -> Dict[str, Any]:
    """Lists workspace files matching a glob, newest first, heavy trees pruned.

    `list_dir` answers "what is in this folder"; this answers "where does this
    kind of file live", which is the question an agent actually asks when it
    starts work on an unfamiliar tree.
    """
    root = Path(root_path or get_default_workspace_root()).resolve()
    if not root.exists():
        return {"success": False, "error": f"Percorso non trovato: {root}", "files": []}

    pattern = (pattern or "**/*").strip()
    limit = max(1, min(int(limit or 300), 2000))

    matches: List[Dict[str, Any]] = []
    truncated = False
    try:
        for entry in root.glob(pattern):
            if len(matches) >= limit:
                truncated = True
                break
            try:
                if entry.is_dir():
                    continue
                # Prune the same heavy trees the content search prunes.
                if any(part in SEARCH_IGNORE_DIRS for part in entry.parts):
                    continue
                if entry.suffix.lower() in SEARCH_IGNORE_EXTENSIONS:
                    continue
                st = entry.stat()
                matches.append({
                    "path": str(entry).replace("\\", "/"),
                    "rel": str(entry.relative_to(root)).replace("\\", "/"),
                    "size": st.st_size,
                    "mtime": st.st_mtime,
                })
            except (OSError, ValueError):
                continue
    except (OSError, ValueError, NotImplementedError) as e:
        return {"success": False, "error": f"Pattern glob non valido: {e}", "files": []}

    matches.sort(key=lambda m: m["mtime"], reverse=True)
    return {
        "success": True,
        "root": str(root).replace("\\", "/"),
        "pattern": pattern,
        "count": len(matches),
        "truncated": truncated,
        "files": matches,
    }



def _normalizza(testo: str) -> str:
    """Il testo ridotto a cio' che conta per dire se e' lo stesso.

    Indentazione e righe vuote cambiano fra due generazioni dello stesso
    contenuto senza cambiarne il significato: confrontare i byte grezzi
    direbbe "diverso" a due copie che il file conterra' comunque due volte.
    """
    return "\n".join(riga.strip() for riga in testo.splitlines() if riga.strip())


def _gia_presente(originale: str, aggiunta: str) -> bool:
    """Se l'aggiunta e' gia' contenuta nel file, per intero."""
    normalizzata = _normalizza(aggiunta)
    if not normalizzata:
        return False
    return normalizzata in _normalizza(originale)



#: Sotto questa frazione del contenuto precedente, una riscrittura si comporta
#: come una cancellazione e va confermata. Il valore e' basso di proposito:
#: deve lasciar passare una semplificazione onesta e fermare uno svuotamento.
TRUNCATION_RATIO = 0.25
#: Sotto questa dimensione il file e' cosi' piccolo che qualunque riscrittura
#: e' plausibile, e la guardia darebbe solo fastidio.
TRUNCATION_MIN_CHARS = 200


def would_truncate(previous: str, new: str) -> bool:
    """Se la nuova versione riduce il file al punto da somigliare a una cancellazione."""
    prima = len((previous or "").strip())
    if prima < TRUNCATION_MIN_CHARS:
        return False
    return len((new or "").strip()) < prima * TRUNCATION_RATIO


def append_file_content(
    file_path: str,
    content: str,
    root: Optional[str] = None,
    ensure_newline: bool = True,
) -> Dict[str, Any]:
    """Aggiunge testo in fondo a un file, creandolo se non esiste.

    Esiste perche' `edit_file` chiede un'ancora e aggiungere in coda non ne ha
    una: costringere ad averla obbliga chi scrive a citare cio' che gia' c'e',
    e un agente che non lo ricorda lo inventa. Qui la posizione e' implicita e
    non c'e' nulla da indovinare.

    `ensure_newline` inserisce un a capo se il file non finiva con uno: due
    definizioni incollate sulla stessa riga sono un errore di sintassi che si
    scopre solo all'import successivo.
    """
    p = Path(file_path).resolve()
    if p.exists() and p.is_dir():
        return {"success": False, "error": f"Il percorso e una cartella: {file_path}"}
    if not content:
        return {"success": False, "error": "Nessun contenuto da aggiungere."}

    esisteva = p.exists()
    originale = ""
    backup_info = None
    ws = Path(root).resolve() if root else find_workspace_root_for_path(p)

    if esisteva:
        try:
            originale = p.read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            return {"success": False, "error": f"Impossibile leggere il file: {e}"}
        backup_info = backup_file_snapshot(str(p), reason="before_append", root=str(ws))

    # Aggiungere due volte la stessa cosa non e' un'aggiunta: e' una
    # duplicazione. Un agente che riaccoda dopo un test fallito sta cercando di
    # correggere, non di estendere, e va rimandato allo strumento giusto.
    if _gia_presente(originale, content):
        return {
            "success": False,
            "path": str(p).replace("\\", "/"),
            "error": (
                "Questo contenuto e gia presente nel file: aggiungerlo di nuovo "
                "lo duplicherebbe. Se devi CORREGGERE quanto hai gia scritto usa "
                "edit_file sul frammento da cambiare; se devi aggiungere altro, "
                "passa solo la parte nuova."
            ),
        }

    separatore = ""
    if ensure_newline and originale and not originale.endswith("\n"):
        separatore = "\n"

    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(originale + separatore + content, encoding="utf-8")
    except Exception as e:
        return {"success": False, "error": f"Errore scrittura file: {e}"}

    prima = len(originale.splitlines())
    dopo = len((originale + separatore + content).splitlines())
    res: Dict[str, Any] = {
        "success": True,
        "path": str(p).replace("\\", "/"),
        "created": not esisteva,
        "lines_before": prima,
        "lines_after": dopo,
        "lines_added": dopo - prima,
        "message": (
            f"{'Creato' if not esisteva else 'Esteso'} {p.name}: "
            f"+{dopo - prima} righe ({prima} -> {dopo})."
        ),
    }
    if backup_info:
        res["backup_id"] = backup_info.get("backup_id")
    return res

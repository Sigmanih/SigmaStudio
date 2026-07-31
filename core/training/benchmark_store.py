# ==============================================================================
# core/training/benchmark_store.py — Persistenza dei risultati di benchmark
# Sigma Studio v7 — Training Lab Sub-package
# ==============================================================================
"""Archivio su disco per gli esiti dei singoli quesiti di un run di benchmark.

I risultati stavano dentro l'indice dei job: ogni quesito completato riscriveva
l'intero file, quindi un run integrale (oltre 200.000 item) ricopiava un JSON che
cresceva a ogni passo, e la lista job restituiva alla UI megabyte di dettaglio a
ogni polling.

Qui il dettaglio vive per job in tre pezzi:

* ``<job>.jsonl``     — un esito per riga, scritto in append
* ``<job>.idx.json``  — offset in byte + verdetto + suite di ogni riga
* l'indice dei job    — solo metadati e metriche aggregate

L'indice laterale e' cio' che rende praticabile la UI: filtrare per verdetto o
suite e impaginare tocca solo il sidecar, poi si leggono le sole righe servite.
"""

from __future__ import annotations

import json
import os
import threading

from core.logger import get_logger

log = get_logger(__name__)

RUNS_DIR = os.path.join("training_lab", "benchmark_runs")

_locks: dict[str, threading.Lock] = {}
_locks_guard = threading.Lock()


def _lock_for(job_id: str) -> threading.Lock:
    with _locks_guard:
        return _locks.setdefault(job_id, threading.Lock())


def _paths(job_id: str) -> tuple[str, str]:
    safe = "".join(c for c in job_id if c.isalnum() or c in "-_")
    return (
        os.path.join(RUNS_DIR, f"{safe}.jsonl"),
        os.path.join(RUNS_DIR, f"{safe}.idx.json"),
    )


def _ensure_dir() -> None:
    os.makedirs(RUNS_DIR, exist_ok=True)


def _load_index(job_id: str) -> list[list]:
    _, idx_path = _paths(job_id)
    if not os.path.exists(idx_path):
        return []
    try:
        with open(idx_path, "r", encoding="utf-8") as fh:
            return json.load(fh).get("entries", [])
    except Exception as err:
        log.warning("Indice risultati di %s illeggibile: %s", job_id, err)
        return []


def _save_index(job_id: str, entries: list[list]) -> None:
    _, idx_path = _paths(job_id)
    tmp = idx_path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump({"entries": entries}, fh)
    os.replace(tmp, idx_path)


def append_results(job_id: str, results: list[dict]) -> None:
    """Aggiunge esiti in coda al run, aggiornando l'indice laterale.

    Scrive a blocchi: il worker accumula gli esiti completati e li versa qui,
    cosi' il costo per quesito e' un append e non una riscrittura.
    """
    if not results:
        return
    _ensure_dir()
    data_path, _ = _paths(job_id)
    with _lock_for(job_id):
        entries = _load_index(job_id)
        offset = os.path.getsize(data_path) if os.path.exists(data_path) else 0
        # newline="\n" e' obbligatorio: con la traduzione automatica di Windows
        # ogni \n diventa \r\n sul disco, mentre l'indice conta un byte solo, e
        # gli offset finirebbero fuori posto già dalla seconda riga.
        with open(data_path, "a", encoding="utf-8", newline="\n") as fh:
            for result in results:
                line = json.dumps(result, ensure_ascii=False)
                fh.write(line + "\n")
                entries.append([
                    offset,
                    result.get("verdict", "fail"),
                    result.get("suite", ""),
                ])
                offset += len(line.encode("utf-8")) + 1
        _save_index(job_id, entries)


def count_results(job_id: str) -> int:
    return len(_load_index(job_id))


def verdict_counts(job_id: str) -> dict[str, int]:
    """Conteggio per verdetto letto dal solo indice laterale."""
    counts: dict[str, int] = {}
    for entry in _load_index(job_id):
        verdict = entry[1] if len(entry) > 1 else "fail"
        counts[verdict] = counts.get(verdict, 0) + 1
    return counts


def suite_breakdown(job_id: str) -> dict[str, dict[str, int]]:
    """Passati/totali per suite, per il riepilogo in testa al pannello."""
    out: dict[str, dict[str, int]] = {}
    for entry in _load_index(job_id):
        verdict = entry[1] if len(entry) > 1 else "fail"
        suite = (entry[2] if len(entry) > 2 else "") or "generale"
        stats = out.setdefault(suite, {"passed": 0, "failed": 0, "review": 0, "total": 0})
        stats["total"] += 1
        if verdict == "pass":
            stats["passed"] += 1
        elif verdict == "fail":
            stats["failed"] += 1
        else:
            stats["review"] += 1
    return out


def _read_at(data_path: str, offsets: list[int]) -> list[dict]:
    """Legge solo le righe richieste, saltando direttamente ai loro offset.

    Apertura binaria: `seek` in modalita' testo non lavora in byte, quindi con
    un offset calcolato in byte atterrerebbe a metà riga.
    """
    out: list[dict] = []
    if not os.path.exists(data_path):
        return out
    with open(data_path, "rb") as fh:
        for offset in offsets:
            try:
                fh.seek(offset)
                line = fh.readline().decode("utf-8", errors="replace")
                if line.strip():
                    out.append(json.loads(line))
            except Exception as err:
                log.debug("Riga a offset %s non leggibile: %s", offset, err)
    return out


def rebuild_index(job_id: str) -> int:
    """Ricostruisce l'indice laterale scorrendo il file degli esiti.

    Rete di sicurezza: se gli offset non combaciano piu' col contenuto (indice
    scritto da una versione precedente, scrittura interrotta a metà), il
    dettaglio resta comunque recuperabile con una singola passata sequenziale.
    """
    data_path, _ = _paths(job_id)
    if not os.path.exists(data_path):
        return 0
    entries: list[list] = []
    with _lock_for(job_id):
        with open(data_path, "rb") as fh:
            offset = 0
            for raw in fh:
                text = raw.decode("utf-8", errors="replace")
                if text.strip():
                    try:
                        item = json.loads(text)
                        entries.append([offset, item.get("verdict", "fail"), item.get("suite", "")])
                    except json.JSONDecodeError:
                        log.debug("Riga non valida a offset %s in %s", offset, job_id)
                offset += len(raw)
        _save_index(job_id, entries)
    log.info("Indice risultati di %s ricostruito: %d esiti.", job_id, len(entries))
    return len(entries)


def _index_is_sound(job_id: str, entries: list[list]) -> bool:
    """Controlla a campione che gli offset dell'indice puntino a righe valide."""
    if not entries:
        return True
    data_path, _ = _paths(job_id)
    probes = {0, len(entries) // 2, len(entries) - 1}
    sample = [entries[i][0] for i in sorted(probes) if 0 <= i < len(entries)]
    return len(_read_at(data_path, sample)) == len(sample)


def _sound_index(job_id: str) -> list[list]:
    """Indice del job, ricostruito al volo se risulta incoerente."""
    entries = _load_index(job_id)
    if _index_is_sound(job_id, entries):
        return entries
    rebuild_index(job_id)
    return _load_index(job_id)


def read_page(
    job_id: str,
    page: int = 1,
    page_size: int = 15,
    verdict: str = "all",
    suite: str = "all",
    query: str = "",
) -> dict:
    """Restituisce una pagina di esiti filtrata per verdetto, suite e testo.

    `verdict` accetta anche il gruppo ``review``, che raccoglie i quesiti da
    valutare a parte (risposta duplice, non interpretabile o in errore).
    """
    from core.training.answer_parser import REVIEW_VERDICTS

    data_path, _ = _paths(job_id)
    entries = _sound_index(job_id)

    selected: list[int] = []
    for entry in entries:
        entry_verdict = entry[1] if len(entry) > 1 else "fail"
        entry_suite = (entry[2] if len(entry) > 2 else "") or ""
        if verdict == "review":
            if entry_verdict not in REVIEW_VERDICTS:
                continue
        elif verdict not in ("all", ""):
            if entry_verdict != verdict:
                continue
        if suite not in ("all", "") and entry_suite != suite:
            continue
        selected.append(entry[0])

    if query.strip():
        # La ricerca testuale non e' indicizzabile: si scorre l'insieme già
        # ristretto dai filtri, con un tetto per non bloccare la richiesta.
        needle = query.strip().lower()
        matched: list[int] = []
        for item, offset in zip(_read_at(data_path, selected[:20000]), selected[:20000]):
            haystack = " ".join(str(item.get(k, "")) for k in
                                ("prompt", "category", "given_answer", "correct_answer", "suite_name"))
            if needle in haystack.lower():
                matched.append(offset)
        selected = matched

    total = len(selected)
    page_size = max(1, min(int(page_size or 15), 200))
    pages = max(1, (total + page_size - 1) // page_size)
    page = max(1, min(int(page or 1), pages))
    window = selected[(page - 1) * page_size: page * page_size]

    return {
        "success": True,
        "job_id": job_id,
        "page": page,
        "page_size": page_size,
        "total": total,
        "pages": pages,
        "results": _read_at(data_path, window),
    }


def read_review_queue(job_id: str, limit: int = 5000) -> list[dict]:
    """Tutti i quesiti in attesa di giudizio umano, per l'export dedicato."""
    from core.training.answer_parser import REVIEW_VERDICTS

    data_path, _ = _paths(job_id)
    offsets = [
        entry[0] for entry in _sound_index(job_id)
        if (entry[1] if len(entry) > 1 else "fail") in REVIEW_VERDICTS
    ]
    return _read_at(data_path, offsets[:limit])


def delete_results(job_id: str) -> None:
    """Cancella dettaglio e indice di un job eliminato."""
    for path in _paths(job_id):
        try:
            if os.path.exists(path):
                os.remove(path)
        except OSError as err:
            log.warning("Impossibile rimuovere %s: %s", path, err)
    with _locks_guard:
        _locks.pop(job_id, None)


def migrate_inline_results(job: dict) -> bool:
    """Sposta nello store i `test_results` ancora annidati in un vecchio job.

    I run salvati prima di questa separazione restano visibili senza conversioni
    manuali: al primo caricamento il dettaglio esce dall'indice e finisce nel
    file per job.
    """
    inline = job.get("test_results")
    if not inline:
        return False
    job_id = job.get("id", "")
    if not job_id:
        return False
    if count_results(job_id) == 0:
        from core.training.answer_parser import grade_answer
        normalized = []
        for item in inline:
            if "verdict" not in item:
                # Gli esiti storici hanno solo un booleano: si rigiudicano col
                # parser attuale per allinearli alle nuove categorie.
                graded = grade_answer(item, item.get("given_answer", ""))
                item = {**item, **{k: graded[k] for k in ("verdict", "passed", "needs_review")},
                        "parsed": graded.get("parsed", {})}
            normalized.append(item)
        append_results(job_id, normalized)
        log.info("Migrati %d esiti del job %s nello store dedicato.", len(normalized), job_id)
    job.pop("test_results", None)
    return True

# ==============================================================================
# core/harness/plan.py — Il piano dell'architetto, tenuto intero
# Sigma Studio v8 — Agent Harness (kernel)
# ==============================================================================
"""Normalizza il piano prodotto dall'Architect senza buttarne via i campi.

Il ruolo `architect` chiede un piano con **file coinvolti, dipendenze e ruolo
consigliato** per ogni task. Il normalizzatore del tool `pipeline` ne teneva
tre chiavi — `id`, `title`, `status` — e scartava il resto. A valle succedeva
questo:

- senza `role`, `_build_pipeline_from_architect` ripiegava su «coder»: ogni
  task del piano veniva eseguito dal Coder, e Tester e Reviewer non ricevevano
  mai un task;
- senza `depends_on`, il grafo delle dipendenze non aveva archi, e
  `next_role_batch()` — che esiste per rispettarli — sceglieva su un insieme in
  cui tutto era sempre pronto;
- senza `description`, l'istruzione del task diventava il suo titolo: una riga.

Tre campi scritti dal modello, letti da nessuno. Qui vengono tenuti, e con loro
le due cose che un grafo deve garantire a chi lo esegue:

**Una dipendenza verso un task che non esiste viene tolta.** `get_ready_tasks()`
considera soddisfatta una dipendenza solo se il nodo esiste **ed e' `done`**: un
id inventato non diventa mai `done`, e il task che lo nomina resta fermo per
sempre. Un errore di battitura dell'architetto bloccherebbe in silenzio meta'
del piano.

**Un ciclo viene spezzato.** Due task che si aspettano a vicenda non partono
mai, e nessuno dice perche'.

In entrambi i casi non si fallisce in silenzio: cio' che e' stato tolto finisce
negli avvisi, che tornano al modello nell'osservazione del turno. Un piano
corretto di nascosto insegna al modello che quel piano andava bene.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Set, Tuple

#: I ruoli che l'orchestratore sa far girare. L'elenco sta qui e non in
#: `roles.py` perche' questo modulo viene importato dal ciclo, e `roles`
#: importa il ciclo: metterlo di la' chiuderebbe un anello fra i moduli.
RUOLI_NOTI: Tuple[str, ...] = ("architect", "coder", "reviewer", "tester", "devops")

#: Il modello scrive in italiano perche' il prompt e' in italiano. Rifiutare
#: «programmatore» misurerebbe il vocabolario, non la qualita' del piano.
ALIAS_RUOLO: Dict[str, str] = {
    "architetto": "architect", "analista": "architect", "progettista": "architect",
    "programmatore": "coder", "sviluppatore": "coder", "developer": "coder",
    "implementatore": "coder", "dev": "coder",
    "revisore": "reviewer", "revisione": "reviewer",
    "test": "tester", "collaudo": "tester", "collaudatore": "tester", "qa": "tester",
    "ops": "devops", "operazioni": "devops", "rilascio": "devops", "deploy": "devops",
}

#: Quando il ruolo manca o non si riconosce. Il Coder e' il ripiego giusto
#: perche' e' l'unico che puo' scrivere: un task finito per sbaglio a un ruolo
#: in sola lettura non potrebbe essere svolto in nessun modo.
RUOLO_PREDEFINITO = "coder"

STATI = ("pending", "in_progress", "done")


def canonical_role(grezzo: Any) -> str:
    """Il ruolo canonico, o `coder` se non si riconosce."""
    nome = str(grezzo or "").strip().lower()
    if not nome:
        return RUOLO_PREDEFINITO
    if nome in RUOLI_NOTI:
        return nome
    return ALIAS_RUOLO.get(nome, RUOLO_PREDEFINITO)


def role_is_known(grezzo: Any) -> bool:
    """Se quel nome corrisponde davvero a un ruolo, alias compresi."""
    nome = str(grezzo or "").strip().lower()
    return bool(nome) and (nome in RUOLI_NOTI or nome in ALIAS_RUOLO)


def _stato(grezzo: Any) -> str:
    stato = str(grezzo or "pending").strip().lower()
    if stato in STATI:
        return stato
    if "complet" in stato or "done" in stato or "fatt" in stato:
        return "done"
    if "prog" in stato or "corr" in stato or "run" in stato:
        return "in_progress"
    return "pending"


def _elenco_di_stringhe(grezzo: Any) -> List[str]:
    """Un elenco, comunque il modello l'abbia scritto.

    Accetta la lista, la stringa con le virgole e la stringa singola: sono i
    tre modi in cui un piano arriva davvero.
    """
    if grezzo is None:
        return []
    if isinstance(grezzo, str):
        pezzi = [p.strip() for p in grezzo.replace(";", ",").split(",")]
        return [p for p in pezzi if p]
    if isinstance(grezzo, (list, tuple, set)):
        fuori: List[str] = []
        for voce in grezzo:
            if isinstance(voce, dict):
                voce = voce.get("id") or voce.get("task") or voce.get("path") or ""
            testo = str(voce or "").strip()
            if testo:
                fuori.append(testo)
        return fuori
    testo = str(grezzo).strip()
    return [testo] if testo else []


def _primo(grezzo: Dict[str, Any], *chiavi: str) -> Any:
    for chiave in chiavi:
        if grezzo.get(chiave) not in (None, "", [], {}):
            return grezzo[chiave]
    return None


def _righe_da_testo(testo: str) -> List[Dict[str, Any]]:
    """Un piano scritto come elenco puntato invece che come JSON."""
    righe = [r.strip("- *\t").strip() for r in testo.splitlines()]
    righe = [r.lstrip("0123456789.) ").strip() for r in righe if r.strip()]
    return [{"id": str(i + 1), "title": r} for i, r in enumerate(righe) if r]


def _togli_cicli(task: List[Dict[str, Any]]) -> List[str]:
    """Spezza i cicli, ritornando gli avvisi su cio' che ha tolto.

    Si visita in profondita' tenendo la pila del cammino: una dipendenza che
    punta a un nodo gia' nella pila chiuderebbe un anello, e viene tolta. Si
    toglie l'arco che lo chiude, non il task: il lavoro resta nel piano, perde
    soltanto un vincolo che nessuno avrebbe potuto soddisfare.
    """
    per_id = {t["id"]: t for t in task}
    avvisi: List[str] = []
    visitati: Set[str] = set()
    in_pila: Set[str] = set()

    def visita(tid: str) -> None:
        visitati.add(tid)
        in_pila.add(tid)
        tenute: List[str] = []
        for dep in per_id[tid]["depends_on"]:
            if dep in in_pila:
                avvisi.append(
                    f"dipendenza '{tid}' -> '{dep}' tolta: chiudeva un ciclo, e "
                    "due task che si aspettano a vicenda non partono mai"
                )
                continue
            tenute.append(dep)
            if dep not in visitati:
                visita(dep)
        per_id[tid]["depends_on"] = tenute
        in_pila.discard(tid)

    for t in task:
        if t["id"] not in visitati:
            visita(t["id"])
    return avvisi


def normalizza_piano(grezzi: Any) -> Tuple[List[Dict[str, Any]], List[str]]:
    """Il piano in forma canonica, piu' gli avvisi su cio' che e' stato corretto.

    Ogni task ha sempre le stesse sei chiavi, cosi' che chi lo consuma non
    debba mai chiedersi se un campo c'e': `id`, `title`, `status`, `role`,
    `description`, `depends_on`. `files` e `verify` compaiono quando il piano
    li dichiara, perche' sono cio' che rende un task eseguibile senza rileggere
    il piano intero.
    """
    if isinstance(grezzi, str):
        try:
            grezzi = json.loads(grezzi)
        except ValueError:
            grezzi = _righe_da_testo(grezzi)
    if isinstance(grezzi, dict):
        grezzi = _primo(grezzi, "tasks", "task_list", "pipeline", "items") or []
    if not isinstance(grezzi, (list, tuple)):
        return [], []

    avvisi: List[str] = []
    task: List[Dict[str, Any]] = []
    usati: Set[str] = set()

    for i, grezzo in enumerate(grezzi):
        if isinstance(grezzo, str):
            grezzo = {"title": grezzo.strip()}
        if not isinstance(grezzo, dict):
            continue
        titolo = str(_primo(grezzo, "title", "name", "task", "titolo")
                     or f"Task {i + 1}").strip()
        if not titolo:
            continue

        tid = str(_primo(grezzo, "id", "task_id") or (i + 1)).strip()
        if tid in usati:
            originale = tid
            n = 2
            while f"{tid}_{n}" in usati:
                n += 1
            tid = f"{tid}_{n}"
            avvisi.append(
                f"id '{originale}' usato due volte: il secondo task e' diventato "
                f"'{tid}', altrimenti le dipendenze verso '{originale}' sarebbero "
                "state ambigue"
            )
        usati.add(tid)

        ruolo_grezzo = _primo(grezzo, "role", "ruolo", "agent", "agente")
        if ruolo_grezzo and not role_is_known(ruolo_grezzo):
            avvisi.append(
                f"ruolo '{ruolo_grezzo}' del task '{tid}' non esiste: assegnato a "
                f"'{RUOLO_PREDEFINITO}'. I ruoli sono {', '.join(RUOLI_NOTI)}"
            )

        voce: Dict[str, Any] = {
            "id": tid,
            "title": titolo,
            "status": _stato(_primo(grezzo, "status", "stato")),
            "role": canonical_role(ruolo_grezzo),
            "description": str(
                _primo(grezzo, "description", "descrizione", "details", "dettagli") or ""
            ).strip(),
            "depends_on": _elenco_di_stringhe(
                _primo(grezzo, "depends_on", "dependencies", "dipendenze", "dipende_da")
            ),
        }
        file_coinvolti = _elenco_di_stringhe(
            _primo(grezzo, "files", "file", "file_coinvolti", "paths"))
        if file_coinvolti:
            voce["files"] = file_coinvolti
        verifica = str(
            _primo(grezzo, "verify", "verifica", "check", "test_command") or "").strip()
        if verifica:
            voce["verify"] = verifica
        task.append(voce)

    noti = {t["id"] for t in task}
    for t in task:
        tenute: List[str] = []
        for dep in t["depends_on"]:
            if dep == t["id"]:
                avvisi.append(
                    f"il task '{t['id']}' dipendeva da se stesso: dipendenza tolta")
                continue
            if dep not in noti:
                avvisi.append(
                    f"dipendenza '{t['id']}' -> '{dep}' tolta: nel piano non c'e' "
                    f"nessun task con id '{dep}', e un task che aspetta un id "
                    "inesistente non parte mai"
                )
                continue
            if dep in tenute:
                continue
            tenute.append(dep)
        t["depends_on"] = tenute

    avvisi.extend(_togli_cicli(task))
    return task, avvisi


def descrivi_task(task: Dict[str, Any], obiettivo: str = "") -> str:
    """Il testo che viene consegnato a chi esegue un singolo task.

    Il titolo non basta: e' una riga, ed era tutto cio' che l'esecutore riceveva
    quando `description` veniva scartata. Qui tornano insieme la descrizione, i
    file che il piano indica e la verifica che il piano chiede — cioe' le tre
    cose che permettono di lavorare senza rileggere il piano intero.
    """
    righe = [str(task.get("title") or "").strip()]
    descrizione = str(task.get("description") or "").strip()
    if descrizione and descrizione != righe[0]:
        righe += ["", descrizione]
    file_coinvolti = task.get("files") or []
    if file_coinvolti:
        righe += ["", "File indicati dal piano:"] + [f"- {f}" for f in file_coinvolti]
    if str(obiettivo or "").strip():
        righe += ["", f"Questo task fa parte dell'obiettivo: {obiettivo.strip()}"]
    verifica = str(task.get("verify") or "").strip()
    if verifica:
        righe += [
            "",
            f"VERIFICA RICHIESTA: esegui `{verifica}` e chiudi solo quando esce "
            "con codice 0.",
        ]
    return "\n".join(righe)

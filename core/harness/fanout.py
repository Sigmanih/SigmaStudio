# ==============================================================================
# core/harness/fanout.py — Piu' agenti sullo stesso obiettivo, in parallelo
# Sigma Studio v8 — Agent Harness (kernel)
# ==============================================================================
"""N run dell'agente che consumano la stessa coda di lavoro.

C'e' un ciclo per volta, e un orchestratore che fa lavorare cinque ruoli **uno
dopo l'altro**. Va bene per un obiettivo circoscritto. Non va bene per un
lavoro che tocca duecento file: in sequenza non finisce, e non e' una questione
di pazienza — e' che il contesto di un singolo run non ci sta, e a meta' strada
l'agente non ricorda piu' cosa aveva gia' sistemato.

Qui il lavoro viene spezzato prima (una voce per file, per cartella, per
modulo — lo decide chi riempie la coda) e poi consumato da piu' run in
parallelo. Ognuno prende una voce, la porta a termine, e ne prende un'altra.

**Perche' e' sicuro solo adesso.** Ogni run lavora nel proprio worktree git:
due agenti che scrivono nello stesso momento non si sovrascrivono, perche' non
scrivono negli stessi file. Senza l'isolamento questo modulo sarebbe un modo
elegante di corrompere un repository.

**Cosa non fa.** Non decide come spezzare il lavoro: quella e' una scelta che
richiede di aver guardato il progetto, ed e' il primo compito dell'agente che
pianifica. Qui si consuma una coda gia' fatta.
"""

from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Generator, List, Optional

from core.harness.workqueue import Voce, WorkQueue, get_queue
from core.logger import get_logger

log = get_logger("fanout")

#: Quanti run in parallelo, se non lo dice nessuno. Due: su una macchina che
#: serve anche il modello, salire oltre di solito non fa finire prima — la
#: banda verso i pesi e' condivisa, e i run cominciano ad aspettarsi a vicenda.
LAVORATORI_PREDEFINITI = 2

#: Tetto: oltre questo non e' parallelismo, e' contesa.
LAVORATORI_MASSIMI = 8


@dataclass
class EsitoVoce:
    """Com'e' andata una voce."""

    item_id: str
    title: str
    ok: bool
    turns: int = 0
    files: List[str] = field(default_factory=list)
    error: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {"item_id": self.item_id, "title": self.title, "ok": self.ok,
                "turns": self.turns, "files": self.files, "error": self.error}


def _prompt_voce(voce: Voce, obiettivo_generale: str) -> str:
    """Il compito di un singolo lavoratore.

    L'obiettivo generale c'e' perche' senza di esso la voce non si capisce:
    «aggiorna sigma_network/index.jsx» non dice cosa aggiornare. Ma viene dopo
    la voce, non prima, perche' cio' che l'agente deve fare adesso e' la voce.
    """
    righe = [voce.title.strip()]
    dettagli = voce.payload or {}
    if dettagli:
        righe.append("")
        for chiave, valore in dettagli.items():
            righe.append(f"{chiave}: {valore}")
    if obiettivo_generale.strip():
        righe += [
            "",
            "Questo pezzo fa parte di un lavoro piu' grande: "
            f"{obiettivo_generale.strip()}",
            "Occupati SOLO del pezzo qui sopra. Altri agenti stanno lavorando "
            "sugli altri in parallelo: non toccare file che non ti competono, "
            "e non riscrivere parti condivise se non e' proprio il tuo compito.",
        ]
    return "\n".join(righe)


def run_queue(
    queue_id: str,
    workspace_root: str,
    goal: str = "",
    workers: int = LAVORATORI_PREDEFINITI,
    model_name: Optional[str] = None,
    max_turns: int = 20,
    role_id: str = "",
    should_cancel: Optional[Callable[[], bool]] = None,
    deliver: bool = True,
) -> Generator[Dict[str, Any], None, None]:
    """Consuma una coda con piu' run in parallelo, raccontando cosa succede.

    Genera eventi: `fanout_started`, `item_started`, `item_finished`,
    `fanout_progress`, `fanout_finished`. Sono l'unico modo che ha chi guarda
    di sapere a che punto e' un lavoro che dura ore.

    `deliver` lascia che ogni run consegni il proprio pezzo (branch, `dev`,
    richiesta). Spento, il lavoro resta sui branch dei singoli run.
    """
    coda = get_queue(queue_id, goal=goal)
    obiettivo = coda.goal or goal
    numero = max(1, min(int(workers or LAVORATORI_PREDEFINITI), LAVORATORI_MASSIMI))

    eventi: "list[Dict[str, Any]]" = []
    lucchetto_eventi = threading.Lock()
    fermati = threading.Event()

    def emetti(evento: Dict[str, Any]) -> None:
        with lucchetto_eventi:
            eventi.append(evento)

    def annullato() -> bool:
        return fermati.is_set() or bool(should_cancel and should_cancel())

    def lavoratore(indice: int) -> None:
        nome = f"w{indice}"
        while not annullato():
            voce = coda.claim(worker=nome)
            if voce is None:
                return
            emetti({"type": "item_started", "worker": nome,
                    "item_id": voce.id, "title": voce.title})
            esito = _esegui_voce(
                voce, coda, workspace_root, obiettivo, nome,
                model_name=model_name, max_turns=max_turns, role_id=role_id,
                should_cancel=annullato, deliver=deliver,
            )
            emetti({"type": "item_finished", "worker": nome, **esito.to_dict()})
            emetti({"type": "fanout_progress", **coda.progress()})

    yield {"type": "fanout_started", "workers": numero, **coda.progress()}

    thread = [
        threading.Thread(target=lavoratore, args=(i + 1,),
                         name=f"fanout-{queue_id}-{i + 1}", daemon=True)
        for i in range(numero)
    ]
    for t in thread:
        t.start()

    # Si resta qui a riferire finche' c'e' qualcuno che lavora. Gli eventi
    # arrivano dai thread e passano di qui: e' il solo punto in cui il
    # chiamante — una risposta HTTP che sta streammando — puo' riceverli.
    try:
        while any(t.is_alive() for t in thread):
            with lucchetto_eventi:
                da_mandare, eventi[:] = list(eventi), []
            for evento in da_mandare:
                yield evento
            if annullato():
                break
            time.sleep(0.2)
    finally:
        if annullato():
            fermati.set()
        for t in thread:
            t.join(timeout=5.0)

    with lucchetto_eventi:
        for evento in eventi:
            yield evento

    yield {"type": "fanout_finished", "cancelled": annullato(), **coda.progress()}


def _esegui_voce(
    voce: Voce,
    coda: WorkQueue,
    workspace_root: str,
    obiettivo: str,
    worker: str,
    model_name: Optional[str],
    max_turns: int,
    role_id: str,
    should_cancel: Callable[[], bool],
    deliver: bool,
) -> EsitoVoce:
    """Un run dell'agente su una voce sola. Non solleva mai.

    Un lavoratore che muore su una voce lascerebbe gli altri a girare a vuoto e
    la coda ferma: qui ogni errore diventa un fallimento registrato, e la voce
    torna disponibile finche' restano tentativi.
    """
    from core.harness.loop import stream_admin_agent_turn

    sessione = f"fanout_{coda.queue_id}_{voce.id}_{uuid.uuid4().hex[:6]}"
    esito = EsitoVoce(item_id=voce.id, title=voce.title, ok=False)
    file_toccati: List[str] = []
    raggiunto = False

    try:
        for evento in stream_admin_agent_turn(
            messages=[{"role": "user", "content": _prompt_voce(voce, obiettivo)}],
            workspace_root=workspace_root,
            model_name=model_name,
            max_turns=max_turns,
            session_id=sessione,
            should_cancel=should_cancel,
            # Ogni lavoratore nel proprio worktree: e' cio' che rende sicuro
            # farli scrivere nello stesso momento.
            isolate_worktree=True,
            # Nessuna revisione per run: N approvazioni in parallelo non le da'
            # nessuno. La revisione e' la richiesta che raccoglie tutto.
            review_run=False,
            allowed_tools=None,
            policy_label=role_id or "",
        ):
            tipo = evento.get("type")
            if tipo == "run_metrics":
                esito.turns = int(evento.get("turns") or 0)
                raggiunto = bool(evento.get("goal_reached"))
            elif tipo == "ledger":
                stato = evento.get("state") or {}
                file_toccati = list(stato.get("modified_files") or file_toccati)
            elif tipo in ("run_delivered", "delivery_failed"):
                file_toccati = list(evento.get("files") or file_toccati)
    except Exception as exc:
        log.warning("[Fanout] voce '%s' interrotta da un errore: %s", voce.id, exc)
        esito.error = str(exc)
        coda.fail(voce.id, esito.error)
        return esito

    esito.files = file_toccati
    esito.ok = raggiunto
    if raggiunto:
        coda.complete(voce.id, {"turns": esito.turns, "files": file_toccati,
                                "session_id": sessione, "worker": worker})
    else:
        # Non e' detto che sia colpa della voce: puo' essere finito il budget di
        # turni. La coda decide se vale la pena riprovare.
        esito.error = "obiettivo non raggiunto entro i turni disponibili"
        coda.fail(voce.id, esito.error)
    return esito

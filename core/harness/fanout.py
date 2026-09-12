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
    #: Dove sta il lavoro, riuscito o no. Un branch di cui nessuno conosce
    #: il nome e' perso quanto uno cancellato.
    branch: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {"item_id": self.item_id, "title": self.title, "ok": self.ok,
                "turns": self.turns, "files": self.files,
                "error": self.error, "branch": self.branch}


def _prompt_voce(voce: Voce, obiettivo_generale: str) -> str:
    """Il compito di un singolo lavoratore.

    L'obiettivo generale c'e' perche' senza di esso la voce non si capisce:
    «aggiorna sigma_network/index.jsx» non dice cosa aggiornare. Ma viene dopo
    la voce, non prima, perche' cio' che l'agente deve fare adesso e' la voce.

    Se la voce dichiara un comando di verifica, quello diventa la prova
    richiesta. Senza, l'agente deve trovarsela: il cancello di completamento
    pretende una verifica riuscita, e su una prova dal vivo un agente ha
    scritto il file giusto, non ha saputo dimostrarlo, e la voce e' stata
    riprovata tre volte per nulla. Dire in anticipo come si dimostra il
    lavoro costa una riga e vale tre run.
    """
    righe = [voce.title.strip()]
    dettagli = dict(voce.payload or {})
    verifica = str(dettagli.pop("verify", "") or "").strip()
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
    if verifica:
        righe += [
            "",
            f"VERIFICA RICHIESTA: esegui `{verifica}` e chiudi solo quando "
            "esce con codice 0. E' la prova che ti verra' chiesta.",
        ]
    else:
        righe += [
            "",
            "Prima di chiudere devi DIMOSTRARE che il lavoro e' fatto con "
            "un comando che esce con codice 0: un test, un lint, un import, "
            "o la lettura del file che hai prodotto. Sceglilo al passo "
            "`spec`, non alla fine: senza una verifica riuscita la chiusura "
            "viene rifiutata e il tuo lavoro resta non dimostrato.",
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
                # Niente da prendere non vuol dire niente da fare: l'unica
                # voce rimasta puo' essere in attesa di quella che un altro
                # lavoratore ha in mano adesso. Andarsene qui chiuderebbe i
                # thread con la coda a meta'.
                if coda.attesa_utile():
                    time.sleep(0.5)
                    continue
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


def _file_modificati(stato: Dict[str, Any]) -> List[str]:
    """I file che il run ha davvero cambiato, letti dallo stato del ledger.

    Lo snapshot elenca sotto `files` **tutti** i file toccati, letture comprese:
    un file solo letto non e' una modifica. Si contano quelli con una scrittura,
    una modifica o una creazione.

    Qui c'era una chiave inventata — `modified_files` — che nello snapshot non
    esiste: la lista restava sempre vuota, e il ventaglio riferiva «nessuna
    modifica prodotta» su run che avevano scritto il file giusto. Il messaggio
    mentiva, ed e' il modo peggiore in cui puo' rompersi un resoconto.
    """
    modificati = []
    for voce in (stato or {}).get("files") or []:
        if not isinstance(voce, dict):
            continue
        if voce.get("writes") or voce.get("edits") or voce.get("created"):
            percorso = str(voce.get("path") or "").strip()
            if percorso and percorso not in modificati:
                modificati.append(percorso)
    return modificati


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
    verifica = str((voce.payload or {}).get("verify") or "").strip()
    esito = EsitoVoce(item_id=voce.id, title=voce.title, ok=False)
    file_toccati: List[str] = []
    raggiunto = False
    non_applicato = {"si": False}

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
            # La prova che la voce dichiara vale come verifica per questo run:
            # chiederla nel prompt e poi non riconoscerla e' il modo piu' sicuro
            # di far fallire un lavoro fatto bene.
            verify_command=verifica,
            # Non era passato: il parametro c'era, il ciclo decideva comunque
            # dalla configurazione, e chiedere «non consegnare» non aveva alcun
            # effetto. Lo stesso difetto che questo progetto ha gia' visto
            # cinque volte, stavolta in casa propria.
            deliver=deliver,
            allowed_tools=None,
            policy_label=role_id or "",
        ):
            tipo = evento.get("type")
            if tipo == "run_metrics":
                esito.turns = int(evento.get("turns") or 0)
                raggiunto = bool(evento.get("goal_reached"))
            elif tipo == "ledger":
                file_toccati = _file_modificati(evento.get("state") or {}) or file_toccati
            elif tipo in ("run_delivered", "delivery_failed"):
                file_toccati = list(evento.get("files") or file_toccati)
            elif tipo == "apply_failed":
                # L'obiettivo e' stato chiuso ma il lavoro non e' arrivato
                # nell'albero: la voce NON e' fatta. Segnarla fatta lascerebbe
                # la coda che dichiara un lavoro compiuto mentre il codice sta
                # su un branch che nessuno guardera'.
                esito.branch = str(evento.get("branch") or esito.branch)
                non_applicato["si"] = True
            elif tipo == "worktree_preserved":
                # Il run e' finito senza chiudere: qui c'e' il branch su cui il
                # lavoro e' rimasto, ed e' l'unica cosa che serve sapere per
                # andarselo a riprendere.
                esito.branch = str(evento.get("branch") or esito.branch)
    except Exception as exc:
        log.warning("[Fanout] voce '%s' interrotta da un errore: %s", voce.id, exc)
        esito.error = str(exc)
        coda.fail(voce.id, esito.error)
        return esito

    esito.files = file_toccati
    # Chiudere l'obiettivo non basta: il lavoro deve essere arrivato dove
    # serve. Su un ventaglio vero cinque voci su otto hanno chiuso mentre la
    # patch verso l'albero falliva, e la coda le ha segnate fatte.
    esito.ok = raggiunto and not non_applicato["si"]
    esito.branch = esito.branch or ("sigma-run/" + sessione)
    if esito.ok:
        coda.complete(voce.id, {"turns": esito.turns, "files": file_toccati,
                                "session_id": sessione, "worker": worker})
    elif non_applicato["si"]:
        esito.error = (
            "obiettivo chiuso ma il lavoro non e' arrivato nell'albero: "
            "resta sul branch %s" % esito.branch
        )
        coda.fail(voce.id, esito.error)
    else:
        # Distinguere «non ha fatto niente» da «ha fatto e non l'ha
        # dimostrato»: sono due problemi diversi e chiedono due rimedi
        # diversi. Nel secondo caso il lavoro esiste e sta sul branch della
        # sessione — riprovare identico non lo migliora, quello che manca e'
        # una prova, ed e' successo dal vivo con un file scritto bene.
        if file_toccati:
            esito.error = (
                "lavoro prodotto (%d file) ma non dimostrato: resta sul "
                "branch %s" % (len(file_toccati), esito.branch)
            )
        else:
            esito.error = "nessuna modifica prodotta entro i turni disponibili"
        coda.fail(voce.id, esito.error)
    return esito

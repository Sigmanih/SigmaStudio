# ==============================================================================
# core/harness/workqueue.py — La lista del lavoro, che sopravvive ai run
# Sigma Studio v8 — Agent Harness (kernel)
# ==============================================================================
"""Una coda di lavoro che vive su disco e piu' agenti possono consumare.

Il ledger racconta un run. Quando il lavoro e' duecento file, il run non e'
piu' l'unita' giusta: servono molti run, magari in parallelo, magari ripresi
domani perche' stanotte il computer si e' spento — e serve un posto dove sta
scritto **cosa e' gia' stato fatto**. Senza, ogni ripartenza ricomincia dalla
mappa, e la mappa e' la parte costosa.

Tre proprieta' la rendono utile invece che decorativa:

**Prendere una voce e' atomico.** Due agenti che partono insieme non devono
lavorare sullo stesso file: chi arriva primo la prende, l'altro passa oltre.

**Il lavoro non resta appeso.** Un agente che muore a meta' lascerebbe la sua
voce «in corso» per sempre. Dopo un tempo dichiarato la voce torna disponibile,
e il conteggio dei tentativi impedisce che una voce impossibile giri all'infinito.

**Lo stato e' sul disco, non nella memoria del processo.** E' l'unica differenza
che conta fra una coda e una lista.
"""

from __future__ import annotations

import json
import os
import tempfile
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from core import paths
from core.logger import get_logger

log = get_logger("workqueue")

#: Stati di una voce.
DA_FARE = "todo"
IN_CORSO = "doing"
FATTA = "done"
FALLITA = "failed"

#: Dopo quanto una voce «in corso» viene considerata abbandonata. Generoso: un
#: run dell'agente puo' durare parecchio, e riprendere una voce ancora viva
#: significherebbe farla fare due volte.
ABBANDONO_S = 3600.0

#: Quanti tentativi prima di dichiarare una voce fallita. Una voce che fa
#: morire l'agente lo farebbe morire all'infinito, e il resto della coda non
#: verrebbe mai lavorato.
TENTATIVI_MASSIMI = 3


@dataclass
class Voce:
    """Un pezzo di lavoro indipendente."""

    id: str
    title: str
    payload: Dict[str, Any] = field(default_factory=dict)
    state: str = DA_FARE
    attempts: int = 0
    worker: str = ""
    claimed_at: float = 0.0
    updated_at: float = 0.0
    result: Dict[str, Any] = field(default_factory=dict)
    error: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class WorkQueue:
    """Una coda di lavoro persistente, condivisa fra piu' agenti.

    Il lucchetto e' di processo. Basta perche' i consumatori sono i thread di
    questo server; se un giorno saranno processi diversi servira' un lucchetto
    sul file, e il posto dove metterlo e' qui.
    """

    def __init__(self, queue_id: str, goal: str = "",
                 abbandono_s: float = ABBANDONO_S,
                 tentativi_massimi: int = TENTATIVI_MASSIMI):
        self.queue_id = str(queue_id or "").strip() or uuid.uuid4().hex[:12]
        self.goal = goal
        self._abbandono_s = float(abbandono_s)
        self._tentativi_massimi = int(tentativi_massimi)
        self._lock = threading.RLock()
        self._voci: Dict[str, Voce] = {}
        self._ordine: List[str] = []
        self._carica()

    # -- persistenza ---------------------------------------------------------

    @property
    def path(self) -> Path:
        return Path(paths.var_dir()) / "work_queues" / f"{self.queue_id}.json"

    def _carica(self) -> None:
        percorso = self.path
        if not percorso.is_file():
            return
        try:
            dati = json.loads(percorso.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            log.warning("[WorkQueue] '%s' illeggibile: %s", self.queue_id, exc)
            return
        self.goal = dati.get("goal", self.goal)
        for grezza in dati.get("items", []):
            try:
                voce = Voce(**grezza)
            except TypeError:
                continue
            self._voci[voce.id] = voce
            self._ordine.append(voce.id)

    def _salva(self) -> None:
        """Scrive la coda in modo che un'interruzione non la lasci a meta'.

        Prima su un file temporaneo, poi uno spostamento atomico: una coda
        troncata a meta' salvataggio sarebbe peggio di nessuna coda, perche'
        farebbe rifare lavoro gia' fatto senza dirlo.
        """
        percorso = self.path
        percorso.parent.mkdir(parents=True, exist_ok=True)
        dati = {
            "queue_id": self.queue_id,
            "goal": self.goal,
            "updated_at": time.time(),
            "items": [self._voci[i].to_dict() for i in self._ordine if i in self._voci],
        }
        try:
            with tempfile.NamedTemporaryFile(
                "w", encoding="utf-8", dir=str(percorso.parent),
                prefix=f".{self.queue_id}.", suffix=".tmp", delete=False,
            ) as f:
                json.dump(dati, f, indent=2, ensure_ascii=False)
                temporaneo = f.name
            os.replace(temporaneo, percorso)
        except OSError as exc:
            log.error("[WorkQueue] salvataggio di '%s' fallito: %s", self.queue_id, exc)

    # -- costruzione ---------------------------------------------------------

    def add(self, title: str, payload: Optional[Dict[str, Any]] = None,
            item_id: str = "") -> Voce:
        """Aggiunge una voce. Un id gia' presente non viene duplicato."""
        with self._lock:
            vid = str(item_id or "").strip() or f"w_{uuid.uuid4().hex[:10]}"
            if vid in self._voci:
                return self._voci[vid]
            voce = Voce(id=vid, title=str(title), payload=dict(payload or {}),
                        updated_at=time.time())
            self._voci[vid] = voce
            self._ordine.append(vid)
            self._salva()
            return voce

    def add_many(self, voci: Iterable[Any]) -> List[Voce]:
        """Riempie la coda in un colpo solo, salvando una volta sola."""
        create: List[Voce] = []
        with self._lock:
            for grezza in voci:
                if isinstance(grezza, str):
                    titolo, carico, vid = grezza, {}, ""
                else:
                    titolo = str(grezza.get("title") or grezza.get("path") or "")
                    carico = dict(grezza.get("payload") or
                                  {k: v for k, v in grezza.items()
                                   if k not in ("title", "id", "payload")})
                    vid = str(grezza.get("id") or "")
                vid = vid or f"w_{uuid.uuid4().hex[:10]}"
                if vid in self._voci:
                    continue
                voce = Voce(id=vid, title=titolo, payload=carico, updated_at=time.time())
                self._voci[vid] = voce
                self._ordine.append(vid)
                create.append(voce)
            self._salva()
        return create

    # -- consumo -------------------------------------------------------------

    def _recupera_abbandonate(self) -> None:
        """Rimette in circolo cio' che nessuno sta piu' lavorando.

        Va chiamata dentro il lucchetto.
        """
        adesso = time.time()
        for voce in self._voci.values():
            if voce.state != IN_CORSO:
                continue
            if adesso - voce.claimed_at < self._abbandono_s:
                continue
            if voce.attempts >= self._tentativi_massimi:
                voce.state = FALLITA
                voce.error = voce.error or "abbandonata troppe volte"
            else:
                voce.state = DA_FARE
                voce.worker = ""
            voce.updated_at = adesso
            log.info("[WorkQueue] '%s' riportata a '%s': nessuno la stava lavorando",
                     voce.id, voce.state)

    def claim(self, worker: str = "") -> Optional[Voce]:
        """Prende la prossima voce disponibile. None se non ce ne sono.

        Atomico rispetto agli altri consumatori: e' cio' che impedisce a due
        agenti di lavorare sullo stesso pezzo.
        """
        with self._lock:
            self._recupera_abbandonate()
            for vid in self._ordine:
                voce = self._voci.get(vid)
                if voce is None or voce.state != DA_FARE:
                    continue
                voce.state = IN_CORSO
                voce.worker = str(worker or "")
                voce.attempts += 1
                voce.claimed_at = time.time()
                voce.updated_at = voce.claimed_at
                self._salva()
                return voce
            return None

    def complete(self, item_id: str, result: Optional[Dict[str, Any]] = None) -> bool:
        with self._lock:
            voce = self._voci.get(str(item_id))
            if voce is None:
                return False
            voce.state = FATTA
            voce.result = dict(result or {})
            voce.error = ""
            voce.updated_at = time.time()
            self._salva()
            return True

    def fail(self, item_id: str, error: str = "", riprovabile: bool = True) -> bool:
        """Registra un fallimento. Torna disponibile se restano tentativi.

        Un fallimento non e' una condanna: un errore di rete o un modello che
        si e' perso non dicono che la voce sia impossibile. Dopo
        `tentativi_massimi` pero' lo diventa, altrimenti una sola voce
        avvelenata terrebbe occupati gli agenti mentre il resto aspetta.
        """
        with self._lock:
            voce = self._voci.get(str(item_id))
            if voce is None:
                return False
            voce.error = str(error or "")
            voce.worker = ""
            if riprovabile and voce.attempts < self._tentativi_massimi:
                voce.state = DA_FARE
                # In fondo, non in testa. Restando dov'era, il lavoratore la
                # riprenderebbe subito e la rifarebbe tre volte di fila prima
                # che il resto della coda avanzi: una voce difficile fermerebbe
                # duecento voci facili. E cio' che l'ha fatta fallire — un
                # modello confuso, un file occupato, la rete — ha anche il
                # tempo di cambiare.
                if voce.id in self._ordine:
                    self._ordine.remove(voce.id)
                    self._ordine.append(voce.id)
            else:
                voce.state = FALLITA
            voce.updated_at = time.time()
            self._salva()
            return True

    def release(self, item_id: str) -> bool:
        """Restituisce una voce senza contarla come tentativo fallito."""
        with self._lock:
            voce = self._voci.get(str(item_id))
            if voce is None:
                return False
            voce.state = DA_FARE
            voce.worker = ""
            voce.attempts = max(voce.attempts - 1, 0)
            voce.updated_at = time.time()
            self._salva()
            return True

    # -- lettura -------------------------------------------------------------

    def items(self, state: str = "") -> List[Voce]:
        with self._lock:
            tutte = [self._voci[i] for i in self._ordine if i in self._voci]
            return [v for v in tutte if not state or v.state == state]

    def progress(self) -> Dict[str, Any]:
        """Il consuntivo: e' cio' che si guarda mentre gira."""
        with self._lock:
            conteggi = {DA_FARE: 0, IN_CORSO: 0, FATTA: 0, FALLITA: 0}
            for voce in self._voci.values():
                conteggi[voce.state] = conteggi.get(voce.state, 0) + 1
            totale = len(self._voci)
            return {
                "queue_id": self.queue_id,
                "goal": self.goal,
                "total": totale,
                "todo": conteggi[DA_FARE],
                "doing": conteggi[IN_CORSO],
                "done": conteggi[FATTA],
                "failed": conteggi[FALLITA],
                "finished": conteggi[DA_FARE] == 0 and conteggi[IN_CORSO] == 0,
            }

    def is_finished(self) -> bool:
        return bool(self.progress()["finished"])

    def reset_failed(self) -> int:
        """Rimette in coda cio' che aveva rinunciato. Ritorna quante voci."""
        with self._lock:
            n = 0
            for voce in self._voci.values():
                if voce.state == FALLITA:
                    voce.state = DA_FARE
                    voce.attempts = 0
                    voce.error = ""
                    voce.updated_at = time.time()
                    n += 1
            if n:
                self._salva()
            return n

    def delete(self) -> None:
        with self._lock:
            try:
                self.path.unlink(missing_ok=True)
            except OSError:
                pass


# ---------------------------------------------------------------------------
# Registro delle code aperte
# ---------------------------------------------------------------------------
# Due consumatori della stessa coda devono vedere lo stesso oggetto, altrimenti
# i loro lucchetti proteggono due copie diverse e `claim` smette di essere
# atomico — cioe' la coda smette di essere una coda.

_code: Dict[str, WorkQueue] = {}
_lucchetto_registro = threading.RLock()


def get_queue(queue_id: str, goal: str = "") -> WorkQueue:
    chiave = str(queue_id or "").strip()
    with _lucchetto_registro:
        coda = _code.get(chiave)
        if coda is None:
            coda = WorkQueue(chiave, goal=goal)
            _code[chiave] = coda
        elif goal and not coda.goal:
            coda.goal = goal
        return coda


def forget_queue(queue_id: str) -> None:
    with _lucchetto_registro:
        _code.pop(str(queue_id or "").strip(), None)


def list_queues() -> List[Dict[str, Any]]:
    """Le code presenti su disco, con il loro stato."""
    radice = Path(paths.var_dir()) / "work_queues"
    if not radice.is_dir():
        return []
    esiti = []
    for percorso in sorted(radice.glob("*.json")):
        try:
            esiti.append(get_queue(percorso.stem).progress())
        except Exception as exc:
            log.debug("[WorkQueue] '%s' non leggibile: %s", percorso.name, exc)
    return esiti

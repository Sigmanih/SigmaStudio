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
#: Una voce che non potra' mai partire, perche' cio' da cui dipende non e'
#: stato fatto. Diverso da FALLITA: questa non ha nemmeno provato, e
#: riprovarla non servirebbe finche' la sua dipendenza resta indietro.
BLOCCATA = "blocked"

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
    #: Le voci che devono essere `done` prima che questa possa partire.
    #: Senza, l'unico modo di ordinare il lavoro era metterlo in fila e usare
    #: un solo lavoratore — cioe' rinunciare al parallelismo per esprimere un
    #: vincolo che riguardava due voci su venti.
    depends_on: List[str] = field(default_factory=list)
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
            item_id: str = "", depends_on: Optional[Iterable[str]] = None) -> Voce:
        """Aggiunge una voce. Un id gia' presente non viene duplicato."""
        with self._lock:
            vid = str(item_id or "").strip() or f"w_{uuid.uuid4().hex[:10]}"
            if vid in self._voci:
                return self._voci[vid]
            voce = Voce(id=vid, title=str(title), payload=dict(payload or {}),
                        depends_on=[d for d in (depends_on or [])
                                    if d in self._voci and d != vid],
                        updated_at=time.time())
            self._voci[vid] = voce
            self._ordine.append(vid)
            self._salva()
            return voce

    def add_many(self, voci: Iterable[Any],
                 avvisi: Optional[List[str]] = None) -> List[Voce]:
        """Riempie la coda in un colpo solo, salvando una volta sola.

        Le dipendenze vengono verificate contro cio' che la coda conosce **piu'
        cio' che sta entrando adesso**: un piano nomina le proprie voci fra
        loro, e controllarle una per una le rifiuterebbe tutte tranne la prima.

        Una dipendenza verso un id che non esiste viene tolta, non ignorata:
        `claim()` non la considerera' mai soddisfatta, e la voce che la nomina
        resterebbe ferma per sempre senza che nessuno dica perche'. Cio' che
        viene tolto finisce in `avvisi`, se il chiamante ne passa una lista.
        """
        grezze = list(voci)
        create: List[Voce] = []
        note = avvisi if avvisi is not None else []

        def _scomponi(grezza: Any):
            if isinstance(grezza, str):
                return grezza, {}, "", []
            titolo = str(grezza.get("title") or grezza.get("path") or "")
            dipendenze = grezza.get("depends_on") or grezza.get("dipende_da") or []
            if isinstance(dipendenze, str):
                dipendenze = [d.strip() for d in dipendenze.replace(";", ",").split(",")]
            dipendenze = [str(d).strip() for d in dipendenze if str(d).strip()]
            carico = dict(grezza.get("payload") or
                          {k: v for k, v in grezza.items()
                           if k not in ("title", "id", "payload", "depends_on",
                                        "dipende_da")})
            return titolo, carico, str(grezza.get("id") or ""), dipendenze

        with self._lock:
            in_arrivo = {str(g.get("id") or "").strip()
                         for g in grezze if isinstance(g, dict) and g.get("id")}
            conosciuti = set(self._voci) | in_arrivo
            for grezza in grezze:
                titolo, carico, vid, dipendenze = _scomponi(grezza)
                vid = vid or f"w_{uuid.uuid4().hex[:10]}"
                if vid in self._voci:
                    continue
                tenute: List[str] = []
                for dep in dipendenze:
                    if dep == vid:
                        note.append(f"'{vid}' dipendeva da se stessa: tolta")
                    elif dep not in conosciuti:
                        note.append(
                            f"dipendenza '{vid}' -> '{dep}' tolta: nella coda non "
                            f"c'e' nessuna voce '{dep}', e una voce che aspetta "
                            "un id inesistente non parte mai"
                        )
                    elif dep not in tenute:
                        tenute.append(dep)
                voce = Voce(id=vid, title=titolo, payload=carico,
                            depends_on=tenute, updated_at=time.time())
                self._voci[vid] = voce
                self._ordine.append(vid)
                create.append(voce)
            note.extend(self._spezza_cicli())
            self._salva()
        return create

    def _spezza_cicli(self) -> List[str]:
        """Toglie gli archi che chiudono un anello. Da chiamare nel lucchetto.

        Due voci che si aspettano a vicenda non partono mai, e il ventaglio
        resterebbe fermo senza dire perche'.
        """
        avvisi: List[str] = []
        visitati: set = set()
        in_pila: set = set()

        def visita(vid: str) -> None:
            visitati.add(vid)
            in_pila.add(vid)
            tenute: List[str] = []
            for dep in self._voci[vid].depends_on:
                if dep in in_pila:
                    avvisi.append(
                        f"dipendenza '{vid}' -> '{dep}' tolta: chiudeva un ciclo")
                    continue
                tenute.append(dep)
                if dep in self._voci and dep not in visitati:
                    visita(dep)
            self._voci[vid].depends_on = tenute
            in_pila.discard(vid)

        for vid in list(self._voci):
            if vid not in visitati:
                visita(vid)
        return avvisi

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

    def _dipendenze_soddisfatte(self, voce: Voce) -> bool:
        return all(
            (self._voci.get(dep) is not None and self._voci[dep].state == FATTA)
            for dep in voce.depends_on
        )

    def _blocca_gli_irraggiungibili(self) -> None:
        """Segna come bloccate le voci che non potranno mai partire.

        Una voce che dipende da qualcosa di fallito resterebbe «da fare» per
        sempre: la coda non finirebbe mai, e nessuno saprebbe perche'. Si
        propaga, perche' chi dipende da una bloccata e' bloccato a sua volta.

        Va chiamata dentro il lucchetto.
        """
        cambiato = True
        while cambiato:
            cambiato = False
            for voce in self._voci.values():
                if voce.state != DA_FARE:
                    continue
                for dep in voce.depends_on:
                    a_monte = self._voci.get(dep)
                    if a_monte is not None and a_monte.state in (FALLITA, BLOCCATA):
                        voce.state = BLOCCATA
                        voce.error = (
                            f"dipende da '{dep}', che non e' stato fatto "
                            f"({a_monte.state})"
                        )
                        voce.updated_at = time.time()
                        cambiato = True
                        break

    def claim(self, worker: str = "") -> Optional[Voce]:
        """Prende la prossima voce disponibile. None se non ce ne sono.

        Atomico rispetto agli altri consumatori: e' cio' che impedisce a due
        agenti di lavorare sullo stesso pezzo.

        Una voce le cui dipendenze non sono ancora `done` viene saltata, non
        presa: il lavoratore passa alla successiva, e quella tocchera' a chi
        arriva dopo che la dipendenza e' stata chiusa.
        """
        with self._lock:
            self._recupera_abbandonate()
            self._blocca_gli_irraggiungibili()
            for vid in self._ordine:
                voce = self._voci.get(vid)
                if voce is None or voce.state != DA_FARE:
                    continue
                if not self._dipendenze_soddisfatte(voce):
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
            self._blocca_gli_irraggiungibili()
            conteggi = {DA_FARE: 0, IN_CORSO: 0, FATTA: 0, FALLITA: 0, BLOCCATA: 0}
            for voce in self._voci.values():
                conteggi[voce.state] = conteggi.get(voce.state, 0) + 1
            pronte = sum(
                1 for v in self._voci.values()
                if v.state == DA_FARE and self._dipendenze_soddisfatte(v)
            )
            return {
                "queue_id": self.queue_id,
                "goal": self.goal,
                "total": len(self._voci),
                "todo": conteggi[DA_FARE],
                # Quante di quelle «da fare» possono partire adesso. Senza
                # questo numero, «10 da fare, 0 in corso» non distingue una
                # coda ferma da una coda che sta aspettando una dipendenza.
                "ready": pronte,
                "doing": conteggi[IN_CORSO],
                "done": conteggi[FATTA],
                "failed": conteggi[FALLITA],
                "blocked": conteggi[BLOCCATA],
                "finished": conteggi[DA_FARE] == 0 and conteggi[IN_CORSO] == 0,
            }

    def attesa_utile(self) -> bool:
        """Se conviene aspettare invece di andarsene.

        Un lavoratore che non trova niente da prendere non puo' concludere che
        il lavoro sia finito: puo' darsi che l'unica voce rimasta stia
        aspettando quella che un altro lavoratore ha in mano proprio adesso.
        Andarsene li' lascerebbe la coda a meta' con i thread gia' chiusi.
        """
        with self._lock:
            self._blocca_gli_irraggiungibili()
            in_corso = any(v.state == IN_CORSO for v in self._voci.values())
            in_attesa = any(v.state == DA_FARE for v in self._voci.values())
            return in_corso and in_attesa

    def is_finished(self) -> bool:
        return bool(self.progress()["finished"])

    def reset_failed(self) -> int:
        """Rimette in coda cio' che aveva rinunciato. Ritorna quante voci."""
        with self._lock:
            n = 0
            for voce in self._voci.values():
                if voce.state in (FALLITA, BLOCCATA):
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

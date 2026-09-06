# ==============================================================================
# core/harness/review.py — L'umano vede la modifica prima che resti
# Sigma Studio v8 — Agent Harness (kernel)
# ==============================================================================
"""Il passaggio di revisione fra una scrittura dell'agente e la sua permanenza.

Finora l'agente scriveva e poi mostrava cosa aveva scritto. Il flusso che serve
in modalita' developer e' l'opposto — propone, l'umano rivede, poi si applica —
ed e' anche la precondizione perche' far girare un run autonomo su un
repository altrui sia una scelta invece che un azzardo.

**Come e' implementato, e perche' cosi'.** La modifica viene *eseguita*, mostrata
con il suo diff reale, e **annullata se rifiutata**. L'alternativa — calcolare
il contenuto risultante senza scrivere — richiederebbe di replicare fuori dai
tool la semantica di `edit_file`: l'unicita' dell'ancora, la sostituzione
multipla, la guardia contro le riscritture che azzerano. Sarebbe una seconda
copia di quelle regole, e le seconde copie divergono: e' lo stesso difetto che
in questo progetto e' gia' costato due motori di pipeline e due Developer
Studio.

Applicare e poi eventualmente annullare ha in cambio due proprieta' che una
simulazione non puo' dare: il diff mostrato e' quello vero, e la modifica ha
gia' superato i controlli automatici — validazione della sintassi compresa —
quindi l'umano rivede qualcosa che almeno compila.

Il ripristino si appoggia ai backup che ogni scrittura crea gia' per conto suo.

**Il silenzio non e' un si'.** Se nessuno decide entro il tempo concesso, la
modifica viene annullata. Il contrario — applicare in assenza di risposta —
renderebbe la revisione una formalita' proprio nei casi in cui nessuno sta
guardando, che sono quelli per cui esiste.
"""

import difflib
import os
import threading
import time
import uuid
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from core.logger import get_logger

log = get_logger("review_gate")

#: Quanto si attende una decisione prima di annullare la modifica. Cinque
#: minuti: il tempo di leggere un diff, non quello di andare a pranzo.
REVIEW_TIMEOUT_S = 300.0

#: Esiti possibili di una proposta.
APPROVED = "approved"
REJECTED = "rejected"
TIMEOUT = "timeout"


class ReviewGate:
    """Le proposte di scrittura in attesa di giudizio, per una sessione.

    Thread-safe perche' chi propone e' il thread che esegue il run, mentre chi
    decide arriva da una richiesta HTTP diversa.
    """

    def __init__(self, timeout_s: float = REVIEW_TIMEOUT_S):
        self._timeout_s = float(timeout_s)
        self._lock = threading.RLock()
        #: id proposta -> evento su cui il run attende
        self._eventi: Dict[str, threading.Event] = {}
        #: id proposta -> decisione, anche se arrivata prima dell'attesa
        self._decisioni: Dict[str, str] = {}
        #: id proposta -> descrizione, per chi deve decidere
        self._proposte: Dict[str, Dict[str, Any]] = {}

    # -- lato agente ---------------------------------------------------------

    def open(self, path: str, diff: str, tool: str = "",
             summary: str = "") -> Dict[str, Any]:
        """Registra una modifica in attesa di giudizio e ne ritorna la scheda.

        Aprire e attendere sono due passi separati perche' fra i due ci va
        l'evento che porta la proposta all'umano: chi deve decidere ha bisogno
        dell'identificativo, e l'identificativo nasce qui. Fonderli
        significherebbe bloccare il run su una proposta che nessuno ha ancora
        visto.
        """
        proposta_id = f"rev_{uuid.uuid4().hex[:12]}"
        scheda = {
            "id": proposta_id,
            "path": path,
            "tool": tool,
            "summary": summary,
            "diff": diff,
            "proposed_at": time.time(),
        }
        with self._lock:
            self._eventi[proposta_id] = threading.Event()
            self._proposte[proposta_id] = scheda
        return dict(scheda)

    def wait(self, proposta_id: str) -> str:
        """Attende il giudizio su una proposta aperta. Ritorna l'esito."""
        pid = str(proposta_id or "").strip()
        with self._lock:
            evento = self._eventi.get(pid)
            gia_decisa = self._decisioni.get(pid)
            percorso = (self._proposte.get(pid) or {}).get("path", pid)
        if evento is None:
            # Nessuno l'ha aperta, o e' gia' stata chiusa: non e' una modifica
            # che qualcuno ha approvato, quindi non la si tiene.
            return gia_decisa or REJECTED

        ottenuta = evento.wait(timeout=self._timeout_s)

        with self._lock:
            self._eventi.pop(pid, None)
            self._proposte.pop(pid, None)
            decisione = self._decisioni.pop(pid, None)

        if not ottenuta:
            log.info("[Review] '%s' annullata: nessuna decisione entro %.0fs",
                     percorso, self._timeout_s)
            return TIMEOUT
        return decisione or REJECTED

    def propose(self, path: str, diff: str, tool: str = "",
                summary: str = "") -> Dict[str, Any]:
        """Apre e attende in un colpo solo. Comodo dove non serve l'evento."""
        scheda = self.open(path=path, diff=diff, tool=tool, summary=summary)
        return {"id": scheda["id"], "decision": self.wait(scheda["id"])}

    # -- lato umano ----------------------------------------------------------

    def decide(self, proposta_id: str, decision: str) -> bool:
        """Registra la decisione e sblocca il run. False se nessuno attendeva.

        La distinzione serve alla UI: una decisione arrivata dopo il timeout
        non e' un errore, ma non ha nemmeno avuto effetto, e dirlo evita che
        l'utente creda di aver approvato qualcosa che era gia' stato annullato.
        """
        pid = str(proposta_id or "").strip()
        esito = APPROVED if str(decision).lower().startswith("appr") else REJECTED
        with self._lock:
            self._decisioni[pid] = esito
            evento = self._eventi.get(pid)
            if evento is None:
                return False
            evento.set()
            return True

    def pending(self) -> List[Dict[str, Any]]:
        """Le proposte in attesa, senza il diff: serve a elencarle."""
        with self._lock:
            return [
                {k: v for k, v in p.items() if k != "diff"}
                for p in self._proposte.values()
            ]

    def pending_detail(self, proposta_id: str) -> Optional[Dict[str, Any]]:
        """Una proposta con il suo diff, per chi la deve leggere."""
        with self._lock:
            proposta = self._proposte.get(str(proposta_id or "").strip())
            return dict(proposta) if proposta else None

    def cancel_all(self, reason: str = "") -> None:
        """Sblocca ogni attesa con un rifiuto: si usa quando il run viene fermato.

        Lasciare un'attesa aperta terrebbe il thread fermo fino al timeout,
        molto dopo che l'utente ha premuto stop.
        """
        with self._lock:
            for pid, evento in list(self._eventi.items()):
                self._decisioni[pid] = REJECTED
                evento.set()
        if reason:
            log.info("[Review] proposte annullate: %s", reason)


# ---------------------------------------------------------------------------
# Registro per sessione
# ---------------------------------------------------------------------------
# Chi decide arriva su una richiesta HTTP diversa da quella che sta streammando
# il lavoro: senza un posto dove ritrovare il gate, il thread in attesa non e'
# raggiungibile e la revisione resta una promessa. E' lo stesso motivo per cui
# gli orchestratori in esecuzione hanno un registro.

_gates: Dict[str, ReviewGate] = {}
_gates_lock = threading.RLock()


def gate_for(session_id: str, create: bool = True) -> Optional[ReviewGate]:
    """Il gate di questa sessione, creandolo se serve."""
    chiave = str(session_id or "").strip()
    if not chiave:
        return ReviewGate() if create else None
    with _gates_lock:
        gate = _gates.get(chiave)
        if gate is None and create:
            gate = ReviewGate()
            _gates[chiave] = gate
        return gate


def release_gate(session_id: str) -> None:
    """Dimentica il gate di una sessione finita, sbloccando cio' che resta."""
    chiave = str(session_id or "").strip()
    with _gates_lock:
        gate = _gates.pop(chiave, None)
    if gate is not None:
        gate.cancel_all("sessione terminata")


def decide(session_id: str, proposta_id: str, decision: str) -> bool:
    """Registra una decisione su una proposta di una sessione."""
    gate = gate_for(session_id, create=False)
    return bool(gate and gate.decide(proposta_id, decision))


def pending(session_id: str) -> List[Dict[str, Any]]:
    gate = gate_for(session_id, create=False)
    return gate.pending() if gate else []


# ---------------------------------------------------------------------------
# Il prima e il dopo di un file
# ---------------------------------------------------------------------------


def _apri(path: str, mode: str = "r"):
    """`open` in UTF-8 in un punto solo: le riscritture fatte qui devono
    combaciare con quelle dei tool, altrimenti annullare una modifica
    cambierebbe di nascosto la codifica o i fine riga del file."""
    return open(path, mode, encoding="utf-8", newline="")


@dataclass
class FileSnapshot:
    """Com'era un file prima che un tool lo toccasse.

    Serve a due cose che devono restare coerenti: mostrare il diff vero e saper
    tornare indietro. Tenerle nello stesso oggetto evita che il diff mostrato e
    la modifica annullata riguardino stati diversi.
    """

    path: str
    #: Il testo precedente, o None se il file non esisteva.
    before: Optional[str] = None
    #: True se il contenuto non e' testo leggibile: niente diff, niente revert.
    opaque: bool = False

    @classmethod
    def take(cls, path: str) -> "FileSnapshot":
        percorso = str(path or "")
        if not percorso or not os.path.isfile(percorso):
            return cls(path=percorso, before=None)
        try:
            with _apri(percorso) as f:
                return cls(path=percorso, before=f.read())
        except (OSError, UnicodeDecodeError):
            # Binario, o illeggibile: si puo' ancora proporre la modifica, ma
            # senza fingere di poterne mostrare il diff.
            return cls(path=percorso, before=None, opaque=True)

    @property
    def existed(self) -> bool:
        return self.before is not None

    def _attuale(self) -> Optional[str]:
        if not os.path.isfile(self.path):
            return None
        try:
            with _apri(self.path) as f:
                return f.read()
        except (OSError, UnicodeDecodeError):
            return None

    def diff(self, max_lines: int = 400) -> str:
        """Il diff unificato fra il prima e lo stato attuale del file."""
        if self.opaque:
            return "(contenuto non testuale: diff non disponibile)"
        dopo = self._attuale()
        if dopo is None:
            return "(file non leggibile dopo la modifica)"
        nome = os.path.basename(self.path) or self.path
        righe = list(difflib.unified_diff(
            (self.before or "").splitlines(keepends=True),
            dopo.splitlines(keepends=True),
            fromfile=("a/" + nome) if self.existed else "/dev/null",
            tofile="b/" + nome,
            n=3,
        ))
        if not righe:
            return "(nessuna differenza)"
        if len(righe) > max_lines:
            tagliate = len(righe) - max_lines
            righe = righe[:max_lines]
            righe.append("\n... %d righe di diff omesse\n" % tagliate)
        return "".join(righe)

    def revert(self) -> bool:
        """Riporta il file a com'era. False se non e' stato possibile.

        Riscrive il testo che questo snapshot ha letto invece di passare dai
        backup: e' esattamente lo stato mostrato nel diff, mentre l'indice dei
        backup risponde alla domanda diversa «qual e' l'ultimo salvataggio».
        """
        if self.opaque:
            return False
        try:
            if not self.existed:
                if os.path.isfile(self.path):
                    os.remove(self.path)
                return True
            genitore = os.path.dirname(self.path)
            if genitore:
                os.makedirs(genitore, exist_ok=True)
            with _apri(self.path, "w") as f:
                f.write(self.before or "")
            return True
        except OSError as e:
            log.error("[Review] ripristino di '%s' fallito: %s", self.path, e)
            return False


def rejection_message(path: str, decision: str, reverted: bool) -> str:
    """Cosa dire all'agente quando la sua modifica non e' stata tenuta."""
    motivo = ("nessuno l'ha rivista entro il tempo previsto"
              if decision == TIMEOUT else "e' stata rifiutata da chi la rivede")
    coda = ("Il file e' tornato com'era."
            if reverted else
            "ATTENZIONE: non e' stato possibile annullarla, controlla il file.")
    return (
        "Modifica a '%s' NON applicata: %s. %s\n"
        "Non riproporre la stessa identica modifica. Se credi che sia "
        "necessaria, spiega nella risposta perche' lo e', oppure proponi una "
        "versione diversa che tenga conto del rifiuto." % (path, motivo, coda)
    )

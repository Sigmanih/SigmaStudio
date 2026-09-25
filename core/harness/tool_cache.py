# ==============================================================================
# core/harness/tool_cache.py — La stessa domanda, letta dal disco una volta sola
# Sigma Studio v8 — Agent Harness (kernel)
# ==============================================================================
"""Cache deterministica dei risultati dei tool di sola lettura.

Un agente che ricognisce legge lo stesso file piu' volte: la mappa dei simboli
lo nomina, la ricerca dei file citati lo ripropone, il turno dopo serve ancora.
Ogni ripetizione e' un `open` + `read` + parsing che restituisce **gli stessi
byte**, e su un run da trenta turni sono decine di letture identiche.

**Perche' una cache e non un divieto.** L'harness ha gia' una guardia che
*rifiuta* la lettura ripetuta (`inert_call_signatures` in `loop.py`): funziona,
ma paga il prezzo peggiore — toglie all'agente l'informazione di cui aveva
bisogno proprio nel momento in cui gli serviva, per punire la ripetizione. La
cache separa le due cose: la ripetizione resta un turno non produttivo (la
pressione ad agire resta), ma la risposta arriva comunque e arriva subito.

**Cosa e' una risposta ancora valida.** Dipende dal tool:

* `read_file` e i suoi alias: dalla **impronta del file**. Sotto una soglia e'
  mtime in nanosecondi, dimensione e un digest BLAKE2b del contenuto; sopra la
  soglia, solo mtime e dimensione. La differenza ha una ragione misurata: mtime
  e dimensione non distinguono due scritture *della stessa lunghezza* avvenute
  nello stesso battito dell'orologio del filesystem, e la prima stesura di
  questo modulo serviva cosi' un file appena riscritto identico riga per riga.
  Il digest toglie il problema e costa una lettura sequenziale, che su un file
  sotto la soglia e' una frazione del lavoro che il tool farebbe comunque —
  risoluzione del percorso, finestra di righe, numerazione, budget, JSON. Su un
  file grande la lettura e' invece il costo dominante, e li' resta mtime e
  dimensione: e' un compromesso, e il residuo e' una scrittura di pari
  dimensione nello stesso battito su un file oltre la soglia. A chiudere quel
  residuo c'e' `invalida(percorso)`, che il ciclo chiama a ogni scrittura
  riuscita e che conosce il percorso toccato.
* elenchi, ricerche e `find_symbol`: da un'**epoca di scrittura**. Guardano
  l'albero intero, quindi nessuna impronta di un singolo file li descrive.
  Qualunque scrittura riuscita incrementa l'epoca e li invalida tutti: e' la
  scelta conservativa, ed e' quella giusta perche' una ricerca sbagliata non
  fa lento l'agente, lo fa sbagliare.

Il `terminal` non entra mai in cache: un comando ha effetti, e due esecuzioni
identiche non sono la stessa cosa.

**Cosa questa cache non e'.** Non e' una cache di contesto: non decide cosa
finisce nella finestra e non riduce l'osservazione. Restituisce lo stesso
dizionario che il tool avrebbe prodotto, quindi chi legge dopo di lei — il
ledger, le finestre di lettura, il riassunto dell'osservazione — non sa che
esiste, ed e' cio' che la rende innestabile senza toccare il resto.
"""

from __future__ import annotations

import hashlib
import json
import os
import threading
import time
from typing import Any, Dict, List, Optional, Set, Tuple

from core.logger import get_logger

log = get_logger("tool_cache")

#: I tool il cui risultato dipende dal contenuto di un file solo.
TOOL_DI_FILE = (
    "read_file", "read", "cat", "view_file", "read_lines",
)

#: I tool il cui risultato dipende dallo stato dell'albero.
TOOL_DI_ALBERO = (
    "list_dir", "list_directory", "ls", "glob", "find_files",
    "search_code", "search", "grep", "find_symbol", "map",
    "git_status", "consult_project",
)

#: Quante voci tenere. Oltre questa soglia la cache smette di essere una cache e
#: diventa una seconda copia del repository in RAM: la parte piu' grande e' data
#: dai risultati di `search_code`, che sono elenchi di righe.
MAX_VOCI = 256

#: Oltre questa dimensione una voce non viene tenuta. Il tetto esiste perche' la
#: memoria dell'harness e' quella dell'utente: una ricerca su un albero enorme
#: puo' restituire megabyte di righe.
MAX_BYTE_PER_VOCE = 512 * 1024

#: Sotto questa dimensione l'impronta di un file include il digest del
#: contenuto, l'unico modo di accorgersi di una riscrittura *della stessa
#: lunghezza*. Sopra, il digest costerebbe una lettura del file intero, cioe'
#: proprio cio' che la cache esiste per non fare.
SOGLIA_DIGEST = 256 * 1024


def _chiave(tool: str, params: Dict[str, Any]) -> str:
    """La chiave di una chiamata: nome del tool piu' parametri normalizzati.

    I parametri sono serializzati con `sort_keys` perche' l'ordine delle chiavi
    nel JSON del modello cambia fra un turno e l'altro, e senza l'ordinamento
    la stessa chiamata produrrebbe due chiavi diverse.
    """
    try:
        corpo = json.dumps(params or {}, sort_keys=True, default=str)
    except (TypeError, ValueError):
        corpo = repr(params)
    return f"{tool}|{corpo}"


def _chiave_percorso(percorso: str) -> str:
    """Il percorso normalizzato con cui si indicizza una voce per file.

    Serve a `invalida(percorso)`: il ciclo conosce il percorso cosi' come il
    modello l'ha scritto — a volte relativo, a volte con le barre rovesciate —
    e la voce e' indicizzata sul percorso che il modello aveva scritto allora.
    """
    try:
        return os.path.normcase(os.path.abspath(percorso))
    except (OSError, ValueError):
        return os.path.normcase(percorso)


def _impronta_di_file(percorso: str) -> Optional[Tuple[Any, ...]]:
    """mtime, dimensione, e il digest del contenuto se il file e' piccolo.

    Un file che non esiste non e' una voce cacheabile: la sua assenza e' un
    fatto, ma se nasce fra un turno e l'altro la cache lo direbbe ancora
    assente. Meglio un miss.
    """
    try:
        st = os.stat(percorso)
    except OSError:
        return None
    base: Tuple[Any, ...] = (st.st_mtime_ns, st.st_size)
    if st.st_size > SOGLIA_DIGEST:
        return base
    try:
        with open(percorso, "rb") as fh:
            return base + (hashlib.blake2b(fh.read(), digest_size=16).hexdigest(),)
    except OSError:
        return None


def _percorso_di(params: Dict[str, Any]) -> str:
    for chiave in ("path", "file_path", "filepath", "target", "pattern_file"):
        valore = params.get(chiave)
        if isinstance(valore, str) and valore:
            return valore
    return ""



class ToolResultCache:
    """Cache thread-safe dei risultati dei tool di sola lettura."""

    __slots__ = ("_voci", "_ordine", "_per_percorso", "_max_voci", "_epoca",
                 "_lock", "hits", "misses", "scritture", "salvate", "rifiutate")

    def __init__(self, max_voci: int = MAX_VOCI):
        self._voci: Dict[str, Tuple[Any, Any, float]] = {}
        self._ordine: List[str] = []
        #: percorso normalizzato -> chiavi delle voci che lo riguardano. Serve
        #: a `invalida(percorso)`: senza questo indice, per buttare le voci di
        #: un file appena scritto bisognerebbe scandire tutte le chiavi e
        #: risolverne i percorsi.
        self._per_percorso: Dict[str, Set[str]] = {}
        self._max_voci = max(1, int(max_voci))
        self._epoca = 0
        self._lock = threading.RLock()
        self.hits = 0
        self.misses = 0
        self.scritture = 0
        self.salvate = 0
        self.rifiutate = 0

    # ------------------------------------------------------------- lettura

    def e_cacheabile(self, tool: str) -> bool:
        return tool in TOOL_DI_FILE or tool in TOOL_DI_ALBERO

    def get(self, tool: str, params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Il risultato gia' ottenuto per questa chiamata, se ancora valido."""
        if not self.e_cacheabile(tool):
            return None
        chiave = _chiave(tool, params)
        with self._lock:
            voce = self._voci.get(chiave)
            if voce is None:
                self.misses += 1
                return None
            risultato, impronta, _ = voce
            if not self._ancora_valida(tool, params, impronta):
                self._dimentica(chiave)
                self.misses += 1
                return None
            self._ordine.remove(chiave)
            self._ordine.append(chiave)
            self.hits += 1
        # Copia superficiale: chi riceve un hit puo' annotarlo (`cached`) senza
        # che l'annotazione finisca nella voce e quindi in ogni hit successivo.
        if isinstance(risultato, dict):
            return dict(risultato)
        return risultato

    def _ancora_valida(self, tool: str, params: Dict[str, Any], impronta: Any) -> bool:
        if tool in TOOL_DI_ALBERO:
            return impronta == self._epoca
        percorso = _percorso_di(params)
        if not percorso:
            return False
        return _impronta_di_file(percorso) == impronta

    # ------------------------------------------------------------ scrittura

    def put(self, tool: str, params: Dict[str, Any], risultato: Dict[str, Any]) -> None:
        """Memorizza un risultato riuscito. I fallimenti non si memorizzano.

        Un errore e' spesso temporaneo — un file ancora non creato, un permesso
        che arriva dopo — e servirne uno vecchio all'agente gli direbbe che cio'
        che ha appena sistemato e' ancora rotto.
        """
        if not self.e_cacheabile(tool):
            return
        if not isinstance(risultato, dict) or not risultato.get("success"):
            return

        impronta: Any
        if tool in TOOL_DI_ALBERO:
            impronta = self._epoca
        else:
            impronta = _impronta_di_file(_percorso_di(params))
            if impronta is None:
                self.rifiutate += 1
                return

        try:
            dimensione = len(json.dumps(risultato, default=str))
        except (TypeError, ValueError):
            dimensione = MAX_BYTE_PER_VOCE + 1
        if dimensione > MAX_BYTE_PER_VOCE:
            self.rifiutate += 1
            return

        chiave = _chiave(tool, params)
        with self._lock:
            self._dimentica(chiave)
            self._voci[chiave] = (dict(risultato), impronta, time.monotonic())
            self._ordine.append(chiave)
            if tool in TOOL_DI_FILE:
                self._per_percorso.setdefault(
                    _chiave_percorso(_percorso_di(params)), set()).add(chiave)
            self.salvate += 1
            while len(self._ordine) > self._max_voci:
                self._dimentica(self._ordine[0])

    def invalida(self, percorso: Optional[str] = None) -> None:
        """Il workspace e' cambiato: elenchi e ricerche non valgono piu'.

        Le letture di file **restano**, perche' la loro validita' e' l'impronta
        del file, ricontrollata a ogni `get`. Buttare anche quelle renderebbe la
        cache inutile proprio nel ciclo in cui serve — modifica, poi rileggi.

        Se pero' chi invalida conosce il percorso che ha scritto, quelle voci se
        ne vanno lo stesso. E' l'unico caso che mtime e dimensione non coprono:
        una riscrittura della stessa lunghezza nello stesso battito dell'orologio
        del filesystem. Il ciclo passa sempre il percorso quando ce l'ha.
        """
        with self._lock:
            self._epoca += 1
            self.scritture += 1
            if not percorso:
                return
            for chiave in self._per_percorso.pop(_chiave_percorso(percorso), set()):
                self._dimentica(chiave)

    def svuota(self) -> None:
        with self._lock:
            self._voci.clear()
            self._ordine.clear()
            self._per_percorso.clear()
            self._epoca += 1

    def _dimentica(self, chiave: str) -> None:
        voce = self._voci.pop(chiave, None)
        try:
            self._ordine.remove(chiave)
        except ValueError:
            pass
        if voce is None:
            return
        # L'indice per percorso va tenuto pulito, altrimenti `invalida`
        # restituisce voci che non esistono piu' e la mappa cresce senza
        # motivo per tutta la sessione.
        for insieme in list(self._per_percorso.values()):
            insieme.discard(chiave)

    # ------------------------------------------------------------ telemetria

    def stats(self) -> Dict[str, Any]:
        with self._lock:
            voci = len(self._voci)
            epoca = self._epoca
        totale = self.hits + self.misses
        return {
            "voci": voci,
            "max_voci": self._max_voci,
            "epoca": epoca,
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate_percent": round(self.hits / totale * 100, 1) if totale else 0.0,
            "salvate": self.salvate,
            "rifiutate": self.rifiutate,
            "invalidazioni": self.scritture,
        }

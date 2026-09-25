# ==============================================================================
# core/harness/prefetch.py — Le letture partono mentre il modello le chiede
# Sigma Studio v8 — Agent Harness (kernel)
# ==============================================================================
"""Esecuzione anticipata delle letture di un turno, una accanto all'altra.

Un turno di ricognizione chiede tre o quattro file che non dipendono l'uno
dall'altro: ``read_file`` su tre percorsi diversi, una ``search_code``, un
``find_symbol``. Eseguiti in fila costano la somma dei loro tempi; eseguiti
insieme costano il piu' lento. Su un albero grande la differenza fra i due e' il
tempo di un turno intero.

**Perche' non `asyncio.gather`.** Questo ciclo non e' asincrono: e'
`stream_admin_agent_turn`, un generatore **sincrono** che gira dentro un thread
del pool di `FastAPIHandlerAdapter`. Non esiste un event loop sotto, e
introdurne uno significherebbe riscrivere il ciclo. Il parallelismo qui si fa
con i thread.

**La decisione resta seriale, l'esecuzione no.** Questo e' il punto che rende
sicuro il modulo, ed e' anche il motivo per cui si chiama *prefetch* e non
"esecuzione parallela di tool". I controlli prima di un tool — permesso del
ruolo, turno forzato, guardia anti-ripetizione, finestre di lettura — sono
**stateful e ordinati**: eseguirli due alla volta renderebbe non deterministico
cio' che il ledger registra. Qui non vengono toccati. Parte in anticipo solo
l'**esecuzione**, che per un tool di sola lettura non cambia niente: rileggere
un file che poi viene rifiutato non lascia traccia.

Da qui una proprieta' che vale la pena dichiarare: **se il prefetch non parte,
il turno e' identico a prima**. Un futuro non pronto al momento in cui serve
significa eseguire il tool in linea come sempre, e un errore dentro un thread
significa eseguirlo in linea. La via di servizio e' la vecchia strada.

**Quanto rende, misurato.** Quattro letture che attendono 150 ms l'una: da
600 ms in fila a 153 ms anticipate, il 75% in meno. Quattro ``search_code`` su
un albero di tremila file: da 1285 ms a 1077 ms, il 16% in meno. La differenza
fra i due casi e' che il primo e' attesa e il secondo e' lavoro di Python, che
la GIL quasi non lascia passare in due thread. Il guadagno sta nell'attesa —
letture grandi, cache fredda, dischi lenti — non nella CPU; e un pool che non
serve a niente costa mezzo millisecondo per turno.
"""

from __future__ import annotations

import json
import threading
from concurrent.futures import Future, ThreadPoolExecutor
from typing import Any, Callable, Dict, List, Optional, Tuple

from core.logger import get_logger

log = get_logger("prefetch")

#: Quanti thread al massimo. Le letture sono I/O su disco: oltre quattro il
#: disco e' gia' saturo, e ogni thread in piu' e' un file descriptor in piu' su
#: una macchina che potrebbe essere un Raspberry Pi.
MAX_WORKER = 4

#: Oltre questo numero di tool in un turno il prefetch non parte: un turno che
#: chiede quindici file non e' ricognizione, e' un piano.
MAX_TOOL_IN_UN_TURNO = 6

#: I tool che si possono anticipare. Solo sola lettura: un prefetch non deve
#: poter scrivere su disco prima che i permessi e la revisione abbiano parlato.
ANTICIPABILI = (
    "read_file", "read", "cat", "view_file", "read_lines",
    "list_dir", "list_directory", "ls", "glob", "find_files",
    "search_code", "search", "grep", "find_symbol", "map",
    "git_status", "consult_project",
)


def tutte_anticipabili(nomi: List[str]) -> bool:
    """Vero se **tutte** le chiamate del turno sono anticipabili.

    Basta una scrittura in mezzo per rinunciare del tutto: il turno verrebbe
    comunque serializzato a un'azione sola dal ciclo, e anticipare le letture di
    un turno che il ciclo sta per ridurre e' lavoro buttato.
    """
    if not nomi or len(nomi) < 2:
        return False
    if len(nomi) > MAX_TOOL_IN_UN_TURNO:
        return False
    return all(nome in ANTICIPABILI for nome in nomi)


def _firma(tool: str, params: Dict[str, Any]) -> str:
    try:
        corpo = json.dumps(params or {}, sort_keys=True, default=str)
    except (TypeError, ValueError):
        corpo = repr(params)
    return f"{tool}|{corpo}"



class PrefetchLetture:
    """Anticipa l'esecuzione dei tool di sola lettura di un turno."""

    __slots__ = ("_pool", "_futuri", "_max_worker", "_lock",
                 "avviati", "consumati", "fallback")

    def __init__(self, max_worker: int = MAX_WORKER):
        self._pool: Optional[ThreadPoolExecutor] = None
        self._futuri: Dict[str, Tuple[Future, Dict[str, Any]]] = {}
        self._max_worker = max(1, int(max_worker))
        self._lock = threading.Lock()
        self.avviati = 0
        self.consumati = 0
        self.fallback = 0

    def avvia(self, tool: List[Dict[str, Any]], workspace_root: str,
              should_cancel: Optional[Callable[[], bool]] = None,
              active_cwd: Optional[str] = None) -> bool:
        """Mette in coda i tool del turno. Falso se non si anticipa niente.

        `dimensioni_viste` non viene passato: e' un dizionario che il ciclo
        condivide fra i tool di un turno per annotare «questo file l'hai gia'
        visto, era lungo N», e scriverlo da piu' thread sarebbe una corsa. La
        lettura resta identica nel contenuto; cambia solo quell'annotazione, che
        e' un promemoria, non un dato.
        """
        nomi = [n for n in (t.get("tool") for t in tool) if isinstance(n, str)]
        if not tutte_anticipabili(nomi):
            return False
        try:
            # Un thread per chiamata, fino al tetto del disco. Il `- 1` che
            # c'era qui riservava un posto a un consumatore che non consuma:
            # il thread del ciclo, quando un futuro non e' pronto, esegue il
            # tool da solo e non occupa il pool. Misurato su quattro letture da
            # 150 ms: 300 ms con tre thread, 150 ms con quattro.
            self._pool = ThreadPoolExecutor(
                max_workers=min(self._max_worker, len(tool)),
                thread_name_prefix="sigma-prefetch",
            )
        except Exception as exc:  # pragma: no cover - dipende dall'OS
            log.debug("[Prefetch] pool non creato (%s): turno in linea", exc)
            return False

        for invocazione in tool:
            nome = invocazione.get("tool")
            params = invocazione.get("params") or {}
            try:
                futuro = self._pool.submit(
                    _esegui, nome, params, workspace_root, should_cancel, active_cwd)
            except Exception as exc:  # pragma: no cover - dipende dall'OS
                log.debug("[Prefetch] submit fallito per %s (%s)", nome, exc)
                continue
            self._futuri[_firma(nome, params)] = (futuro, invocazione)
        self.avviati = len(self._futuri)
        return self.avviati > 0

    def risultato(self, tool: str, params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Il risultato anticipato, o None se tocca eseguirlo in linea."""
        chiave = _firma(tool, params)
        with self._lock:
            voce = self._futuri.get(chiave)
        if voce is None:
            return None
        futuro, _ = voce
        # `timeout=0` e' la scelta giusta qui: se non e' ancora pronto si esegue
        # in linea. Aspettare converte il prefetch in una serializzazione con
        # passi in piu', che e' peggio di non averlo.
        if not futuro.done():
            self.fallback += 1
            return None
        try:
            risultato = futuro.result(timeout=0)
        except Exception as exc:
            log.debug("[Prefetch] %s e' fallito nel thread (%s): eseguo in linea",
                      tool, exc)
            self.fallback += 1
            return None
        if not isinstance(risultato, dict):
            self.fallback += 1
            return None
        self.consumati += 1
        return risultato

    def chiudi(self) -> None:
        """Rilascia il pool. Va chiamato a fine turno: i thread non si riusano."""
        pool, self._pool = self._pool, None
        self._futuri = {}
        if pool is None:
            return
        try:
            pool.shutdown(wait=False, cancel_futures=True)
        except TypeError:  # pragma: no cover - Python < 3.9
            pool.shutdown(wait=False)
        except Exception as exc:  # pragma: no cover - dipende dall'OS
            log.debug("[Prefetch] chiusura del pool non riuscita: %s", exc)

    def stats(self) -> Dict[str, Any]:
        return {
            "avviati": self.avviati,
            "consumati": self.consumati,
            "fallback": self.fallback,
        }


def _esegui(tool: str, params: Dict[str, Any], workspace_root: str,
            should_cancel: Optional[Callable[[], bool]],
            active_cwd: Optional[str]) -> Dict[str, Any]:
    """Esegue un tool di sola lettura. Import locale per non creare un ciclo.

    `loop` importa questo modulo, e questo modulo ha bisogno di `loop` solo
    dentro un thread: l'import in testa chiuderebbe il cerchio.
    """
    from core.harness.loop import execute_admin_tool
    return execute_admin_tool(
        tool, params, workspace_root,
        should_cancel=should_cancel,
        dimensioni_viste=None,
        active_cwd=active_cwd,
    ) or {}

# ==============================================================================
# core/sse.py — Come si scrive su uno stream, e cosa succede quando si rompe
#
# Cinque handler avevano ognuno la propria copia di questa funzione, sei righe
# ciascuna, e le copie erano divergenti nel punto che conta: la gestione
# dell'errore. Tre usavano `except: pass`, due `except Exception: pass`.
#
# Non e' un dettaglio di stile. Il modo in cui questa applicazione ferma una
# generazione abbandonata e' far *fallire la scrittura*: quando il client chiude
# la tab, il writer solleva ClientGone, l'eccezione risale attraverso il ciclo
# di generazione e il ciclo si interrompe. Un `except` nudo cancella quel
# segnale. Il generatore prosegue fino a esaurire il budget di token, scrivendo
# in una coda che nessuno legge piu' e tenendo occupato un thread e la memoria
# di un contesto per un interlocutore che se n'e' andato.
#
# Qui la scrittura e' una sola, e distingue i due casi: un errore di
# serializzazione si registra e si va avanti, un lettore sparito si propaga.
# ==============================================================================
from __future__ import annotations

import json
import threading
from typing import Any, Callable, Dict, Optional

from core.logger import get_logger

log = get_logger(__name__)


class ClientGone(BrokenPipeError):
    """Il lettore dello stream se n'e' andato.

    Sollevata dentro il thread dell'handler quando una scrittura non ha piu'
    destinatario. Chi genera non deve intercettarla: e' il segnale di smettere,
    e il dispatcher la aspetta per chiudere ordinatamente.
    """


def sse_frame(event: Any) -> bytes:
    """Un evento nel formato che il browser si aspetta."""
    return f"data: {json.dumps(event, ensure_ascii=False)}\n\n".encode("utf-8")


def sse_writer(
    handler: Any,
    lock: Optional[threading.Lock] = None,
) -> Callable[[Any], None]:
    """Restituisce la funzione con cui un handler manda eventi al client.

    Args:
        handler: l'handler della richiesta, con il suo `wfile`.
        lock: da passare quando piu' thread scrivono sullo stesso stream —
            gli agenti in parallelo dello swarm e della ricerca lo fanno. Senza,
            due frame possono interlacciarsi e il client riceve JSON spezzato.

    La funzione restituita solleva ClientGone quando il lettore e' sparito, e
    non solleva nient'altro: un evento che non si riesce a serializzare viene
    registrato e saltato, perche' perdere un frame di avanzamento non e' un buon
    motivo per far fallire un lavoro che sta andando bene.
    """

    def scrivi(event: Any) -> None:
        try:
            frame = sse_frame(event)
        except (TypeError, ValueError) as exc:
            log.warning("[SSE] Evento non serializzabile, saltato: %s", exc)
            return

        if lock is not None:
            with lock:
                _emetti(handler, frame)
        else:
            _emetti(handler, frame)

    return scrivi


def _emetti(handler: Any, frame: bytes) -> None:
    try:
        handler.wfile.write(frame)
        handler.wfile.flush()
    except ClientGone:
        # Il segnale che ferma la generazione: passa oltre intatto.
        raise
    except (BrokenPipeError, ConnectionResetError) as exc:
        # Stessa sostanza, sollevata dal socket invece che dall'adapter.
        raise ClientGone(str(exc)) from exc
    except Exception as exc:                                # pragma: no cover
        # Qualunque altro guasto di scrittura resta un guasto dello stream: e'
        # comunque finito, e continuare a generare non serve a nessuno.
        raise ClientGone(f"Scrittura sullo stream fallita: {exc}") from exc

# ==============================================================================
# core/engine/cancellation.py — Stopping a generation that nobody is reading
#
# The client aborts its fetch when the user presses stop, or closes the tab, or
# loses the network. None of that reached the engine: the SSE writer swallowed
# the broken pipe and the generation thread ran on to max_new_tokens. On a
# single-resident-model engine that is worse than wasted electricity -- the
# abandoned answer holds the model while the next request waits for it.
#
# A token is a threading.Event with a reason attached. Nothing here imports
# torch or any runtime, so the same object travels through the transformers
# path, the llama.cpp path and the HTTP providers on every platform.
# ==============================================================================
import threading
import contextlib
import http.client
import io
import select
import socket
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Optional

from core.logger import get_logger

log = get_logger(__name__)


@contextlib.contextmanager
def cancellable_http_response(request, timeout, cancel=None):
    """Chiude il trasporto anche durante il prefill, quando non arriva ancora testo."""
    if cancel is None:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            yield response
        return
    target = urllib.parse.urlsplit(request.full_url)
    if target.scheme not in ('http', 'https'):
        raise ValueError('Protocollo HTTP non valido')
    connection_type = http.client.HTTPSConnection if target.scheme == 'https' else http.client.HTTPConnection
    connection = connection_type(target.hostname, target.port, timeout=timeout)

    class Reader(io.RawIOBase):
        def __init__(self, transport):
            self.transport = transport
            # HTTPConnection può chiudere il proprio socket dopo gli header;
            # il corpo deve conservarne un riferimento come fa socket.makefile.
            self.stream = transport.makefile('rb', buffering=0)

        def close(self):
            self.stream.close()
            super().close()

        def readable(self):
            return True

        def readinto(self, buffer):
            deadline = time.monotonic() + timeout
            while not is_cancelled(cancel):
                # Il polling evita una recv bloccata che shutdown da un altro thread
                # non sblocca tempestivamente su Windows.
                pending = getattr(self.transport, 'pending', lambda: 0)()
                ready, _, _ = select.select([self.transport], [], [], .1 if not pending else 0)
                if ready or pending:
                    return self.stream.readinto(buffer)
                if time.monotonic() >= deadline:
                    raise TimeoutError('Runtime di inferenza senza risposta')
            raise ConnectionAbortedError('Generazione annullata')

    class Response(http.client.HTTPResponse):
        def __init__(self, transport, *args, **kwargs):
            class SocketView:
                def makefile(self, *args, **kwargs):
                    return io.BufferedReader(Reader(transport))
            super().__init__(SocketView(), *args, **kwargs)

    connection.response_class = Response
    response = None
    try:
        if is_cancelled(cancel):
            raise ConnectionAbortedError('Generazione annullata')
        connection.request(request.get_method(), urllib.parse.urlunsplit(('', '', target.path or '/', target.query, '')),
                           body=request.data, headers=dict(request.header_items()))
        response = connection.getresponse()
        if response.status >= 400:
            body = response.read()
            raise urllib.error.HTTPError(request.full_url, response.status, response.reason,
                                         response.headers, io.BytesIO(body))
        yield response
    finally:
        if response is not None:
            response.close()
        connection.close()


class CancellationToken:
    """Signals, across threads, that a generation is no longer wanted."""

    __slots__ = ("_event", "_reason", "_parent_event")

    def __init__(self, parent_event=None) -> None:
        self._event = threading.Event()
        self._parent_event = parent_event
        self._reason: Optional[str] = None

    def cancel(self, reason: str = "client_disconnected") -> None:
        """Idempotent: the first reason is the one that gets reported."""
        if not self._event.is_set():
            self._reason = reason
            self._event.set()
            log.debug("[Cancel] generation cancelled: %s", reason)

    @property
    def cancelled(self) -> bool:
        if self._parent_event is not None and self._parent_event.is_set():
            self.cancel('client_disconnected')
        return self._event.is_set()

    def is_cancelled(self) -> bool:
        return self.cancelled

    @property
    def reason(self) -> Optional[str]:
        return self._reason

    def __bool__(self) -> bool:
        """``if token:`` reads as "was this cancelled"."""
        return self.cancelled

    def wait(self, timeout: Optional[float] = None) -> bool:
        return self._event.wait(timeout)


def is_cancelled(token: Any) -> bool:
    """
    Tolerant check for the many call sites that may or may not have a token.

    Callers that predate cancellation pass None, and a few pass a bare
    threading.Event; both must behave as "not cancelled" rather than raise in
    the middle of a generation loop.
    """
    if token is None:
        return False
    try:
        if isinstance(token, CancellationToken):
            return token.cancelled
        if isinstance(token, threading.Event):
            return token.is_set()
        if callable(token):
            return bool(token())
        checker = getattr(token, "cancelled", None)
        if isinstance(checker, bool):
            return checker
        if callable(checker):
            return bool(checker())
    except Exception:                       # never let this break generation
        return False
    return False


def stopping_criteria_for(token: Any):
    """
    A transformers ``StoppingCriteriaList`` that ends generation on cancel.

    Returns None when there is nothing to watch or when transformers is not
    importable here, so the caller can pass the result straight through to
    ``generate`` either way.
    """
    if token is None:
        return None
    try:
        from transformers import StoppingCriteria, StoppingCriteriaList
    except Exception:
        return None

    class _Cancelled(StoppingCriteria):
        # Called once per decoded token, so it must stay a flag read.
        def __call__(self, input_ids, scores, **kwargs) -> bool:
            return is_cancelled(token)

    return StoppingCriteriaList([_Cancelled()])

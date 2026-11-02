"""Limita i body HTTP anche quando il client non dichiara Content-Length."""
import os

from starlette.datastructures import Headers
from starlette.responses import JSONResponse


class PayloadTooLarge(ValueError):
    """Il body eccede il budget della richiesta."""


class RequestLimitMiddleware:
    def __init__(self, app, max_bytes=None):
        self.app = app
        configured = os.environ.get("SIGMA_MAX_REQUEST_BYTES", str(64 * 1024 * 1024))
        self.max_bytes = int(max_bytes if max_bytes is not None else configured)
        if self.max_bytes <= 0:
            raise ValueError("Il limite delle richieste deve essere positivo.")

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        headers = Headers(scope=scope)
        length = headers.get("content-length")
        if length is not None:
            if not length.isascii() or not length.isdecimal() or len(length) > 18:
                await JSONResponse({"error": "Content-Length non valido."}, status_code=400)(scope, receive, send)
                return
            if int(length) > self.max_bytes:
                await self._reject(scope, receive, send)
                return
        consumed = 0
        started = False

        async def limited_receive():
            nonlocal consumed
            message = await receive()
            if message["type"] == "http.request":
                consumed += len(message.get("body", b""))
                if consumed > self.max_bytes:
                    raise PayloadTooLarge("Richiesta oltre il limite configurato.")
            return message

        async def track_send(message):
            nonlocal started
            if message["type"] == "http.response.start":
                started = True
            await send(message)

        try:
            await self.app(scope, limited_receive, track_send)
        except PayloadTooLarge:
            if started:
                raise
            await self._reject(scope, receive, send)

    async def _reject(self, scope, receive, send):
        await JSONResponse({"error": "Richiesta troppo grande.", "max_bytes": self.max_bytes},
                           status_code=413)(scope, receive, send)

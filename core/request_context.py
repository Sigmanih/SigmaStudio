"""Identificativo della richiesta, propagabile a thread e lavori persistenti."""
from contextlib import contextmanager
from contextvars import ContextVar
from uuid import UUID, uuid4

_request_id = ContextVar("sigma_request_id", default="-")


def get_request_id() -> str:
    return _request_id.get()


@contextmanager
def request_scope(request_id: str):
    token = _request_id.set(request_id)
    try:
        yield request_id
    finally:
        _request_id.reset(token)


class RequestContextMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        raw = dict(scope.get("headers", [])).get(b"x-request-id", b"")
        try:
            request_id = str(UUID(raw.decode("ascii")))
        except (ValueError, UnicodeError):
            request_id = str(uuid4())
        scope.setdefault("state", {})["request_id"] = request_id

        async def traced_send(message):
            if message["type"] == "http.response.start":
                headers = [(key, value) for key, value in message.get("headers", [])
                           if key.lower() != b"x-request-id"]
                message = {**message, "headers": [*headers, (b"x-request-id", request_id.encode("ascii"))]}
            await send(message)

        with request_scope(request_id):
            await self.app(scope, receive, traced_send)

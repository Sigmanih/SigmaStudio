"""Confine HTTP: browser della macchina locale o accesso remoto autenticato."""
import hashlib
import hmac
import ipaddress
import os
import socket
import time
from urllib.parse import parse_qs

from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse, RedirectResponse


def allowed_origins() -> list[str]:
    configured = os.environ.get("SIGMA_ALLOWED_ORIGINS", "")
    return list(dict.fromkeys([
        *(f"http://{host}:{port}" for host in ("localhost", "127.0.0.1")
          for port in (3000, 5173, 8000)),
        *(origin.strip().rstrip("/") for origin in configured.split(",") if origin.strip()),
    ]))


def _local(address: str) -> bool:
    try:
        return ipaddress.ip_address(address).is_loopback
    except ValueError:
        return False


def _valid_host(host: str) -> bool:
    if host.lower() in {"localhost", socket.gethostname().lower(),
                        *(value.strip().lower() for value in os.environ.get("SIGMA_ALLOWED_HOSTS", "").split(","))}:
        return True
    try:
        return not ipaddress.ip_address(host).is_unspecified
    except ValueError:
        return False


def _session(token: str, expiry: str) -> str:
    signature = hmac.new(token.encode(), expiry.encode(), hashlib.sha256).hexdigest()
    return f"{expiry}.{signature}"


def _authorized(request: Request, token: str) -> bool:
    if not token:
        return False
    authorization = request.headers.get("authorization", "")
    if authorization.startswith("Bearer ") and hmac.compare_digest(authorization[7:].encode(), token.encode()):
        return True
    cookie = request.cookies.get("sigma_access", "")
    expiry = cookie.partition(".")[0]
    return (len(expiry) <= 12 and expiry.isascii() and expiry.isdecimal()
            and int(expiry) > time.time()
            and hmac.compare_digest(cookie.encode(), _session(token, expiry).encode()))


class HTTPAccessMiddleware:
    """ASGI puro per non interferire con disconnessione e cancellazione SSE."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        request = Request(scope, receive)
        origin = request.headers.get("origin", "").rstrip("/")
        own_origin = f"{request.url.scheme}://{request.url.netloc}"
        if not _valid_host(request.url.hostname or ""):
            await JSONResponse({"error": "Host non consentito."}, status_code=400)(scope, receive, send)
            return
        if origin and origin != own_origin and origin not in allowed_origins():
            await JSONResponse({"error": "Origine non consentita."}, status_code=403)(scope, receive, send)
            return
        token = os.environ.get("SIGMA_API_TOKEN", "")
        if request.url.path == "/api/access/login" and request.method == "POST":
            body = bytearray()
            async for chunk in request.stream():
                body.extend(chunk)
                if len(body) > 4096:
                    break
            supplied = parse_qs(body.decode("utf-8", errors="replace")).get("token", [""])[0]
            if len(body) <= 4096 and token and hmac.compare_digest(supplied.encode(), token.encode()):
                response = RedirectResponse("/", status_code=303)
                response.set_cookie("sigma_access", _session(token, str(int(time.time()) + 43200)),
                                    max_age=43200, httponly=True, secure=request.url.scheme == "https", samesite="strict")
                await response(scope, receive, send)
                return
        elif _local(request.client.host if request.client else "") or _authorized(request, token):
            await self.app(scope, receive, send)
            return
        if "text/html" in request.headers.get("accept", ""):
            response = HTMLResponse(
                '<!doctype html><html lang="it"><meta charset="utf-8"><meta name="viewport" content="width=device-width">'
                '<title>Accesso a Sigma Studio</title><main><h1>Sigma Studio</h1>'
                '<p>Accedi con il token remoto configurato sul computer che ospita lo studio.</p>'
                '<form method="post" action="/api/access/login"><label>Token di accesso '
                '<input name="token" type="password" autocomplete="current-password" required></label>'
                '<button type="submit">Accedi</button></form></main></html>', status_code=401)
        else:
            response = JSONResponse({"error": "Accesso remoto non autenticato. Configura SIGMA_API_TOKEN e usa Bearer o accedi dal browser."},
                                    status_code=401, headers={"WWW-Authenticate": "Bearer"})
        await response(scope, receive, send)

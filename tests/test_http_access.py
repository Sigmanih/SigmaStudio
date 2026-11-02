"""Il confine HTTP distingue accesso locale, browser estranei e accesso remoto."""
import time
import asyncio

from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from core.security.http_access import HTTPAccessMiddleware, _session
from core.request_context import RequestContextMiddleware, get_request_id


async def endpoint(request):
    return JSONResponse({"ok": True})


def test_traccia_richiesta_validata_e_propagata_ai_thread():
    async def traced(request):
        return JSONResponse({"request_id": get_request_id(), "thread_id": await asyncio.to_thread(get_request_id)})

    app = Starlette(routes=[Route("/", traced)])
    app.add_middleware(RequestContextMiddleware)
    caller_id = "b3aa767a-1542-4f43-99b6-76bd6134aa67"
    with TestClient(app) as c:
        response = c.get("/", headers={"X-Request-ID": caller_id})
        assert response.json() == {"request_id": caller_id, "thread_id": caller_id}
        assert response.headers["x-request-id"] == caller_id
        invalid = c.get("/", headers={"X-Request-ID": "un-valore-non-valido"})
        assert invalid.headers["x-request-id"] != "un-valore-non-valido"
    assert get_request_id() == "-"


def test_errore_imprevisto_mantiene_la_traccia_senza_esporre_dettagli_interni():
    from core.fastapi_app import unexpected_error

    async def fail(request):
        raise RuntimeError("dettaglio interno riservato")

    app = Starlette(routes=[Route("/", fail)], exception_handlers={Exception: unexpected_error})
    app.add_middleware(RequestContextMiddleware)
    with TestClient(app, raise_server_exceptions=False) as c:
        response = c.get("/")
        assert response.status_code == 500
        assert response.json()["request_id"] == response.headers["x-request-id"]
        assert "riservato" not in response.text


def client(remote=False, host="localhost"):
    app = Starlette(routes=[Route("/", endpoint, methods=["GET", "POST"])])
    app.add_middleware(HTTPAccessMiddleware)
    return TestClient(app, base_url=f"http://{host}",
                      client=("192.168.1.20" if remote else "127.0.0.1", 1234))


def test_locale_funziona_senza_token(monkeypatch):
    monkeypatch.delenv("SIGMA_API_TOKEN", raising=False)
    assert client().get("/").status_code == 200


def test_browser_estraneo_non_puo_mutare_lo_studio():
    assert client().post("/", headers={"Origin": "https://estraneo.invalid"}).status_code == 403


def test_host_estraneo_non_passa_dal_loopback():
    assert client(host="estraneo.invalid").get("/").status_code == 400


def test_remoto_richiede_token_anche_senza_configurazione(monkeypatch):
    monkeypatch.delenv("SIGMA_API_TOKEN", raising=False)
    assert client(remote=True).get("/").status_code == 401


def test_bearer_remoto(monkeypatch):
    monkeypatch.setenv("SIGMA_API_TOKEN", "segreto-di-prova")
    api = client(remote=True)
    assert api.get("/", headers={"Authorization": "Bearer errato"}).status_code == 401
    assert api.get("/", headers={"Authorization": "Bearer segreto-di-prova"}).status_code == 200


def test_accesso_browser_e_cookie_non_falsificabile(monkeypatch):
    monkeypatch.setenv("SIGMA_API_TOKEN", "segreto-di-prova")
    browser = client(remote=True)
    response = browser.post("/api/access/login", data={"token": "segreto-di-prova"}, follow_redirects=False)
    assert response.status_code == 303
    assert "HttpOnly" in response.headers["set-cookie"]
    assert browser.get("/").status_code == 200
    browser.cookies.clear()
    browser.cookies.set("sigma_access", _session("altro-segreto", str(int(time.time()) + 60)))
    assert browser.get("/").status_code == 401


def test_cookie_scaduto_viene_rifiutato(monkeypatch):
    monkeypatch.setenv("SIGMA_API_TOKEN", "segreto-di-prova")
    browser = client(remote=True)
    browser.cookies.set("sigma_access", _session("segreto-di-prova", "1"))
    assert browser.get("/").status_code == 401

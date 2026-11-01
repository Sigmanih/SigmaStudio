"""Il confine HTTP distingue accesso locale, browser estranei e accesso remoto."""
import time

from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from core.security.http_access import HTTPAccessMiddleware, _session


async def endpoint(request):
    return JSONResponse({"ok": True})


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

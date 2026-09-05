"""Test per la route POST /api/network/research_note."""
import json
from unittest.mock import patch, MagicMock, AsyncMock

import pytest
from fastapi.testclient import TestClient

# Il modulo di rete e' installabile e ignorato da git: su una macchina che
# non lo ha, questi test non hanno nulla da verificare.
pytest.importorskip(
    "core.modules.sigma_network_lab.handlers",
    reason="modulo sigma_network_lab non installato",
)


def _make_app():
    """Crea un'app FastAPI minima con la route research_note registrata."""
    from fastapi import FastAPI
    from core.modules.sigma_network_lab.handlers import router
    app = FastAPI()
    app.include_router(router, prefix="/api/network")
    return app


@pytest.fixture
def client():
    app = _make_app()
    return TestClient(app)


# ---------------------------------------------------------------------------
# Test di successo: pagina letta con successo, nota creata
# ---------------------------------------------------------------------------
@patch("core.modules.sigma_network_lab.handlers.asyncio.to_thread")
def test_research_note_success(mock_to_thread, client, tmp_path, monkeypatch):
    """Con una pagina leggibile la nota viene salvata e il percorso restituito."""
    # Simula il risultato di _fetch_for_note
    mock_to_thread.return_value = {"title": "Pagina di Test", "text": "Contenuto estratto dalla pagina."}

    # Reindirizza data/ricerche verso tmp_path per non toccare data/ reale
    import core.modules.sigma_network_lab.handlers as handlers_mod
    original_base = handlers_mod.Path("data") / "ricerche"
    monkeypatch.setattr(handlers_mod, "Path", lambda *a, **kw: tmp_path if a and a[0] == "data" else __builtins__["__import__"]("pathlib").Path(*a, **kw))

    resp = client.post("/api/network/research_note", json={"url": "https://esempio.it/articolo", "argomento": "Tema di ricerca"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert "path" in body
    assert body["title"] == "Pagina di Test"
    assert body["url"] == "https://esempio.it/articolo"
    assert body["argomento"] == "Tema di ricerca"

    # Verifica che il file esista e contenga i campi attesi
    from pathlib import Path
    saved = Path(body["path"])
    assert saved.exists()
    content = saved.read_text(encoding="utf-8")
    assert "# Pagina di Test" in content
    assert "https://esempio.it/articolo" in content
    assert "Tema di ricerca" in content
    assert "Contenuto estratto dalla pagina." in content


# ---------------------------------------------------------------------------
# Test errore: URL non raggiungibile (HTTPError)
# ---------------------------------------------------------------------------
@patch("core.modules.sigma_network_lab.handlers.asyncio.to_thread")
def test_research_note_url_unreachable(mock_to_thread, client):
    """Se la pagina non e' raggiungibile restituisce 502."""
    import urllib.error
    mock_to_thread.side_effect = urllib.error.HTTPError("https://esempio.it", 404, "Not Found", {}, None)

    resp = client.post("/api/network/research_note", json={"url": "https://esempio.it", "argomento": "Arg"})
    assert resp.status_code == 502
    assert resp.json()["success"] is False


# ---------------------------------------------------------------------------
# Test errore: pagina senza testo (ValueError)
# ---------------------------------------------------------------------------
@patch("core.modules.sigma_network_lab.handlers.asyncio.to_thread")
def test_research_note_no_text(mock_to_thread, client):
    """Se non c'e' testo estratto restituisce 422."""
    mock_to_thread.side_effect = ValueError("Nessun testo estratto dalla pagina.")

    resp = client.post("/api/network/research_note", json={"url": "https://esempio.it", "argomento": "Arg"})
    assert resp.status_code == 422
    assert resp.json()["success"] is False


# ---------------------------------------------------------------------------
# Test errore: payload mancante (400)
# ---------------------------------------------------------------------------
def test_research_note_missing_url(client):
    """Senza url restituisce 400."""
    resp = client.post("/api/network/research_note", json={"argomento": "Arg"})
    assert resp.status_code == 400
    assert resp.json()["success"] is False


def test_research_note_missing_argomento(client):
    """Senza argomento restituisce 400."""
    resp = client.post("/api/network/research_note", json={"url": "https://esempio.it"})
    assert resp.status_code == 400
    assert resp.json()["success"] is False

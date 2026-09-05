# ==============================================================================
# tests/test_network_fetch_page.py
# Test per la route POST /api/network/fetch_page del modulo sigma_network_lab
# ==============================================================================
import json
from unittest.mock import patch, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

# Il modulo di rete e' installabile e ignorato da git: su una macchina che non
# lo ha, questi test non hanno nulla da verificare e non devono far fallire la
# suite del kernel.
pytest.importorskip(
    "core.modules.sigma_network_lab.handlers",
    reason="modulo sigma_network_lab non installato",
)

from core.modules.sigma_network_lab.handlers import (  # noqa: E402
    router,
    _extract_title,
    _extract_readable_text,
    _extract_main_links,
    MAX_PAGE_SIZE_BYTES,
)


def _make_app():
    app = FastAPI()
    app.include_router(router, prefix="/api/network")
    return app


def _make_response(status_code=200, body=b"<html></html>", content_type="text/html"):
    """Crea un mock di urllib.request.urlopen che restituisce una risposta fittizia."""
    resp = MagicMock()
    resp.getcode.return_value = status_code
    resp.headers = {"Content-Type": content_type}
    resp.read.return_value = body
    resp.__enter__ = lambda s: s
    resp.__exit__ = lambda s, *a: None
    return resp


# ---------------------------------------------------------------------------
# Test unitari delle funzioni di estrazione
# ---------------------------------------------------------------------------
class TestExtractTitle:
    def test_basic_title(self):
        html = "<html><head><title>Mio Titolo</title></head><body>ok</body></html>"
        assert _extract_title(html) == "Mio Titolo"

    def test_title_with_attributes(self):
        html = '<html><head><title lang="it">Pagina</title></head></html>'
        assert _extract_title(html) == "Pagina"

    def test_no_title(self):
        html = "<html><body>no title here</body></html>"
        assert _extract_title(html) == ""

    def test_whitespace_normalized(self):
        html = "<html><head><title>  Hello   World  </title></head></html>"
        assert _extract_title(html) == "Hello World"


class TestExtractReadableText:
    def test_removes_scripts_and_styles(self):
        html = (
            "<html><head><style>body{color:red}</style></head>"
            "<body><script>var x=1;</script><p>Ciao Mondo</p></body></html>"
        )
        text = _extract_readable_text(html)
        assert "Ciao Mondo" in text
        assert "color:red" not in text
        assert "var x=1" not in text

    def test_removes_tags(self):
        html = "<html><body><h1>Titolo</h1><p>Testo</p></body></html>"
        text = _extract_readable_text(html)
        assert "Titolo" in text
        assert "Testo" in text
        assert "<h1>" not in text

    def test_html_entities(self):
        html = "<html><body>&amp; &lt;tag&gt;</body></html>"
        text = _extract_readable_text(html)
        assert "&" in text
        assert "<tag>" in text


class TestExtractMainLinks:
    def test_absolute_links(self):
        html = '<a href="https://example.com/page">Page</a>'
        links = _extract_main_links(html, "https://example.com")
        assert len(links) == 1
        assert links[0]["url"] == "https://example.com/page"
        assert links[0]["text"] == "Page"

    def test_relative_links_resolved(self):
        html = '<a href="/about">About</a>'
        links = _extract_main_links(html, "https://example.com/home")
        assert len(links) == 1
        assert links[0]["url"] == "https://example.com/about"

    def test_skips_javascript_and_mailto(self):
        html = '<a href="javascript:void(0)">JS</a><a href="mailto:x@y.z">Mail</a>'
        links = _extract_main_links(html, "https://example.com")
        assert len(links) == 0

    def test_deduplication(self):
        html = '<a href="/x">A</a><a href="/x">B</a>'
        links = _extract_main_links(html, "https://example.com")
        assert len(links) == 1

    def test_max_50_links(self):
        parts = [f'<a href="/p{i}">L{i}</a>' for i in range(80)]
        html = "".join(parts)
        links = _extract_main_links(html, "https://example.com")
        assert len(links) == 50


# ---------------------------------------------------------------------------
# Test della route POST /api/network/fetch_page
# ---------------------------------------------------------------------------
class TestFetchPageRoute:
    @pytest.fixture(autouse=True)
    def client(self):
        app = _make_app()
        return TestClient(app)

    def test_success(self, client):
        body = (
            b"<html><head><title>Test Page</title></head>"
            b"<body><p>Hello World</p>"
            b'<a href="https://example.com/link">Link</a>'
            b"</body></html>"
        )
        with patch("urllib.request.urlopen", return_value=_make_response(200, body)):
            resp = client.post(
                "/api/network/fetch_page",
                json={"url": "https://example.com"},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["title"] == "Test Page"
        assert "Hello World" in data["text"]
        assert data["links_count"] >= 1
        assert data["links"][0]["url"] == "https://example.com/link"

    def test_missing_url(self, client):
        resp = client.post("/api/network/fetch_page", json={})
        assert resp.status_code == 400
        assert resp.json()["success"] is False

    def test_invalid_json_body(self, client):
        resp = client.post(
            "/api/network/fetch_page",
            content=b"not json",
            headers={"Content-Type": "application/json"},
        )
        assert resp.status_code == 400
        assert resp.json()["success"] is False

    def test_timeout_returns_504(self, client):
        import socket
        with patch("urllib.request.urlopen", side_effect=socket.timeout("timed out")):
            resp = client.post(
                "/api/network/fetch_page",
                json={"url": "https://example.com"},
            )
        assert resp.status_code == 504
        data = resp.json()
        assert data["success"] is False
        assert "timeout" in data["error"].lower() or "Timeout" in data["error"]

    def test_http_error_returns_502(self, client):
        import urllib.error
        with patch(
            "urllib.request.urlopen",
            side_effect=urllib.error.HTTPError("https://x.com", 404, "Not Found", None, None),
        ):
            resp = client.post(
                "/api/network/fetch_page",
                json={"url": "https://example.com"},
            )
        assert resp.status_code == 502
        data = resp.json()
        assert data["success"] is False
        assert "404" in data["error"]

    def test_page_too_large(self, client):
        from core.modules.sigma_network_lab.handlers import MAX_PAGE_SIZE_BYTES as LIMIT
        big_body = b"A" * (LIMIT + 1)
        with patch("urllib.request.urlopen", return_value=_make_response(200, big_body)):
            resp = client.post(
                "/api/network/fetch_page",
                json={"url": "https://example.com"},
            )
        data = resp.json()
        assert data["success"] is False
        assert "troppo grande" in data["error"]

    def test_url_normalization_adds_https(self, client):
        body = b"<html><head><title>T</title></head><body>ok</body></html>"
        with patch("urllib.request.urlopen", return_value=_make_response(200, body)) as mock_open:
            resp = client.post(
                "/api/network/fetch_page",
                json={"url": "example.com"},
            )
        assert resp.status_code == 200
        req_obj = mock_open.call_args[0][0]
        assert req_obj.full_url.startswith("https://")

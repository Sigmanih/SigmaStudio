import json
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.modules.sigma_email_client import handlers as email_handlers


@pytest.fixture
def app(tmp_path, monkeypatch):
    """Crea un'app FastAPI con le rotte email e una config isolata in tmp_path."""
    cfg_path = tmp_path / "config" / "email_client.json"
    monkeypatch.setattr(email_handlers, "CONFIG_PATH", cfg_path)

    app = FastAPI()
    email_handlers.register_routes(app)
    return app


@pytest.fixture
def client(app):
    return TestClient(app)


def _write_config(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


def test_status_demo_mode(client, app):
    cfg = email_handlers.CONFIG_PATH
    _write_config(cfg, {"demo_mode": True})
    res = client.get("/api/email/status")
    assert res.status_code == 200
    body = res.json()
    assert body["mode"] == "demo"
    assert body["configured"] is True


def test_status_unconfigured(client, app):
    # Config vuota: non demo e server non configurato
    with patch.object(email_handlers, "_get_email_server") as mock_srv:
        mock_srv.return_value.is_configured.return_value = False
        res = client.get("/api/email/status")
    assert res.status_code == 200
    body = res.json()
    assert body["mode"] == "unconfigured"
    assert body["configured"] is False


def test_inbox_demo_mode(client, app):
    cfg = email_handlers.CONFIG_PATH
    _write_config(cfg, {"demo_mode": True})
    res = client.get("/api/email/inbox?limit=2")
    assert res.status_code == 200
    body = res.json()
    assert body["mode"] == "demo"
    assert len(body["messages"]) <= 2
    assert all("id" in m for m in body["messages"])


def test_inbox_unread_only_demo(client, app):
    cfg = email_handlers.CONFIG_PATH
    _write_config(cfg, {"demo_mode": True})
    res = client.get("/api/email/inbox?unread_only=true")
    assert res.status_code == 200
    body = res.json()
    assert all(m["unread"] for m in body["messages"])


def test_message_demo_mode(client, app):
    cfg = email_handlers.CONFIG_PATH
    _write_config(cfg, {"demo_mode": True})
    res = client.get("/api/email/message/demo-1")
    assert res.status_code == 200
    body = res.json()
    assert body["mode"] == "demo"
    assert body["message"]["id"] == "demo-1"
    assert "body_html" in body["message"]


def test_send_demo_mode(client, app):
    cfg = email_handlers.CONFIG_PATH
    _write_config(cfg, {"demo_mode": True})
    res = client.post("/api/email/send", json={
        "to": "dest@esempio.it",
        "subject": "Ciao",
        "body": "Test",
    })
    assert res.status_code == 200
    body = res.json()
    assert body["sent"] is True
    assert body["mode"] == "demo"


def test_send_missing_fields(client, app):
    cfg = email_handlers.CONFIG_PATH
    _write_config(cfg, {"demo_mode": True})
    res = client.post("/api/email/send", json={"to": ""})
    assert res.status_code == 400


def test_ai_draft_demo_mode(client, app):
    cfg = email_handlers.CONFIG_PATH
    _write_config(cfg, {"demo_mode": True})
    res = client.post("/api/email/ai-draft", json={
        "context": "progetto sigma",
        "action": "reply",
    })
    assert res.status_code == 200
    body = res.json()
    assert body["mode"] == "demo"
    assert isinstance(body["draft"], str) and len(body["draft"]) > 0


def test_config_save_demo_mode(client, app):
    res = client.post("/api/email/config", json={"demo_mode": True})
    assert res.status_code == 200
    body = res.json()
    assert body["saved"] is True
    assert body["demo_mode"] is True
    # La config e' stata scritta su disco
    assert email_handlers.CONFIG_PATH.exists()
    saved = json.loads(email_handlers.CONFIG_PATH.read_text(encoding="utf-8"))
    assert saved["demo_mode"] is True


def test_config_save_live_fields(client, app):
    with patch.object(email_handlers, "set_integration_config") as mock_sync:
        res = client.post("/api/email/config", json={
            "address": "tu@esempio.it",
            "password": "segreta",
            "smtp_host": "smtp.example.com",
            "smtp_port": 587,
            "imap_host": "imap.example.com",
            "imap_port": 993,
            "demo_mode": False,
        })
    assert res.status_code == 200
    saved = json.loads(email_handlers.CONFIG_PATH.read_text(encoding="utf-8"))
    assert saved["address"] == "tu@esempio.it"
    assert saved["smtp_host"] == "smtp.example.com"
    assert saved["demo_mode"] is False

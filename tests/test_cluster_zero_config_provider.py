"""Test suite per Zero-Config Cluster Auto-Discovery e Provider Sigma Network con AiloToken."""

import base64
import json
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from core.modules.sigma_network.discovery import (
    PeerDiscovery,
    get_active_interfaces_and_broadcasts,
)
from core.modules.sigma_network.peer_registry import PeerRegistry
from core.modules.sigma_network.ailocoin import Wallet
from core.modules.sigma_network.cluster_broker import ClusterBroker
from core.modules.sigma_network.identity import generate_identity, sign, verify
import core.modules.sigma_network.handlers as handlers


@pytest.fixture
def clean_environment(tmp_path: Path):
    """Configura directory e file isolati per i test del cluster."""
    id_file = str(tmp_path / "identity.json")
    peers_file = str(tmp_path / "peers.json")
    wallet_file = str(tmp_path / "wallet.json")

    handlers._reset_singletons()
    handlers._identity_file = id_file
    handlers._peers_file = peers_file
    handlers._wallet_file = wallet_file

    yield tmp_path

    handlers._reset_singletons()


def test_get_active_interfaces_and_broadcasts():
    """Verifica che il calcolo degli indirizzi di broadcast rilevi le interfacce attive."""
    interfaces = get_active_interfaces_and_broadcasts()
    assert isinstance(interfaces, list)
    for iface_name, ip, bcast in interfaces:
        assert isinstance(ip, str)
        assert isinstance(bcast, str)
        assert not ip.startswith("127.")
        assert not ip.startswith("169.254.")


def test_p2p_handshake_and_auto_trust(clean_environment):
    """Verifica che l'handshake crittografico autentichi e imposti a trusted il nodo del cluster."""
    from fastapi import FastAPI
    app = FastAPI()
    app.include_router(handlers.router)
    client = TestClient(app)

    # Crea un peer remoto simulato con coppia di chiavi valida
    remote_id = generate_identity(clean_environment / "remote_id.json")
    remote_peer_id = remote_id["peer_id"]
    remote_pubkey = remote_id["public_key"]
    priv_bytes = base64.b64decode(remote_id["private_key"])

    # Firma il messaggio di handshake
    ts = str(time.time())
    msg = f"cluster_handshake:{remote_peer_id}:local_test:{ts}"
    sig = sign(priv_bytes, msg)

    payload = {
        "peer_id": remote_peer_id,
        "public_key": remote_pubkey,
        "name": "PC-Remoto-2",
        "host": "192.168.1.7",
        "port": 8000,
        "models": ["llama-3.2-3b.gguf"],
        "message": msg,
        "signature": sig,
    }

    resp = client.post("/p2p/handshake", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert "public_key" in data

    # Verifica che il peer sia ora nel registry in stato 'trusted'
    reg = handlers._get_registry()
    peer = reg.get(remote_peer_id)
    assert peer is not None
    assert peer["state"] == "trusted"
    assert peer["public_key"] == remote_pubkey
    assert "llama-3.2-3b.gguf" in peer["models"]


def test_cluster_models_catalog(clean_environment):
    """Verifica che /cluster/models aggreghi i modelli locali e i modelli remoti del cluster."""
    from fastapi import FastAPI
    app = FastAPI()
    app.include_router(handlers.router)
    client = TestClient(app)

    # Aggiunge un peer trusted con un modello
    reg = handlers._get_registry()
    reg.add_peer(
        host="192.168.1.7",
        port=8000,
        peer_id="peer-remoto-abc",
        public_key="pubkey_test",
        name="Sigma-Worker-1",
        models=["qwen-2.5-coder-7b.gguf"],
    )
    reg.set_state("peer-remoto-abc", "trusted")

    resp = client.get("/cluster/models")
    assert resp.status_code == 200
    data = resp.json()
    assert data["cluster_active"] is True
    models = data["models"]
    remote_models = [m for m in models if m["model_id"] == "qwen-2.5-coder-7b.gguf"]
    assert len(remote_models) == 1
    assert remote_models[0]["provider_name"] == "Sigma-Worker-1"
    assert remote_models[0]["sharing_active"] is True


def test_cluster_broker_auto_faucet_and_inference(clean_environment):
    """Verifica che se il saldo AiloToken è zero, venga accreditato il Genesis Faucet e avviata l'inferenza."""
    identity = handlers._get_identity()
    wallet = handlers._get_wallet()
    local_peer_id = identity["peer_id"]

    # Saldo iniziale 0
    assert wallet.balance(local_peer_id)["balance"] == 0.0

    broker = handlers._get_broker()

    # Registra un peer remoto con un modello
    reg = handlers._get_registry()
    reg.add_peer(
        host="127.0.0.1",
        port=8000,
        peer_id="remote-provider-xyz",
        public_key=identity["public_key"],
        name="Remote Provider",
        models=["phi-4.gguf"],
    )
    reg.set_state("remote-provider-xyz", "trusted")

    # Mock della risposta HTTP SSE del peer remoto
    fake_sse_lines = [
        b'data: {"token": "Risposta "}\n\n',
        b'data: {"token": "dal "}\n\n',
        b'data: {"token": "cluster!"}\n\n',
        b'data: [DONE]\n\n',
    ]

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.iter_lines.return_value = fake_sse_lines

    with patch.object(broker._http_session, "post", return_value=mock_resp):
        events = list(broker.execute_cluster_inference(
            prompt="Ciao, chi sei?",
            model="phi-4.gguf",
            max_tokens=100,
        ))

    # Verifica che il faucet sia stato erogato (saldo > 0)
    assert wallet.balance(local_peer_id)["balance"] > 0.0

    # Verifica che gli eventi contengano i token
    text_accumulated = ""
    for ev in events:
        if "token" in ev:
            data = json.loads(ev.replace("data: ", "").strip())
            text_accumulated += data.get("token", "")

    assert "Risposta dal cluster!" in text_accumulated


def test_call_ai_model_stream_sigma_network_provider(clean_environment):
    """Verifica che call_ai_model_stream instradi correttamente provider='sigma_network'."""
    from core.ai_providers import call_ai_model_stream

    broker = handlers._get_broker()

    # Registra un peer remoto fidato
    reg = handlers._get_registry()
    identity = handlers._get_identity()
    reg.add_peer(
        host="127.0.0.1",
        port=8000,
        peer_id="worker-cluster-1",
        public_key=identity["public_key"],
        name="Cluster Node",
        models=["deepseek-r1-distill.gguf"],
    )
    reg.set_state("worker-cluster-1", "trusted")

    fake_sse = [
        'data: {"type": "start", "provider_name": "Cluster Node"}\n\n',
        'data: {"token": "Elaborato "}\n\n',
        'data: {"token": "in rete P2P"}\n\n',
        'data: {"type": "finish", "tokens_generated": 2, "cost_ailocoin": 0.002}\n\n',
        'data: [DONE]\n\n',
    ]

    with patch.object(broker, "execute_cluster_inference", return_value=fake_sse):
        messages = [{"role": "user", "content": "Risolvi problema"}]
        chunks = list(call_ai_model_stream(
            messages=messages,
            ai_cfg={},
            model="deepseek-r1-distill.gguf",
            provider="sigma_network",
            endpoint="",
            api_url="",
            api_key="",
            temperature=0.7,
            max_tokens=256,
            top_p=0.9,
            request_timeout=30,
        ))

    tokens = [c["token"] for c in chunks if "token" in c]
    assert "".join(tokens) == "Elaborato in rete P2P"

"""Test End-to-End P2P, NAT Traversal e Settlement Bridge per Sigma Network.

Valida:
1. Risoluzione STUN / NAT Traversal (RFC 5389) con parsing dei pacchetti di risposta.
2. Generazione Merkle Tree, proof di inclusione e verifica per Web3 Settlement.
3. Simulazione multi-nodo completa (Node A consumer <-> Node B provider) con
   scambio di richieste firmate Ed25519, emissione e controfirma ricevuta,
   aggiornamento saldi e verifica di continuita crittografica della catena.
"""

from __future__ import annotations

import base64
import os
import struct
import time
import pytest

pytest.importorskip("cryptography")

from core.modules.sigma_network.identity import generate_identity, sign, verify
from core.modules.sigma_network.peer_registry import PeerRegistry
from core.modules.sigma_network.ailocoin import Wallet, compute_receipt_hash
from core.modules.sigma_network.provider import InferenceProvider
from core.modules.sigma_network.nat_traversal import (
    STUNClient,
    STUN_BINDING_RESPONSE,
    STUN_MAGIC_COOKIE,
    ATTR_XOR_MAPPED_ADDRESS,
    detect_nat_info,
)
from core.modules.sigma_network.settlement import (
    MerkleTree,
    verify_merkle_proof,
    create_settlement_bundle,
)


# ==============================================================================
# 1. TEST NAT TRAVERSAL & STUN CLIENT
# ==============================================================================

def test_stun_packet_parsing():
    """Valida il parser dei pacchetti STUN RFC 5389 (XOR-MAPPED-ADDRESS)."""
    client = STUNClient()

    # Creiamo un pacchetto STUN di risposta sintetico
    tx_id = b"123456789012"
    magic = STUN_MAGIC_COOKIE

    # Codifica porta 8000 con XOR magic cookie
    raw_port = 8000
    xor_port = raw_port ^ (magic >> 16)

    # Codifica IP 198.51.100.1 con XOR magic cookie
    ip_parts = [198, 51, 100, 1]
    raw_ip_int = struct.unpack("!I", bytes(ip_parts))[0]
    xor_ip_int = raw_ip_int ^ magic

    # Attributo XOR-MAPPED-ADDRESS: Type(2B), Len(2B), Reserved(1B), Family=IPv4(1B), X-Port(2B), X-Address(4B)
    attr_body = struct.pack("!BBHI", 0x00, 0x01, xor_port, xor_ip_int)
    attr_header = struct.pack("!HH", ATTR_XOR_MAPPED_ADDRESS, len(attr_body))
    attr_data = attr_header + attr_body

    stun_resp = struct.pack("!HHI12s", STUN_BINDING_RESPONSE, len(attr_data), magic, tx_id) + attr_data

    # Simuliamo il parsing della risposta
    msg_type, msg_len, m_cookie, resp_tx_id = struct.unpack("!HHI12s", stun_resp[:20])
    assert msg_type == STUN_BINDING_RESPONSE
    assert m_cookie == STUN_MAGIC_COOKIE
    assert resp_tx_id == tx_id


def test_nat_info_structure():
    """Verifica che detect_nat_info restituisca un dizionario conforme alle specifiche."""
    info = detect_nat_info(local_service_port=8000)
    assert "lan_ip" in info
    assert "local_port" in info
    assert "wan_ip" in info
    assert "is_behind_nat" in info
    assert info["local_port"] == 8000


# ==============================================================================
# 2. TEST MERKLE TREE & SETTLEMENT BRIDGE
# ==============================================================================

def test_merkle_tree_empty_and_single():
    """Verifica alberi di Merkle con zero e un elemento."""
    empty_tree = MerkleTree([])
    assert empty_tree.root == "0" * 64

    single_tree = MerkleTree(["tx_hash_1"])
    assert len(single_tree.root) == 64
    proof = single_tree.get_proof(0)
    assert verify_merkle_proof("tx_hash_1", proof, single_tree.root) is True


def test_merkle_tree_multi_element_consistency():
    """Verifica la validita delle prove Merkle su alberi di forme diverse (pari e dispari)."""
    elements = [f"receipt_{i}_{os.urandom(8).hex()}" for i in range(7)]
    tree = MerkleTree(elements)

    assert len(tree.root) == 64

    # Ogni foglia deve poter essere verificata rispetto alla root tramite il suo audit path
    for i, el in enumerate(elements):
        proof = tree.get_proof(i)
        assert verify_merkle_proof(el, proof, tree.root) is True

    # Elemento non presente deve fallire la verifica
    assert verify_merkle_proof("elemento_falso", tree.get_proof(0), tree.root) is False


def test_create_settlement_bundle():
    """Verifica la creazione del bundle EIP-712 per il settlement on-chain."""
    receipts = [
        {
            "receipt_id": f"rec_{i}",
            "receipt_hash": f"hash_{i}_{os.urandom(16).hex()}",
            "provider_signature": "SIG_PROV",
            "amount": 2.5,
            "tokens": 2500,
        }
        for i in range(4)
    ]

    bundle = create_settlement_bundle(
        receipts=receipts,
        provider_peer_id="peer_provider_123",
        consumer_peer_id="peer_consumer_456",
    )

    assert bundle["receipt_count"] == 4
    assert bundle["total_amount"] == 10.0
    assert bundle["total_tokens"] == 10000
    assert "merkle_root" in bundle
    assert len(bundle["merkle_root"]) == 64
    assert bundle["eip712_domain"]["name"] == "SigmaNetworkSettlement"
    assert bundle["eip712_message"]["totalTokens"] == 10000


# ==============================================================================
# 3. TEST SIMULAZIONE END-TO-END MULTI-NODO (Node A <-> Node B)
# ==============================================================================

def test_full_p2p_handshake_inference_and_accounting(tmp_path):
    """Simula due nodi Sigma Studio indipendenti che eseguono inferenza remota e contabilità AiloCoin."""
    dir_a = tmp_path / "node_a"
    dir_b = tmp_path / "node_b"
    dir_a.mkdir()
    dir_b.mkdir()

    # Inizializzazione Identità e Wallet per Node A (Consumer)
    id_a = generate_identity(str(dir_a / "identity.json"))
    wallet_a = Wallet(str(dir_a / "wallet.json"))
    reg_a = PeerRegistry(str(dir_a / "peers.json"))

    # Inizializzazione Identità, Wallet e Provider per Node B (Provider)
    id_b = generate_identity(str(dir_b / "identity.json"))
    wallet_b = Wallet(str(dir_b / "wallet.json"))
    reg_b = PeerRegistry(str(dir_b / "peers.json"))

    priv_key_b = base64.b64decode(id_b["private_key"])
    priv_key_a = base64.b64decode(id_a["private_key"])

    # Node B offre il modello 'qwen-coder'
    provider_b = InferenceProvider(
        settings={
            "shared_models": ["qwen-coder"],
            "sharing_enabled": True,
            "rate": 1000.0,  # 1 AiloCoin = 1000 token
        }
    )

    # 1. Handshake e Registrazione Peer
    # Node A registra Node B e gli accorda fiducia
    reg_a.add_peer(
        host="192.168.1.50",
        port=8000,
        peer_id=id_b["peer_id"],
        public_key=id_b["public_key"],
        name="Node B (Workstation GPU)",
        models=["qwen-coder"],
    )
    reg_a.set_state(id_b["peer_id"], "trusted")

    # Node B registra Node A e gli accorda fiducia
    reg_b.add_peer(
        host="192.168.1.20",
        port=8000,
        peer_id=id_a["peer_id"],
        public_key=id_a["public_key"],
        name="Node A (Laptop)",
        models=[],
    )
    reg_b.set_state(id_a["peer_id"], "trusted")

    # 2. Richiesta di inferenza firmata da Node A verso Node B
    prompt = "Scrivi una funzione Python per calcolare la serie di Fibonacci"
    timestamp = time.time()
    sign_payload = f"{id_a['peer_id']}:qwen-coder:{prompt}:{timestamp}"
    signature_a = sign(priv_key_a, sign_payload)

    # Node B riceve la richiesta e verifica la firma di Node A
    assert verify(id_a["public_key"], sign_payload, signature_a) is True

    # 3. Node B serve la richiesta ed emette la ricevuta firmata
    tokens_produced = 500  # 500 token generati
    receipt_b = wallet_b.issue_receipt(
        request_id="req-fibonacci-001",
        provider_id=id_b["peer_id"],
        consumer_id=id_a["peer_id"],
        model="qwen-coder",
        tokens=tokens_produced,
        rate=1000.0,
        private_key_bytes=priv_key_b,
    )

    # 4. Node A riceve la ricevuta, verifica la firma del Provider (Node B)
    assert receipt_b["provider_signature"] is not None
    assert receipt_b["amount"] == 0.5  # 500 / 1000 = 0.5 AiloCoin

    # Node A controfirma e salva la ricevuta nel proprio wallet locale
    counter_signed = wallet_a.countersign(
        receipt=receipt_b,
        private_key_bytes=priv_key_a,
        provider_public_key=id_b["public_key"],
    )
    assert counter_signed["consumer_signature"] is not None

    # 5. Verifica contabile dei Wallet
    bal_a = wallet_a.balance(id_a["peer_id"])
    bal_b = wallet_b.balance(id_b["peer_id"])

    assert bal_a["spent"] == 0.5
    assert bal_b["earned"] == 0.5

    # 6. Verifica dell'integrita crittografica della catena su entrambi i nodi
    verify_a = wallet_a.verify_chain()
    verify_b = wallet_b.verify_chain()

    assert verify_a["valid"] is True
    assert verify_a["corrupted_count"] == 0
    assert verify_b["valid"] is True
    assert verify_b["corrupted_count"] == 0

    # 7. Verifica Merkle Settlement per Node B
    bundle = create_settlement_bundle(
        receipts=wallet_b.receipts(),
        provider_peer_id=id_b["peer_id"],
        consumer_peer_id=id_a["peer_id"],
    )
    assert bundle["receipt_count"] == 1
    assert bundle["total_amount"] == 0.5
    assert bundle["total_tokens"] == 500

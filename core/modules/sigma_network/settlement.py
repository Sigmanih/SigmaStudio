"""Web3 Export & Merkle Settlement Bridge per AiloCoin.

Permette di raggruppare ricevute di inferenza firmate reciprocamente in un
albero di Merkle (Merkle Tree) verificabile per il settlement cumulativo su
blockchain (EVM / Base / Arbitrum o Solana).
"""

from __future__ import annotations

import hashlib
import json
import time
from typing import Any, Dict, List, Optional, Tuple


def _hash_leaf(data: str) -> str:
    """Hash canonico di una foglia Merkle con prefisso 0x00 (anti-preimage attack)."""
    return hashlib.sha256(b"\x00" + data.encode("utf-8")).hexdigest()


def _hash_nodes(left: str, right: str) -> str:
    """Hash di due nodi interni Merkle ordinati alfabeticamente per determinismo."""
    ordered = sorted([left, right])
    combined = ordered[0].encode("utf-8") + ordered[1].encode("utf-8")
    return hashlib.sha256(b"\x01" + combined).hexdigest()


class MerkleTree:
    """Implementazione crittografica di Merkle Tree per ricevute di calcolo."""

    def __init__(self, elements: List[str]) -> None:
        self.elements = list(elements)
        self.leaves = [_hash_leaf(e) for e in elements]
        self.levels: List[List[str]] = []
        if self.leaves:
            self._build_tree()

    def _build_tree(self) -> None:
        current = list(self.leaves)
        self.levels.append(current)

        while len(current) > 1:
            next_level = []
            for i in range(0, len(current), 2):
                left = current[i]
                right = current[i + 1] if i + 1 < len(current) else current[i]
                next_level.append(_hash_nodes(left, right))
            current = next_level
            self.levels.append(current)

    @property
    def root(self) -> str:
        """Root hash del Merkle Tree."""
        if not self.levels:
            return "0" * 64
        return self.levels[-1][0]

    def get_proof(self, index: int) -> List[Dict[str, str]]:
        """Restituisce il percorso di prova (audit path) per la foglia all'indice dato."""
        if index < 0 or index >= len(self.leaves):
            raise IndexError("Indice foglia fuori intervallo")

        proof = []
        curr_idx = index

        for level in self.levels[:-1]:
            is_right_node = curr_idx % 2 == 1
            sibling_idx = curr_idx - 1 if is_right_node else curr_idx + 1

            if sibling_idx < len(level):
                sibling_hash = level[sibling_idx]
            else:
                sibling_hash = level[curr_idx]

            proof.append({
                "position": "left" if is_right_node else "right",
                "hash": sibling_hash,
            })
            curr_idx = curr_idx // 2

        return proof


def verify_merkle_proof(element: str, proof: List[Dict[str, str]], root: str) -> bool:
    """Verifica che un elemento appartenga al Merkle Root fornito tramite la prova."""
    current = _hash_leaf(element)
    for step in proof:
        sibling = step["hash"]
        current = _hash_nodes(current, sibling)
    return current == root


def create_settlement_bundle(
    receipts: List[Dict[str, Any]],
    provider_peer_id: str,
    consumer_peer_id: str,
) -> Dict[str, Any]:
    """Crea un bundle di settlement on-chain per un batch di ricevute firmate."""
    # Filtra ricevute valide con firme
    valid_receipts = [
        r for r in receipts
        if r.get("provider_signature") and r.get("receipt_hash")
    ]

    hashes = [r["receipt_hash"] for r in valid_receipts]
    tree = MerkleTree(hashes)

    total_amount = sum(float(r.get("amount", 0.0)) for r in valid_receipts)
    total_tokens = sum(int(r.get("tokens", 0)) for r in valid_receipts)

    proofs = {
        r["receipt_hash"]: tree.get_proof(idx)
        for idx, r in enumerate(valid_receipts)
    }

    bundle = {
        "settlement_id": f"settle_{int(time.time())}_{tree.root[:12]}",
        "created_at": time.time(),
        "provider_peer_id": provider_peer_id,
        "consumer_peer_id": consumer_peer_id,
        "receipt_count": len(valid_receipts),
        "total_amount": round(total_amount, 6),
        "total_tokens": total_tokens,
        "merkle_root": tree.root,
        "receipt_proofs": proofs,
        # Standard EIP-712 Typed Data format pronto per smart contract Solidity
        "eip712_domain": {
            "name": "SigmaNetworkSettlement",
            "version": "1.0",
            "chainId": 8453,  # Base Mainnet o L2 EVM compatibile
            "verifyingContract": "0x0000000000000000000000000000000000000000",
        },
        "eip712_message": {
            "merkleRoot": "0x" + tree.root,
            "totalTokens": total_tokens,
            "totalAmount": int(total_amount * 1e18),  # 18 decimali standard ERC-20
            "provider": provider_peer_id,
            "consumer": consumer_peer_id,
            "timestamp": int(time.time()),
        },
    }
    return bundle

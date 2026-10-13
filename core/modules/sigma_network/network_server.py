"""Sigma Network — MCP Server per Agenti e Swarm di Sigma Studio.

Consente agli agenti intelligenti del kernel e dei moduli di interagire
con la rete P2P decentralizzata di Ailo Network:
- Rilevamento peer e topologia della rete / radar
- Inferenza distribuita sul cluster di modelli cooperativi con micro-pagamento AiloToken
- Gestione del wallet ed emissione / verifica di ricevute crittografiche Ed25519
- Proof-of-Useful-Work (PoUW) mining e federated learning aggregation
"""

from __future__ import annotations

import json
from typing import Any, Dict, Optional

from core.logger import get_logger
from core.mcp.base_server import BaseMCPServer
from core.mcp.governance import SAFE, SENSITIVE

from .handlers import (
    _get_broker,
    _get_identity,
    _get_mining,
    _get_registry,
    _get_settings,
    _get_wallet,
    _get_aggregator,
)

log = get_logger(__name__)


class SigmaNetworkMCPServer(BaseMCPServer):
    """MCP Server exposing decentralized P2P cluster and AiloCoin capabilities to agents."""

    def __init__(self) -> None:
        super().__init__(
            name="Sigma Network (Ailo P2P)",
            version="1.0.0",
            description="Rete P2P decentralizzata, cluster di modelli federati, AiloCoin e PoUW neural mining.",
        )

        self.register_tool(
            name="p2p_list_peers",
            description="Elenca tutti i peer noti nella rete P2P (online, offline, latenza stimata, modelli offerti e fiducia).",
            input_schema={"type": "object", "properties": {}},
            handler=self._tool_list_peers,
            safety=SAFE,
            category="network",
        )

        self.register_tool(
            name="p2p_get_network_map",
            description="Ottiene la mappa topologica radar della rete P2P con coordinate polari, latenze e clustering dei nodi.",
            input_schema={"type": "object", "properties": {}},
            handler=self._tool_get_network_map,
            safety=SAFE,
            category="network",
        )

        self.register_tool(
            name="p2p_cluster_infer",
            description="Invia un prompt al cluster decentralizzato P2P di Sigma Network, selezionando il nodo ottimale o locale e pagando in AiloTokens con ricevuta firmata.",
            input_schema={
                "type": "object",
                "properties": {
                    "prompt": {"type": "string", "description": "Il prompt o task da completare via modello cooperativo."},
                    "model": {"type": "string", "description": "Nome o architettura del modello richiesto (es. 'ailo-152m', 'deepseek-r1', 'qwen-coder')."},
                    "max_tokens": {"type": "integer", "description": "Massimo numero di token da generare (default 512).", "default": 512},
                    "preferred_peer_id": {"type": "string", "description": "ID del peer preferito se noto, o None per routing automatico."},
                },
                "required": ["prompt", "model"],
            },
            handler=self._tool_cluster_infer,
            safety=SAFE,
            category="network",
        )

        self.register_tool(
            name="p2p_wallet_balance",
            description="Controlla lo stato del wallet AiloCoin locale (saldo spendibile, guadagnato come provider, minato, speso, e integrità del ledger crittografico).",
            input_schema={"type": "object", "properties": {}},
            handler=self._tool_wallet_balance,
            safety=SAFE,
            category="network",
        )

        self.register_tool(
            name="p2p_mine_block",
            description="Esegue un ciclo di Proof-of-Useful-Work (PoUW) neurale, calcolando gradienti per la rete e accreditando reward in AiloCoin.",
            input_schema={
                "type": "object",
                "properties": {
                    "intensity": {"type": "integer", "description": "Livello intensità calcolo (1=basso, 2=medio, 3=alto)", "default": 1}
                },
            },
            handler=self._tool_mine_block,
            safety=SAFE,
            category="network",
        )

        self.register_tool(
            name="p2p_federated_status",
            description="Restituisce lo stato del Federated Learning distribuito: versione del modello globale AILO, gradienti accumulati e consenso.",
            input_schema={"type": "object", "properties": {}},
            handler=self._tool_federated_status,
            safety=SAFE,
            category="network",
        )

    def _tool_list_peers(self, **kwargs) -> Dict[str, Any]:
        registry = _get_registry()
        peers = registry.all_peers()
        return {
            "total_peers": len(peers),
            "peers": peers,
        }

    def _tool_get_network_map(self, **kwargs) -> Dict[str, Any]:
        identity = _get_identity()
        registry = _get_registry()
        local_info = {
            "peer_id": identity["peer_id"],
            "name": _get_settings().get("display_name", "Local Node"),
            "models": _get_settings().get("shared_models", []),
            "sharing_enabled": _get_settings().get("sharing_enabled", False),
        }
        return registry.get_network_map(local_info)

    def _tool_cluster_infer(
        self,
        prompt: str,
        model: str,
        max_tokens: int = 512,
        preferred_peer_id: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        broker = _get_broker()
        gen = broker.execute_cluster_inference(
            prompt=prompt,
            model=model,
            max_tokens=max_tokens,
            preferred_peer_id=preferred_peer_id,
        )

        accumulated_text = []
        receipt_info = None
        error_msg = None

        for chunk in gen:
            # chunk è formato SSE: "data: ...\n\n"
            lines = chunk.strip().split("\n")
            for line in lines:
                if line.startswith("data: "):
                    payload_str = line[6:].strip()
                    try:
                        data = json.loads(payload_str)
                        if "token" in data:
                            accumulated_text.append(data["token"])
                        if "receipt" in data:
                            receipt_info = data["receipt"]
                        if "error" in data:
                            error_msg = data["error"]
                    except Exception:
                        pass

        full_response = "".join(accumulated_text)
        return {
            "success": error_msg is None,
            "error": error_msg,
            "response": full_response,
            "model": model,
            "receipt": receipt_info,
            "tokens_generated": len(accumulated_text),
        }

    def _tool_wallet_balance(self, **kwargs) -> Dict[str, Any]:
        identity = _get_identity()
        wallet = _get_wallet()
        totals = wallet.balance(identity["peer_id"])
        verification = wallet.verify_chain()
        return {
            "peer_id": identity["peer_id"],
            "balance": totals["balance"],
            "earned_as_provider": totals["earned"],
            "mined_via_pouw": totals["mined"],
            "faucet_received": totals["faucet"],
            "spent_on_inference": totals["spent"],
            "total_transactions": len(wallet.receipts()),
            "chain_valid": verification["valid"],
            "chain_length": verification["chain_length"],
        }

    def _tool_mine_block(self, intensity: int = 1, **kwargs) -> Dict[str, Any]:
        miner = _get_mining()
        miner.set_intensity(intensity)
        step_result = miner.compute_step_now()
        status = miner.get_status()
        return {
            "step_result": step_result,
            "status": status,
        }

    def _tool_federated_status(self, **kwargs) -> Dict[str, Any]:
        aggregator = _get_aggregator()
        return aggregator.get_state()

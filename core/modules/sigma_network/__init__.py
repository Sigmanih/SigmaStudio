"""Sigma Network — rete peer-to-peer per inferenza distribuita.

Espone il router HTTP del modulo. La registrazione MCP e' dichiarata ma non
ancora attiva: il server MCP richiede di collegare registry, wallet e broker
con le loro API reali, ed e' preferibile non esporre tool agli agenti finche'
non fanno quello che dichiarano di fare.
"""

from core.logger import get_logger
from .handlers import router

log = get_logger("sigma_network")

__all__ = ["router", "register_mcp"]


def register_mcp(mcp_hub) -> None:
    """Registra il server MCP di Sigma Network nell'hub MCP del kernel."""
    try:
        from .network_server import SigmaNetworkMCPServer
        mcp_hub.register_server(SigmaNetworkMCPServer)
        log.info("[sigma_network] Sigma Network MCP Server registrato con successo nell'MCP Hub.")
    except Exception as e:
        log.warning(f"[sigma_network] Sigma Network MCP Server non registrato: {e}")


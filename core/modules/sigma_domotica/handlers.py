from .homeassistant_server import HomeAssistantMCPServer

def register_mcp(mcp_hub):
    """Register HomeAssistant MCP server with the hub."""
    server = HomeAssistantMCPServer()
    mcp_hub.register_server("homeassistant", server)
    return server

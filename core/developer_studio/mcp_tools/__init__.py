# ==============================================================================
# core/developer_studio/mcp_tools/__init__.py
# Sigma Studio v8 — Developer Studio MCP Tool Servers
# ==============================================================================
"""MCP servers specific to the Developer Studio: Git, Lint, Test.

Each server extends BaseMCPServer and is registered in the MCP Hub
at startup, making its tools available to all agents — not just the
admin agent — through the unified governance pipeline.
"""

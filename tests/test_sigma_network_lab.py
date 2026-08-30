"""Unit tests for sigma_network_lab module:
- Network status & connectivity
- Web Search scraping (DuckDuckGo & Wikipedia)
- HTTP API Request builder
- DNS Diagnostics
- Ping & Latency tester
- Network MCP server tools
"""
import pytest
import asyncio
import json
from fastapi import FastAPI
from core.modules.sigma_network_lab.handlers import (
    router, register_routes, register_mcp,
    get_network_status, execute_dns_lookup, execute_ping_test,
    execute_web_search, execute_http_request
)
from core.modules.sigma_network_lab.network_server import NetworkMCPServer


def test_network_status_endpoint():
    """Checks that the network status endpoint returns host, IPs and connectivity."""
    response = asyncio.run(get_network_status())
    assert response.status_code == 200
    data = json.loads(response.body.decode("utf-8"))
    assert data["success"] is True
    assert "hostname" in data
    assert isinstance(data["local_ips"], list)
    assert "internet_online" in data
    assert "services" in data


def test_dns_lookup_endpoint():
    """Checks DNS lookup resolution for known host."""
    class MockReq:
        method = "GET"
        query_params = {"domain": "1.1.1.1"}

    response = asyncio.run(execute_dns_lookup(MockReq()))
    assert response.status_code == 200
    data = json.loads(response.body.decode("utf-8"))
    assert data["success"] is True
    assert data["domain"] == "1.1.1.1"
    assert len(data["records"]) >= 1
    assert any(r["type"] in ("A", "PTR (Reverse DNS)") for r in data["records"])


def test_ping_endpoint():
    """Checks TCP socket ping latency measurement."""
    class MockPingReq:
        method = "GET"
        query_params = {"host": "1.1.1.1", "port": "80", "count": "2"}

    response = asyncio.run(execute_ping_test(MockPingReq()))
    assert response.status_code == 200
    data = json.loads(response.body.decode("utf-8"))
    assert data["transmitted"] == 2
    assert data["host"] == "1.1.1.1"
    assert "samples" in data
    assert len(data["samples"]) == 2


def test_web_search_endpoint():
    """Checks Web Search endpoint with wikipedia engine."""
    class MockSearchReq:
        method = "GET"
        query_params = {"query": "Python", "engine": "wikipedia", "max_results": "3"}

    response = asyncio.run(execute_web_search(MockSearchReq()))
    assert response.status_code == 200
    data = json.loads(response.body.decode("utf-8"))
    assert data["success"] is True
    assert data["query"] == "Python"
    assert "results" in data


def test_http_request_endpoint():
    """Checks HTTP request builder execution."""
    class MockHttpReq:
        method = "POST"
        async def json(self):
            return {
                "method": "GET",
                "url": "https://httpbin.org/get",
                "headers": {"Accept": "application/json"}
            }

    # Should execute or gracefully report result/timeout without crash
    response = asyncio.run(execute_http_request(MockHttpReq()))
    assert response.status_code == 200
    data = json.loads(response.body.decode("utf-8"))
    assert "latency_ms" in data
    assert "method" in data


def test_network_mcp_server():
    """Checks NetworkMCPServer registration, tools, and resources."""
    server = NetworkMCPServer()
    assert server.name == "Network MCP"
    tools_dict = getattr(server, "_tools", {}) or getattr(server, "tools", {})
    assert "search_web" in tools_dict
    assert "fetch_web_page" in tools_dict
    assert "http_request" in tools_dict
    assert "resolve_dns" in tools_dict
    assert "ping_node" in tools_dict
    assert "discover_peers" in tools_dict

    # Test local resolve_dns tool
    dns_tool = server._handle_resolve_dns(domain="1.1.1.1")
    assert dns_tool.get("success") is True

    # Test local ping_node tool
    ping_tool = server._handle_ping_node(node_ip="127.0.0.1")
    assert ping_tool.get("success") is True


def test_register_routes_on_app():
    """Checks router registration on FastAPI."""
    app = FastAPI()
    register_routes(app)
    # Check that router is mounted
    assert len(app.routes) > 4
    inc = app.routes[-1]
    orig = getattr(inc, "original_router", None) or inc
    paths = [getattr(r, "path", "") for r in getattr(orig, "routes", [])]
    assert any("/status" in p or "/search" in p for p in paths)

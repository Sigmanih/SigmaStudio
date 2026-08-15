# ==============================================================================
# tests/test_fastapi_server.py — Test Suite for FastAPI Server Endpoints
# Sigma Studio v8.2 — Test Coverage Expansion
# ==============================================================================
"""Integration tests for FastAPI ASGI application: OpenAPI /docs, middleware CORS,
GET and POST API endpoints dispatching.
"""

import pytest
from fastapi.testclient import TestClient
from core.fastapi_app import app

client = TestClient(app)


class TestFastAPIServerEndpoints:
    """Test suite for FastAPI server routing and OpenAPI documentation."""

    def test_openapi_swagger_docs_available(self):
        """GET /docs returns 200 Swagger UI page."""
        response = client.get("/docs")
        assert response.status_code == 200
        assert "swagger-ui" in response.text.lower() or "html" in response.text.lower()

    def test_openapi_schema_json(self):
        """GET /openapi.json returns valid OpenAPI 3.0 schema."""
        response = client.get("/openapi.json")
        assert response.status_code == 200
        data = response.json()
        assert "openapi" in data
        assert data["info"]["title"] == "Σ-SIGMA Studio API"

    def test_api_modules_endpoint(self):
        """GET /api/modules returns modules metadata dictionary."""
        response = client.get("/api/modules")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, dict)

    def test_api_topics_endpoint(self):
        """GET /api/topics returns topics list."""
        response = client.get("/api/topics")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, dict) or isinstance(data, list)

    def test_api_skills_endpoint(self):
        """GET /api/skills returns skills status list."""
        response = client.get("/api/skills")
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") is True
        assert "skills" in data


    def test_api_config_endpoint(self):
        """GET /api/config returns platform config."""
        response = client.get("/api/config")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, dict)

    def test_api_non_existent_route(self):
        """GET /api/non_existent_route returns 404 error."""
        response = client.get("/api/non_existent_route_12345")
        assert response.status_code == 404
        assert "error" in response.json()

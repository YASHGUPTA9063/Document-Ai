"""
API Integration Tests
======================
Tests for the FastAPI REST endpoints using httpx TestClient.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.fixture
def client():
    """
    A TestClient over the real app with startup stubbed out.

    Provider construction, the health monitor and the DINOv2 preload all moved
    into bootstrap.init_platform(), so that single call is what has to be
    stubbed here - patching main.ProviderRegistry no longer works, because
    main.py does not import it any more. platform_state() is stubbed too,
    since /health and /ready both read it.

    The database is NOT stubbed: conftest.py points DATABASE_URL at a scratch
    SQLite file and creates the schema, so the document and claim endpoints run
    real queries. They go through SQLAlchemy directly rather than through a
    module-level `db` object, so a mock there would test nothing.
    """
    from fastapi.testclient import TestClient

    fake_state = {
        "execution_mode": "inline",
        "deployment_name": "test-deployment",
        "providers": {"llm": ["mistral"]},
        "provider_health": {},
        "circuit_breakers": {},
        "agents": {
            "workflow_id_bound": True,
            "deployment_name": "test-deployment",
            "required_missing": [],
            "bound": 0,
            "total_optional": 0,
            "degraded_capabilities": {},
        },
    }

    patches = [
        patch("main.init_platform", new=AsyncMock(return_value={})),
        patch("main.shutdown_platform", new=AsyncMock(return_value=None)),
        patch("main.assert_agent_bindings", new=MagicMock()),
        patch("main.assert_workflow_binding", new=MagicMock()),
        patch("main.platform_state", new=MagicMock(return_value=fake_state)),
    ]
    for p in patches:
        p.start()
    try:
        from main import app
        with TestClient(app) as c:
            yield c
    finally:
        for p in reversed(patches):
            p.stop()


class TestHealthEndpoint:
    """Tests for the /health endpoint."""

    def test_health_returns_200(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        # /health reports how work reaches Mistral Studio, so an operator can
        # tell a queue deployment from an inline one without reading env vars.
        assert "execution_mode" in data
        assert "circuit_breakers" in data


class TestReadyEndpoint:
    """Tests for the /ready endpoint."""

    def test_ready_reports_checks(self, client):
        with patch("main.db_ping", new=AsyncMock(return_value=True)):
            response = client.get("/ready")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ready"
        assert data["checks"]["database"] is True
        assert data["checks"]["required_agents_bound"] is True

    def test_ready_is_503_when_database_is_down(self, client):
        """Readiness must fail closed so traffic stops being routed here."""
        with patch("main.db_ping", new=AsyncMock(return_value=False)):
            response = client.get("/ready")
        assert response.status_code == 503
        assert response.json()["status"] == "not_ready"


class TestDocumentEndpoints:
    """Tests for /api/v1/documents endpoints."""

    def test_list_documents(self, client):
        response = client.get("/api/v1/documents")
        assert response.status_code == 200

    def test_status_404_for_unknown_document(self, client):
        response = client.get("/api/v1/documents/does-not-exist/status")
        assert response.status_code == 404

    def test_retry_404_for_unknown_document(self, client):
        response = client.post("/api/v1/documents/does-not-exist/retry")
        assert response.status_code == 404


class TestClaimEndpoints:
    """Tests for /api/v1/claims endpoints."""

    def test_list_claims(self, client):
        response = client.get("/api/v1/claims")
        assert response.status_code == 200


class TestRouteSurface:
    """
    The canonical surface is /api/v1; the flat paths an older frontend build
    calls are aliases onto the same handlers while ENABLE_LEGACY_ROOT_ROUTES
    is on. Both must resolve, and to the same endpoint function.
    """

    def test_canonical_and_legacy_paths_share_a_handler(self, client):
        from fastapi.routing import APIRoute

        routes = {
            (r.path, frozenset(m for m in r.methods if m != "HEAD")): r.endpoint
            for r in client.app.routes
            if isinstance(r, APIRoute)
        }
        pairs = [
            ("/api/v1/documents/upload", "/upload", frozenset({"POST"})),
            ("/api/v1/documents/upload/batch", "/upload/batch", frozenset({"POST"})),
            ("/api/v1/documents/{document_id}/status", "/status/{document_id}", frozenset({"GET"})),
        ]
        for canonical, legacy, methods in pairs:
            assert (canonical, methods) in routes, f"missing {canonical}"
            assert (legacy, methods) in routes, f"missing legacy alias {legacy}"
            assert routes[(canonical, methods)] is routes[(legacy, methods)], (
                f"{legacy} and {canonical} must be the same handler, not a copy"
            )

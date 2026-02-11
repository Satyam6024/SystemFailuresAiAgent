"""Integration tests for FastAPI API endpoints.

Uses httpx.AsyncClient with the FastAPI app, overriding DB dependencies
to use in-memory SQLite.
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.api.app import create_app
from src.core.runner import InvestigationRunner
from src.db.models import Base, InvestigationRecord


# ── Test fixtures ───────────────────────────────────────────────


@pytest.fixture
async def test_engine():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture
async def test_session_factory(test_engine):
    return async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)


@pytest.fixture
def mock_runner():
    """A mock InvestigationRunner that doesn't actually run the graph."""
    runner = MagicMock(spec=InvestigationRunner)
    runner.is_running = False
    runner.current_investigation_id = None
    runner.start_investigation = AsyncMock(return_value="mock-inv-001")
    return runner


@pytest.fixture
async def client(test_session_factory, mock_runner):
    """Create a test client with overridden dependencies."""
    app = create_app()

    async def override_db_session():
        async with test_session_factory() as session:
            yield session

    def override_runner():
        return mock_runner

    from src.api.dependencies import get_db_session, get_investigation_runner
    app.dependency_overrides[get_db_session] = override_db_session
    app.dependency_overrides[get_investigation_runner] = override_runner

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
async def client_with_data(test_session_factory, mock_runner):
    """Client with a pre-populated investigation record."""
    app = create_app()

    # Insert a test record
    async with test_session_factory() as session:
        record = InvestigationRecord(
            id="existing-001",
            scenario_type="latent_config_bug",
            alert_data={
                "service": "checkout-service",
                "metric": "p99_latency_ms",
                "value": 2000.0,
                "threshold": 500.0,
                "severity": "critical",
                "description": "Latency spike",
            },
            status="completed",
            findings_data=[
                {"agent_name": "logs_agent", "summary": "Found errors", "confidence": 0.85, "evidence": ["error1"]},
            ],
            root_cause="DB pool exhausted",
            confidence=0.85,
            recommendation="Rollback config",
            reasoning_trace=["step1", "step2"],
            agent_errors=[],
            duration_seconds=10.5,
            created_at=datetime(2025, 1, 15, 10, 30, 0),
            completed_at=datetime(2025, 1, 15, 10, 30, 10),
        )
        session.add(record)
        await session.commit()

    async def override_db_session():
        async with test_session_factory() as session:
            yield session

    def override_runner():
        return mock_runner

    from src.api.dependencies import get_db_session, get_investigation_runner
    app.dependency_overrides[get_db_session] = override_db_session
    app.dependency_overrides[get_investigation_runner] = override_runner

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# ── Health endpoint tests ───────────────────────────────────────


class TestHealthEndpoint:
    @pytest.mark.asyncio
    async def test_health_ok(self, client):
        response = await client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["investigation_running"] is False

    @pytest.mark.asyncio
    async def test_health_running(self, client, mock_runner):
        mock_runner.is_running = True
        mock_runner.current_investigation_id = "running-001"
        response = await client.get("/health")
        data = response.json()
        assert data["investigation_running"] is True
        assert data["current_investigation_id"] == "running-001"


# ── Alert endpoint tests ───────────────────────────────────────


class TestAlertEndpoint:
    @pytest.mark.asyncio
    async def test_trigger_alert_success(self, client):
        response = await client.post(
            "/api/v1/alert",
            json={"scenario_type": "latent_config_bug", "seed": 42, "severity": "critical"},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["investigation_id"] == "mock-inv-001"
        assert data["status"] == "detecting"

    @pytest.mark.asyncio
    async def test_trigger_alert_default_params(self, client):
        response = await client.post("/api/v1/alert", json={})
        assert response.status_code == 201

    @pytest.mark.asyncio
    async def test_trigger_alert_invalid_scenario(self, client):
        response = await client.post(
            "/api/v1/alert",
            json={"scenario_type": "nonexistent"},
        )
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_trigger_alert_already_running(self, client, mock_runner):
        from src.core.runner import InvestigationAlreadyRunning
        mock_runner.start_investigation = AsyncMock(
            side_effect=InvestigationAlreadyRunning("Already running")
        )
        response = await client.post(
            "/api/v1/alert",
            json={"scenario_type": "latent_config_bug"},
        )
        assert response.status_code == 409


# ── Investigation endpoints tests ──────────────────────────────


class TestInvestigationEndpoints:
    @pytest.mark.asyncio
    async def test_list_empty(self, client):
        response = await client.get("/api/v1/investigations")
        assert response.status_code == 200
        data = response.json()
        assert data["investigations"] == []
        assert data["total"] == 0

    @pytest.mark.asyncio
    async def test_list_with_data(self, client_with_data):
        response = await client_with_data.get("/api/v1/investigations")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["investigations"][0]["id"] == "existing-001"

    @pytest.mark.asyncio
    async def test_get_detail(self, client_with_data):
        response = await client_with_data.get("/api/v1/investigations/existing-001")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "existing-001"
        assert data["status"] == "completed"
        assert data["root_cause"] == "DB pool exhausted"
        assert data["confidence"] == 0.85
        assert len(data["findings"]) == 1

    @pytest.mark.asyncio
    async def test_get_detail_not_found(self, client):
        response = await client.get("/api/v1/investigations/nonexistent")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_list_pagination(self, client_with_data):
        response = await client_with_data.get(
            "/api/v1/investigations", params={"limit": 10, "offset": 0}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["limit"] == 10
        assert data["offset"] == 0


# ── Report endpoints tests ─────────────────────────────────────


class TestReportEndpoints:
    @pytest.mark.asyncio
    async def test_get_markdown_report(self, client_with_data):
        response = await client_with_data.get(
            "/api/v1/investigations/existing-001/report"
        )
        assert response.status_code == 200
        assert "text/" in response.headers["content-type"]
        assert len(response.text) > 100

    @pytest.mark.asyncio
    async def test_get_report_not_found(self, client):
        response = await client.get("/api/v1/investigations/nonexistent/report")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_get_pdf_report(self, client_with_data):
        response = await client_with_data.get(
            "/api/v1/investigations/existing-001/report/pdf"
        )
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/pdf"
        assert response.content[:4] == b"%PDF"

    @pytest.mark.asyncio
    async def test_get_pdf_not_found(self, client):
        response = await client.get("/api/v1/investigations/nonexistent/report/pdf")
        assert response.status_code == 404


# ── Metrics endpoint tests ─────────────────────────────────────


class TestMetricsEndpoint:
    @pytest.mark.asyncio
    async def test_prometheus_metrics(self, client):
        response = await client.get("/metrics")
        assert response.status_code == 200
        text = response.text
        assert "sfa_investigations_total" in text
        assert "sfa_investigation_running" in text
        assert "sfa_uptime_seconds" in text
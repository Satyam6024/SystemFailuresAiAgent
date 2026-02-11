"""Shared test fixtures for the SFA test suite."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.core.models import (
    AgentFinding,
    Alert,
    InvestigationPlan,
    MockDataSet,
    RCAReport,
    ServiceName,
    Severity,
)
from src.db.models import Base, InvestigationRecord


# ── Async engine for tests (in-memory SQLite) ──────────────────


@pytest.fixture
async def async_engine():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture
async def db_session(async_engine) -> AsyncGenerator[AsyncSession, None]:
    session_factory = async_sessionmaker(
        async_engine, class_=AsyncSession, expire_on_commit=False
    )
    async with session_factory() as session:
        yield session


# ── Sample data fixtures ────────────────────────────────────────


@pytest.fixture
def sample_alert() -> Alert:
    return Alert(
        alert_id="test-alert-001",
        service=ServiceName.CHECKOUT_SERVICE,
        metric="p99_latency_ms",
        value=2000.0,
        threshold=500.0,
        severity=Severity.CRITICAL,
        timestamp=datetime(2025, 1, 15, 10, 30, 0),
        description="Checkout service p99 latency spiked to 2000ms",
    )


@pytest.fixture
def sample_finding() -> AgentFinding:
    return AgentFinding(
        agent_name="logs_agent",
        summary="Found DB connection timeout errors in checkout-service",
        evidence=[
            "20 DB connection timeout errors in last 5 minutes",
            "Pool exhausted: active=10/10",
        ],
        confidence=0.85,
        relevant_timestamps=[
            datetime(2025, 1, 15, 10, 25, 0),
            datetime(2025, 1, 15, 10, 30, 0),
        ],
    )


@pytest.fixture
def sample_plan() -> InvestigationPlan:
    return InvestigationPlan(
        hypothesis="Latent config bug in checkout-service DB connection pool",
        tasks=[
            "Search logs for connection timeout errors",
            "Check recent deployments to checkout-service",
            "Monitor DB connection pool metrics",
        ],
        priority_services=[ServiceName.CHECKOUT_SERVICE, ServiceName.POSTGRES_DB],
        time_window_start=datetime(2025, 1, 15, 10, 0, 0),
        time_window_end=datetime(2025, 1, 15, 10, 30, 0),
    )


@pytest.fixture
def sample_investigation_record(db_session) -> InvestigationRecord:
    """A pre-built InvestigationRecord (not yet committed to DB)."""
    return InvestigationRecord(
        id="test-inv-001",
        scenario_type="latent_config_bug",
        alert_data={
            "service": "checkout-service",
            "metric": "p99_latency_ms",
            "value": 2000.0,
            "threshold": 500.0,
            "severity": "critical",
            "description": "Checkout service p99 latency spiked to 2000ms",
        },
        status="completed",
        plan_data={
            "hypothesis": "Latent config bug",
            "tasks": ["Check logs", "Check metrics"],
            "priority_services": ["checkout-service"],
            "time_window_start": "2025-01-15T10:00:00",
            "time_window_end": "2025-01-15T10:30:00",
        },
        findings_data=[
            {
                "agent_name": "logs_agent",
                "summary": "Found DB connection timeout errors",
                "evidence": ["20 timeouts in 5 min"],
                "confidence": 0.85,
            },
            {
                "agent_name": "metrics_agent",
                "summary": "Latency spike correlated with config deploy",
                "evidence": ["p99 went from 120ms to 2000ms"],
                "confidence": 0.90,
            },
        ],
        root_cause="DB connection pool reduced from 100 to 10 connections",
        confidence=0.87,
        recommendation="Rollback the config change",
        remediation_action="ROLLBACK TRIGGERED",
        reasoning_trace=["Detected alert", "Created plan", "Investigated"],
        agent_errors=[],
        duration_seconds=12.5,
        created_at=datetime(2025, 1, 15, 10, 30, 0),
        completed_at=datetime(2025, 1, 15, 10, 30, 12),
    )
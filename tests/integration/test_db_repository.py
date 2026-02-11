"""Integration tests for src/db/repository.py using in-memory SQLite."""

from __future__ import annotations

from datetime import datetime

import pytest

from src.db.models import InvestigationRecord
from src.db.repository import (
    count_investigations,
    create_investigation,
    get_investigation,
    list_investigations,
    update_investigation,
)


class TestCreateInvestigation:
    @pytest.mark.asyncio
    async def test_create_returns_record(self, db_session):
        record = await create_investigation(
            db_session,
            investigation_id="test-001",
            alert_data={"service": "checkout-service", "metric": "p99_latency_ms"},
            scenario_type="latent_config_bug",
        )
        assert isinstance(record, InvestigationRecord)
        assert record.id == "test-001"
        assert record.status == "detecting"
        assert record.scenario_type == "latent_config_bug"
        assert record.alert_data["service"] == "checkout-service"

    @pytest.mark.asyncio
    async def test_create_without_scenario(self, db_session):
        record = await create_investigation(
            db_session,
            investigation_id="test-002",
            alert_data={"service": "api-gateway"},
        )
        assert record.scenario_type is None

    @pytest.mark.asyncio
    async def test_create_sets_timestamp(self, db_session):
        record = await create_investigation(
            db_session,
            investigation_id="test-003",
            alert_data={"service": "api-gateway"},
        )
        assert record.created_at is not None


class TestGetInvestigation:
    @pytest.mark.asyncio
    async def test_get_existing(self, db_session):
        await create_investigation(
            db_session,
            investigation_id="get-test-001",
            alert_data={"service": "checkout-service"},
        )
        record = await get_investigation(db_session, "get-test-001")
        assert record is not None
        assert record.id == "get-test-001"

    @pytest.mark.asyncio
    async def test_get_nonexistent(self, db_session):
        record = await get_investigation(db_session, "nonexistent")
        assert record is None


class TestUpdateInvestigation:
    @pytest.mark.asyncio
    async def test_update_status(self, db_session):
        await create_investigation(
            db_session,
            investigation_id="update-001",
            alert_data={"service": "checkout-service"},
        )
        updated = await update_investigation(
            db_session, "update-001", status="investigating"
        )
        assert updated is not None
        assert updated.status == "investigating"

    @pytest.mark.asyncio
    async def test_update_multiple_fields(self, db_session):
        await create_investigation(
            db_session,
            investigation_id="update-002",
            alert_data={"service": "checkout-service"},
        )
        updated = await update_investigation(
            db_session,
            "update-002",
            status="completed",
            root_cause="DB pool exhausted",
            confidence=0.85,
            recommendation="Rollback config",
            duration_seconds=12.5,
            completed_at=datetime.utcnow(),
        )
        assert updated.status == "completed"
        assert updated.root_cause == "DB pool exhausted"
        assert updated.confidence == 0.85
        assert updated.duration_seconds == 12.5

    @pytest.mark.asyncio
    async def test_update_json_fields(self, db_session):
        await create_investigation(
            db_session,
            investigation_id="update-003",
            alert_data={"service": "checkout-service"},
        )
        findings = [
            {"agent_name": "logs_agent", "summary": "Found errors", "confidence": 0.8}
        ]
        updated = await update_investigation(
            db_session,
            "update-003",
            findings_data=findings,
            reasoning_trace=["step1", "step2"],
        )
        assert updated.findings_data == findings
        assert updated.reasoning_trace == ["step1", "step2"]

    @pytest.mark.asyncio
    async def test_update_nonexistent(self, db_session):
        result = await update_investigation(
            db_session, "nonexistent", status="completed"
        )
        assert result is None


class TestListInvestigations:
    @pytest.mark.asyncio
    async def test_list_empty(self, db_session):
        records = await list_investigations(db_session)
        assert records == []

    @pytest.mark.asyncio
    async def test_list_multiple(self, db_session):
        for i in range(3):
            await create_investigation(
                db_session,
                investigation_id=f"list-{i}",
                alert_data={"service": "checkout-service"},
            )
        records = await list_investigations(db_session)
        assert len(records) == 3

    @pytest.mark.asyncio
    async def test_list_with_limit(self, db_session):
        for i in range(5):
            await create_investigation(
                db_session,
                investigation_id=f"limit-{i}",
                alert_data={"service": "checkout-service"},
            )
        records = await list_investigations(db_session, limit=2)
        assert len(records) == 2

    @pytest.mark.asyncio
    async def test_list_with_offset(self, db_session):
        for i in range(5):
            await create_investigation(
                db_session,
                investigation_id=f"offset-{i}",
                alert_data={"service": "checkout-service"},
            )
        records = await list_investigations(db_session, limit=10, offset=3)
        assert len(records) == 2

    @pytest.mark.asyncio
    async def test_list_filter_by_status(self, db_session):
        await create_investigation(
            db_session,
            investigation_id="status-1",
            alert_data={"service": "checkout-service"},
        )
        await create_investigation(
            db_session,
            investigation_id="status-2",
            alert_data={"service": "api-gateway"},
        )
        await update_investigation(db_session, "status-2", status="completed")

        detecting = await list_investigations(db_session, status="detecting")
        assert len(detecting) == 1
        assert detecting[0].id == "status-1"

        completed = await list_investigations(db_session, status="completed")
        assert len(completed) == 1
        assert completed[0].id == "status-2"


class TestCountInvestigations:
    @pytest.mark.asyncio
    async def test_count_empty(self, db_session):
        count = await count_investigations(db_session)
        assert count == 0

    @pytest.mark.asyncio
    async def test_count_all(self, db_session):
        for i in range(3):
            await create_investigation(
                db_session,
                investigation_id=f"count-{i}",
                alert_data={"service": "checkout-service"},
            )
        count = await count_investigations(db_session)
        assert count == 3

    @pytest.mark.asyncio
    async def test_count_by_status(self, db_session):
        await create_investigation(
            db_session,
            investigation_id="cnt-1",
            alert_data={"service": "checkout-service"},
        )
        await create_investigation(
            db_session,
            investigation_id="cnt-2",
            alert_data={"service": "api-gateway"},
        )
        await update_investigation(db_session, "cnt-2", status="completed")

        assert await count_investigations(db_session, status="detecting") == 1
        assert await count_investigations(db_session, status="completed") == 1
"""Unit tests for Pydantic models in src/core/models.py."""

from __future__ import annotations

from datetime import datetime

import pytest
from pydantic import ValidationError

from src.core.models import (
    AgentFinding,
    Alert,
    ChangeType,
    DeploymentEvent,
    InvestigationPlan,
    InvestigationStatus,
    LogEntry,
    MetricDataPoint,
    MockDataSet,
    RCAReport,
    ServiceName,
    Severity,
    TimelineEvent,
)


class TestEnums:
    def test_severity_values(self):
        assert Severity.CRITICAL == "critical"
        assert Severity.HIGH == "high"
        assert Severity.MEDIUM == "medium"
        assert Severity.LOW == "low"

    def test_investigation_status_values(self):
        assert InvestigationStatus.DETECTING == "detecting"
        assert InvestigationStatus.COMPLETED == "completed"
        assert InvestigationStatus.FAILED == "failed"

    def test_service_name_values(self):
        assert ServiceName.CHECKOUT_SERVICE == "checkout-service"
        assert ServiceName.API_GATEWAY == "api-gateway"
        assert len(ServiceName) == 8

    def test_change_type_values(self):
        assert ChangeType.CONFIG_CHANGE == "config_change"
        assert ChangeType.CODE_DEPLOY == "code_deploy"
        assert ChangeType.ROLLBACK == "rollback"


class TestAlert:
    def test_create_alert(self, sample_alert):
        assert sample_alert.service == ServiceName.CHECKOUT_SERVICE
        assert sample_alert.value == 2000.0
        assert sample_alert.severity == Severity.CRITICAL

    def test_alert_auto_id(self):
        alert = Alert(
            service=ServiceName.API_GATEWAY,
            metric="error_rate",
            value=0.5,
            threshold=0.05,
            severity=Severity.HIGH,
            description="Error rate high",
        )
        assert len(alert.alert_id) == 12

    def test_alert_auto_timestamp(self):
        alert = Alert(
            service=ServiceName.API_GATEWAY,
            metric="error_rate",
            value=0.5,
            threshold=0.05,
            severity=Severity.HIGH,
            description="Error rate high",
        )
        assert isinstance(alert.timestamp, datetime)

    def test_alert_serialization(self, sample_alert):
        data = sample_alert.model_dump(mode="json")
        assert data["service"] == "checkout-service"
        assert data["severity"] == "critical"
        assert isinstance(data["timestamp"], str)

    def test_alert_deserialization(self, sample_alert):
        data = sample_alert.model_dump(mode="json")
        restored = Alert.model_validate(data)
        assert restored.service == sample_alert.service
        assert restored.value == sample_alert.value

    def test_alert_invalid_service(self):
        with pytest.raises(ValidationError):
            Alert(
                service="nonexistent-service",
                metric="cpu",
                value=1.0,
                threshold=0.5,
                severity=Severity.LOW,
                description="Test",
            )


class TestLogEntry:
    def test_create_log_entry(self):
        entry = LogEntry(
            timestamp=datetime.utcnow(),
            service=ServiceName.CHECKOUT_SERVICE,
            level="ERROR",
            message="DB connection timeout",
        )
        assert entry.trace_id is None
        assert entry.stack_trace is None

    def test_log_entry_with_trace(self):
        entry = LogEntry(
            timestamp=datetime.utcnow(),
            service=ServiceName.CHECKOUT_SERVICE,
            level="ERROR",
            message="DB connection timeout",
            trace_id="trace-12345",
            stack_trace="java.sql.Exception...",
        )
        assert entry.trace_id == "trace-12345"


class TestMetricDataPoint:
    def test_create_metric(self):
        m = MetricDataPoint(
            timestamp=datetime.utcnow(),
            service=ServiceName.CHECKOUT_SERVICE,
            metric_name="cpu_percent",
            value=85.5,
        )
        assert m.value == 85.5


class TestDeploymentEvent:
    def test_create_deployment(self):
        dep = DeploymentEvent(
            timestamp=datetime.utcnow(),
            service=ServiceName.CHECKOUT_SERVICE,
            change_type=ChangeType.CONFIG_CHANGE,
            description="Updated DB pool config",
        )
        assert len(dep.deploy_id) == 8
        assert dep.author == "ci-bot"

    def test_deployment_serialization(self):
        dep = DeploymentEvent(
            timestamp=datetime(2025, 1, 15, 10, 0, 0),
            service=ServiceName.CHECKOUT_SERVICE,
            change_type=ChangeType.CODE_DEPLOY,
            description="Deploy v2.14.0",
            commit_sha="abc123",
            author="dev-team",
        )
        data = dep.model_dump(mode="json")
        assert data["change_type"] == "code_deploy"
        assert data["author"] == "dev-team"


class TestAgentFinding:
    def test_create_finding(self, sample_finding):
        assert sample_finding.agent_name == "logs_agent"
        assert sample_finding.confidence == 0.85
        assert len(sample_finding.evidence) == 2

    def test_finding_defaults(self):
        f = AgentFinding(agent_name="test", summary="test summary")
        assert f.confidence == 0.0
        assert f.evidence == []
        assert f.relevant_timestamps == []


class TestInvestigationPlan:
    def test_create_plan(self, sample_plan):
        assert sample_plan.hypothesis.startswith("Latent config bug")
        assert len(sample_plan.tasks) == 3
        assert ServiceName.CHECKOUT_SERVICE in sample_plan.priority_services


class TestRCAReport:
    def test_create_report(self, sample_alert, sample_finding, sample_plan):
        report = RCAReport(
            alert=sample_alert,
            plan=sample_plan,
            findings=[sample_finding],
            root_cause="DB pool config change",
            confidence=0.85,
            recommendation="Rollback config",
        )
        assert len(report.investigation_id) == 16
        assert report.status == InvestigationStatus.COMPLETED
        assert report.confidence == 0.85

    def test_report_serialization(self, sample_alert):
        report = RCAReport(
            alert=sample_alert,
            root_cause="Test cause",
            confidence=0.5,
        )
        data = report.model_dump(mode="json")
        assert "investigation_id" in data
        assert data["confidence"] == 0.5
        restored = RCAReport.model_validate(data)
        assert restored.root_cause == "Test cause"


class TestMockDataSet:
    def test_create_dataset(self, sample_alert):
        ds = MockDataSet(scenario_name="test", alert=sample_alert)
        assert ds.logs == []
        assert ds.metrics == []
        assert ds.deployments == []

    def test_dataset_with_data(self, sample_alert):
        log = LogEntry(
            timestamp=datetime.utcnow(),
            service=ServiceName.CHECKOUT_SERVICE,
            level="ERROR",
            message="Error",
        )
        ds = MockDataSet(
            scenario_name="test",
            alert=sample_alert,
            logs=[log],
        )
        assert len(ds.logs) == 1
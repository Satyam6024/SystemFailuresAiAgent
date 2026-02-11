"""Unit tests for mock data generation (scenarios + generator)."""

from __future__ import annotations

from datetime import datetime

import pytest

from src.core.models import MockDataSet, ServiceName, Severity
from src.data.mock_generator import MockDataGenerator


class TestMockDataGenerator:
    def test_available_scenarios(self):
        scenarios = MockDataGenerator.available_scenarios()
        assert "latent_config_bug" in scenarios
        assert "memory_leak" in scenarios
        assert "cascading_failure" in scenarios
        assert "traffic_spike" in scenarios
        assert len(scenarios) == 4

    def test_unknown_scenario_raises(self):
        with pytest.raises(ValueError, match="Unknown scenario 'nonexistent'"):
            MockDataGenerator.generate("nonexistent")

    def test_generate_returns_mock_dataset(self):
        ds = MockDataGenerator.generate("latent_config_bug")
        assert isinstance(ds, MockDataSet)
        assert ds.scenario_name == "latent_config_bug"

    def test_deterministic_with_seed(self):
        ds1 = MockDataGenerator.generate("latent_config_bug", seed=42)
        ds2 = MockDataGenerator.generate("latent_config_bug", seed=42)
        assert len(ds1.logs) == len(ds2.logs)
        assert len(ds1.metrics) == len(ds2.metrics)
        assert len(ds1.deployments) == len(ds2.deployments)

    def test_different_seeds_produce_different_data(self):
        ds1 = MockDataGenerator.generate("latent_config_bug", seed=42)
        ds2 = MockDataGenerator.generate("latent_config_bug", seed=99)
        # Log counts can differ with different seeds
        assert ds1.logs[0].message != ds2.logs[0].message or len(ds1.logs) != len(ds2.logs)

    def test_custom_incident_time(self):
        fixed_time = datetime(2025, 6, 15, 12, 0, 0)
        ds = MockDataGenerator.generate(
            "latent_config_bug", incident_time=fixed_time
        )
        assert ds.alert.timestamp == fixed_time


class TestLatentConfigBugScenario:
    def test_generates_logs_metrics_deployments(self):
        ds = MockDataGenerator.generate("latent_config_bug")
        assert len(ds.logs) > 0
        assert len(ds.metrics) > 0
        assert len(ds.deployments) > 0

    def test_alert_is_checkout_service(self):
        ds = MockDataGenerator.generate("latent_config_bug")
        assert ds.alert.service == ServiceName.CHECKOUT_SERVICE
        assert ds.alert.metric == "p99_latency_ms"

    def test_has_deployment_event(self):
        ds = MockDataGenerator.generate("latent_config_bug")
        assert len(ds.deployments) >= 1
        dep = ds.deployments[0]
        assert dep.service == ServiceName.CHECKOUT_SERVICE
        assert "config" in dep.change_type.value

    def test_has_error_logs(self):
        ds = MockDataGenerator.generate("latent_config_bug")
        error_logs = [l for l in ds.logs if l.level == "ERROR"]
        assert len(error_logs) > 0
        # Should have DB connection timeout errors
        timeout_errors = [l for l in error_logs if "timeout" in l.message.lower()]
        assert len(timeout_errors) > 0

    def test_severity_parameter(self):
        ds = MockDataGenerator.generate("latent_config_bug", severity="high")
        assert ds.alert.severity == Severity.HIGH

    def test_logs_sorted_by_timestamp(self):
        ds = MockDataGenerator.generate("latent_config_bug")
        timestamps = [l.timestamp for l in ds.logs]
        assert timestamps == sorted(timestamps)

    def test_metrics_sorted_by_timestamp(self):
        ds = MockDataGenerator.generate("latent_config_bug")
        timestamps = [m.timestamp for m in ds.metrics]
        assert timestamps == sorted(timestamps)


class TestMemoryLeakScenario:
    def test_generates_data(self):
        ds = MockDataGenerator.generate("memory_leak")
        assert len(ds.logs) > 0
        assert len(ds.metrics) > 0
        assert len(ds.deployments) >= 1

    def test_alert_is_inventory_service(self):
        ds = MockDataGenerator.generate("memory_leak")
        assert ds.alert.service == ServiceName.INVENTORY_SERVICE
        assert ds.alert.metric == "memory_mb"

    def test_has_oom_error(self):
        ds = MockDataGenerator.generate("memory_leak")
        oom_logs = [l for l in ds.logs if "OOM" in l.message or "OutOfMemory" in (l.stack_trace or "")]
        assert len(oom_logs) > 0

    def test_memory_metrics_increasing(self):
        ds = MockDataGenerator.generate("memory_leak")
        mem_metrics = [
            m for m in ds.metrics
            if m.metric_name == "memory_mb" and m.service == ServiceName.INVENTORY_SERVICE
        ]
        assert len(mem_metrics) > 10
        # First value should be much lower than last value
        assert mem_metrics[0].value < mem_metrics[-1].value


class TestCascadingFailureScenario:
    def test_generates_data(self):
        ds = MockDataGenerator.generate("cascading_failure")
        assert len(ds.logs) > 0
        assert len(ds.metrics) > 0

    def test_no_deployments(self):
        ds = MockDataGenerator.generate("cascading_failure")
        # Cascading failure has no deployments
        assert len(ds.deployments) == 0

    def test_postgres_error_logs(self):
        ds = MockDataGenerator.generate("cascading_failure")
        pg_errors = [l for l in ds.logs if l.service == ServiceName.POSTGRES_DB]
        assert len(pg_errors) > 0


class TestTrafficSpikeScenario:
    def test_generates_data(self):
        ds = MockDataGenerator.generate("traffic_spike")
        assert len(ds.logs) > 0
        assert len(ds.metrics) > 0

    def test_no_deployments(self):
        ds = MockDataGenerator.generate("traffic_spike")
        assert len(ds.deployments) == 0

    def test_alert_is_api_gateway(self):
        ds = MockDataGenerator.generate("traffic_spike")
        assert ds.alert.service == ServiceName.API_GATEWAY
        assert ds.alert.metric == "requests_per_second"

    def test_has_rate_limit_warnings(self):
        ds = MockDataGenerator.generate("traffic_spike")
        rate_limit_logs = [l for l in ds.logs if "rate limit" in l.message.lower()]
        assert len(rate_limit_logs) > 0
"""Unit tests for src/reports/generator.py."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock

import pytest

from src.reports.generator import (
    _fmt_duration,
    _fmt_percent,
    _fmt_timestamp,
    generate_markdown_from_dict,
    generate_markdown_report,
)


class TestFormatTimestamp:
    def test_datetime_object(self):
        dt = datetime(2025, 1, 15, 10, 30, 0)
        assert _fmt_timestamp(dt) == "2025-01-15 10:30:00 UTC"

    def test_iso_string(self):
        result = _fmt_timestamp("2025-01-15T10:30:00")
        assert "2025-01-15" in result
        assert "10:30:00" in result

    def test_iso_string_with_z(self):
        result = _fmt_timestamp("2025-01-15T10:30:00Z")
        assert "2025-01-15" in result

    def test_non_datetime_passthrough(self):
        assert _fmt_timestamp(12345) == "12345"

    def test_invalid_string(self):
        assert _fmt_timestamp("not-a-date") == "not-a-date"


class TestFormatPercent:
    def test_float_value(self):
        assert _fmt_percent(0.85) == "85%"

    def test_zero(self):
        assert _fmt_percent(0.0) == "0%"

    def test_one(self):
        assert _fmt_percent(1.0) == "100%"

    def test_none(self):
        assert _fmt_percent(None) == "N/A"

    def test_string_number(self):
        assert _fmt_percent("0.5") == "50%"

    def test_invalid(self):
        assert _fmt_percent("not-a-number") == "not-a-number"


class TestFormatDuration:
    def test_seconds(self):
        assert _fmt_duration(12.5) == "12.5s"

    def test_minutes(self):
        result = _fmt_duration(125.0)
        assert "2m" in result
        assert "5s" in result

    def test_none(self):
        assert _fmt_duration(None) == "N/A"

    def test_zero(self):
        assert _fmt_duration(0) == "0.0s"


class TestGenerateMarkdownReport:
    def test_generates_markdown(self, sample_investigation_record):
        record = sample_investigation_record
        md = generate_markdown_report(record)
        assert isinstance(md, str)
        assert len(md) > 100
        assert "test-inv-001" in md
        assert "checkout-service" in md or "Checkout" in md

    def test_contains_root_cause(self, sample_investigation_record):
        record = sample_investigation_record
        md = generate_markdown_report(record)
        assert "DB connection pool" in md or "connection pool" in md.lower()

    def test_contains_findings(self, sample_investigation_record):
        record = sample_investigation_record
        md = generate_markdown_report(record)
        assert "logs_agent" in md
        assert "metrics_agent" in md


class TestGenerateMarkdownFromDict:
    def test_basic_dict(self):
        data = {
            "id": "dict-test-001",
            "status": "completed",
            "alert_data": {
                "service": "checkout-service",
                "metric": "p99_latency_ms",
                "value": 2000.0,
                "threshold": 500.0,
                "severity": "critical",
                "description": "Latency spike",
            },
            "root_cause": "Config change reduced connections",
            "confidence": 0.9,
            "recommendation": "Rollback config",
        }
        md = generate_markdown_from_dict(data)
        assert isinstance(md, str)
        assert "dict-test-001" in md
        assert "Config change" in md or "config change" in md.lower()

    def test_empty_dict(self):
        md = generate_markdown_from_dict({})
        assert isinstance(md, str)
        assert "unknown" in md.lower() or "N/A" in md

    def test_alternative_key_names(self):
        """Test that the function handles both 'alert_data' and 'alert' keys."""
        data = {
            "id": "alt-test",
            "status": "completed",
            "alert": {"service": "api-gateway", "description": "Error rate high"},
            "findings": [
                {"agent_name": "logs_agent", "summary": "Found errors", "confidence": 0.8}
            ],
        }
        md = generate_markdown_from_dict(data)
        assert "alt-test" in md
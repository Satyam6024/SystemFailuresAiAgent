"""RCA Report Generator — Jinja2-based markdown report renderer.

Takes an InvestigationRecord (from DB) or raw investigation dict and produces
a structured markdown RCA report using a Jinja2 template.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader

TEMPLATE_DIR = Path(__file__).parent / "templates"


def _fmt_timestamp(value: Any) -> str:
    """Format a timestamp for display."""
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S UTC")
    if isinstance(value, str):
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return dt.strftime("%Y-%m-%d %H:%M:%S UTC")
        except ValueError:
            return value
    return str(value)


def _fmt_percent(value: Any) -> str:
    """Format a float as percentage."""
    if value is None:
        return "N/A"
    try:
        return f"{float(value):.0%}"
    except (TypeError, ValueError):
        return str(value)


def _fmt_duration(value: Any) -> str:
    """Format seconds as a readable duration."""
    if value is None:
        return "N/A"
    try:
        secs = float(value)
        if secs < 60:
            return f"{secs:.1f}s"
        mins = int(secs // 60)
        remaining = secs % 60
        return f"{mins}m {remaining:.0f}s"
    except (TypeError, ValueError):
        return str(value)


def _get_jinja_env() -> Environment:
    """Create a Jinja2 environment with custom filters."""
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATE_DIR)),
        trim_blocks=True,
        lstrip_blocks=True,
        keep_trailing_newline=True,
    )
    env.filters["fmt_timestamp"] = _fmt_timestamp
    env.filters["fmt_percent"] = _fmt_percent
    env.filters["fmt_duration"] = _fmt_duration
    return env


def generate_markdown_report(record) -> str:
    """Generate a structured markdown RCA report from a DB record.

    Args:
        record: An InvestigationRecord ORM object with attributes like
                id, status, scenario_type, alert_data, plan_data,
                findings_data, root_cause, confidence, recommendation,
                remediation_action, reasoning_trace, created_at,
                completed_at, duration_seconds.

    Returns:
        A formatted markdown string.
    """
    env = _get_jinja_env()
    template = env.get_template("rca_template.md.j2")

    context = {
        "id": record.id,
        "status": record.status,
        "scenario_type": record.scenario_type or "N/A",
        "created_at": record.created_at,
        "completed_at": record.completed_at,
        "duration_seconds": record.duration_seconds,
        "alert": record.alert_data or {},
        "plan": record.plan_data or {},
        "findings": record.findings_data or [],
        "root_cause": record.root_cause or "Undetermined",
        "confidence": record.confidence,
        "recommendation": record.recommendation or "Manual investigation recommended",
        "remediation_action": record.remediation_action,
        "reasoning_trace": record.reasoning_trace or [],
        "agent_errors": record.agent_errors or [],
    }

    return template.render(**context)


def generate_markdown_from_dict(data: dict) -> str:
    """Generate a markdown RCA report from a raw dictionary.

    Useful for generating reports without a DB record (e.g., from API response).
    """
    env = _get_jinja_env()
    template = env.get_template("rca_template.md.j2")

    context = {
        "id": data.get("id", "unknown"),
        "status": data.get("status", "unknown"),
        "scenario_type": data.get("scenario_type", "N/A"),
        "created_at": data.get("created_at"),
        "completed_at": data.get("completed_at"),
        "duration_seconds": data.get("duration_seconds"),
        "alert": data.get("alert_data", data.get("alert", {})),
        "plan": data.get("plan_data", data.get("plan", {})),
        "findings": data.get("findings_data", data.get("findings", [])),
        "root_cause": data.get("root_cause", "Undetermined"),
        "confidence": data.get("confidence"),
        "recommendation": data.get("recommendation", "Manual investigation recommended"),
        "remediation_action": data.get("remediation_action"),
        "reasoning_trace": data.get("reasoning_trace", []),
        "agent_errors": data.get("agent_errors", []),
    }

    return template.render(**context)
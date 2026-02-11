"""LangChain tool definitions for sub-agent data retrieval.

Each tool pulls data from the MockDataSet stored in the graph state.
The tools format the data as human-readable strings for the LLM.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from src.core.models import MockDataSet, ServiceName


# ── Data Retrieval Functions ─────────────────────────────────────
# These are plain functions (not LangChain @tool decorated) because
# we call them directly from agent nodes with access to mock_data.


def search_logs(
    mock_data: MockDataSet,
    service: Optional[str] = None,
    level: Optional[str] = None,
    time_start: Optional[datetime] = None,
    time_end: Optional[datetime] = None,
    keyword: Optional[str] = None,
    limit: int = 50,
) -> str:
    """Search application logs with filters. Returns formatted log entries."""
    entries = mock_data.logs

    if service:
        entries = [e for e in entries if e.service.value == service]
    if level:
        entries = [e for e in entries if e.level == level.upper()]
    if time_start:
        entries = [e for e in entries if e.timestamp >= time_start]
    if time_end:
        entries = [e for e in entries if e.timestamp <= time_end]
    if keyword:
        kw = keyword.lower()
        entries = [e for e in entries if kw in e.message.lower() or (e.stack_trace and kw in e.stack_trace.lower())]

    entries = entries[:limit]

    if not entries:
        return "No log entries found matching the given filters."

    lines = []
    for e in entries:
        line = f"[{e.timestamp.isoformat()}] [{e.service.value}] {e.level}: {e.message}"
        if e.trace_id:
            line += f" (trace_id={e.trace_id})"
        if e.stack_trace:
            line += f"\n  Stack: {e.stack_trace[:300]}"
        lines.append(line)

    return f"Found {len(entries)} log entries:\n\n" + "\n\n".join(lines)


def query_metrics(
    mock_data: MockDataSet,
    service: Optional[str] = None,
    metric_name: Optional[str] = None,
    time_start: Optional[datetime] = None,
    time_end: Optional[datetime] = None,
    limit: int = 100,
) -> str:
    """Query performance metrics with filters. Returns formatted data points."""
    points = mock_data.metrics

    if service:
        points = [p for p in points if p.service.value == service]
    if metric_name:
        points = [p for p in points if p.metric_name == metric_name]
    if time_start:
        points = [p for p in points if p.timestamp >= time_start]
    if time_end:
        points = [p for p in points if p.timestamp <= time_end]

    points = points[:limit]

    if not points:
        return "No metric data points found matching the given filters."

    lines = []
    for p in points:
        lines.append(
            f"[{p.timestamp.isoformat()}] {p.service.value} | {p.metric_name} = {p.value:.2f}"
        )

    return f"Found {len(points)} metric data points:\n\n" + "\n".join(lines)


def get_deployments(
    mock_data: MockDataSet,
    service: Optional[str] = None,
    time_start: Optional[datetime] = None,
    time_end: Optional[datetime] = None,
) -> str:
    """Get deployment history with filters. Returns formatted events."""
    events = mock_data.deployments

    if service:
        events = [e for e in events if e.service.value == service]
    if time_start:
        events = [e for e in events if e.timestamp >= time_start]
    if time_end:
        events = [e for e in events if e.timestamp <= time_end]

    if not events:
        return "No deployment events found matching the given filters."

    lines = []
    for e in events:
        lines.append(
            f"[{e.timestamp.isoformat()}] {e.service.value} | "
            f"{e.change_type.value} | {e.description} "
            f"(deploy_id={e.deploy_id}, author={e.author}"
            f"{', sha=' + e.commit_sha if e.commit_sha else ''})"
        )

    return f"Found {len(events)} deployment events:\n\n" + "\n".join(lines)


def get_all_services_summary(mock_data: MockDataSet) -> str:
    """Get a summary of all services with latest metric values."""
    from collections import defaultdict

    latest: dict[str, dict[str, float]] = defaultdict(dict)
    for p in mock_data.metrics:
        key = p.service.value
        if p.metric_name not in latest[key] or True:  # always update to get latest
            latest[key][p.metric_name] = p.value

    lines = []
    for svc, metrics in sorted(latest.items()):
        metrics_str = ", ".join(f"{k}={v:.1f}" for k, v in sorted(metrics.items()))
        lines.append(f"  {svc}: {metrics_str}")

    return "Service metrics summary:\n" + "\n".join(lines)

"""Prometheus-compatible metrics endpoint.

Exposes application metrics in Prometheus text format for scraping.
No external dependency required — we format the metrics manually.
"""

from __future__ import annotations

import time

from fastapi import APIRouter, Depends
from fastapi.responses import PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import get_db_session, get_investigation_runner
from src.core.runner import InvestigationRunner
from src.db.repository import count_investigations

router = APIRouter()

_start_time = time.time()


@router.get("/metrics", response_class=PlainTextResponse)
async def prometheus_metrics(
    runner: InvestigationRunner = Depends(get_investigation_runner),
    session: AsyncSession = Depends(get_db_session),
) -> PlainTextResponse:
    """Expose application metrics in Prometheus text format."""

    total = await count_investigations(session)
    uptime = time.time() - _start_time
    running = 1 if runner.is_running else 0

    lines = [
        "# HELP sfa_investigations_total Total number of investigations",
        "# TYPE sfa_investigations_total counter",
        f"sfa_investigations_total {total}",
        "",
        "# HELP sfa_investigation_running Whether an investigation is currently running",
        "# TYPE sfa_investigation_running gauge",
        f"sfa_investigation_running {running}",
        "",
        "# HELP sfa_uptime_seconds API server uptime in seconds",
        "# TYPE sfa_uptime_seconds gauge",
        f"sfa_uptime_seconds {uptime:.1f}",
        "",
    ]

    return PlainTextResponse(
        content="\n".join(lines),
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )
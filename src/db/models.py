"""SQLAlchemy ORM models for investigation persistence."""

from __future__ import annotations

import datetime

from sqlalchemy import DateTime, Float, JSON, String, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class InvestigationRecord(Base):
    __tablename__ = "investigations"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    scenario_type: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Alert snapshot
    alert_data: Mapped[dict] = mapped_column(JSON, nullable=False)

    # Status tracking
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="detecting")

    # Investigation state
    plan_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    findings_data: Mapped[list | None] = mapped_column(JSON, nullable=True)
    reasoning_trace: Mapped[list | None] = mapped_column(JSON, nullable=True)
    agent_errors: Mapped[list | None] = mapped_column(JSON, nullable=True)

    # Results
    root_cause: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    recommendation: Mapped[str | None] = mapped_column(Text, nullable=True)
    remediation_action: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Full report JSON
    report_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Timestamps
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    completed_at: Mapped[datetime.datetime | None] = mapped_column(DateTime, nullable=True)
    duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)

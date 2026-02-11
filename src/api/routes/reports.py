"""RCA report endpoints — Markdown and PDF export."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import PlainTextResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import get_db_session
from src.db.repository import get_investigation
from src.reports.generator import generate_markdown_report
from src.reports.pdf_exporter import export_pdf

router = APIRouter()


def _require_finished(record):
    """Raise 400 if investigation is still running."""
    if record.status not in ("completed", "failed"):
        raise HTTPException(
            status_code=400,
            detail=f"Investigation is still {record.status}. Report not yet available.",
        )


@router.get(
    "/investigations/{investigation_id}/report",
    response_class=PlainTextResponse,
)
async def get_investigation_report(
    investigation_id: str,
    session: AsyncSession = Depends(get_db_session),
) -> PlainTextResponse:
    """Get the RCA report as markdown."""
    record = await get_investigation(session, investigation_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Investigation not found")
    _require_finished(record)

    markdown_content = generate_markdown_report(record)
    return PlainTextResponse(content=markdown_content, media_type="text/markdown")


@router.get(
    "/investigations/{investigation_id}/report/pdf",
)
async def get_investigation_report_pdf(
    investigation_id: str,
    session: AsyncSession = Depends(get_db_session),
) -> Response:
    """Get the RCA report as a downloadable PDF."""
    record = await get_investigation(session, investigation_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Investigation not found")
    _require_finished(record)

    markdown_content = generate_markdown_report(record)
    pdf_bytes = export_pdf(markdown_content)

    filename = f"rca_report_{investigation_id}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
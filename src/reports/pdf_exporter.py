"""PDF Exporter — Converts markdown RCA reports to PDF using xhtml2pdf.

Pipeline: Markdown (str) → HTML (markdown lib + CSS) → PDF (xhtml2pdf).
"""

from __future__ import annotations

import io
from pathlib import Path

import markdown
from xhtml2pdf import pisa

from src.core.logging import get_logger

logger = get_logger("pdf_exporter")

STYLES_PATH = Path(__file__).parent / "templates" / "rca_styles.css"


def _load_css() -> str:
    """Load CSS styles for the PDF."""
    if STYLES_PATH.exists():
        return STYLES_PATH.read_text(encoding="utf-8")
    return ""


def markdown_to_html(md_content: str) -> str:
    """Convert markdown to a full HTML document with embedded CSS."""
    html_body = markdown.markdown(
        md_content,
        extensions=["tables", "fenced_code", "toc", "nl2br"],
    )
    css = _load_css()
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <title>RCA Report</title>
    <style>
{css}
    </style>
</head>
<body>
{html_body}
</body>
</html>"""


def export_pdf(md_content: str) -> bytes:
    """Convert a markdown RCA report to PDF bytes.

    Args:
        md_content: The markdown report string.

    Returns:
        PDF file content as bytes.
    """
    html_string = markdown_to_html(md_content)

    buffer = io.BytesIO()
    result = pisa.CreatePDF(io.StringIO(html_string), dest=buffer)

    if result.err:
        logger.error("pdf_export_failed", errors=result.err)
        raise RuntimeError(f"PDF generation failed with {result.err} errors")

    pdf_bytes = buffer.getvalue()
    logger.info("pdf_exported", size_bytes=len(pdf_bytes))
    return pdf_bytes


def export_pdf_to_file(md_content: str, output_path: str | Path) -> Path:
    """Convert a markdown RCA report to a PDF file on disk.

    Args:
        md_content: The markdown report string.
        output_path: Destination file path.

    Returns:
        The Path to the written PDF file.
    """
    output_path = Path(output_path)
    pdf_bytes = export_pdf(md_content)
    output_path.write_bytes(pdf_bytes)
    logger.info("pdf_saved", path=str(output_path), size_bytes=len(pdf_bytes))
    return output_path
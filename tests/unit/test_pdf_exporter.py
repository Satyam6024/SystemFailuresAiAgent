"""Unit tests for src/reports/pdf_exporter.py."""

from __future__ import annotations

import pytest

from src.reports.pdf_exporter import export_pdf, markdown_to_html


class TestMarkdownToHtml:
    def test_converts_heading(self):
        html = markdown_to_html("# Hello World")
        assert "<h1" in html
        assert "Hello World" in html

    def test_converts_table(self):
        md = "| Col1 | Col2 |\n|------|------|\n| A | B |"
        html = markdown_to_html(md)
        assert "<table>" in html
        assert "<td>" in html

    def test_wraps_in_html_doc(self):
        html = markdown_to_html("Some text")
        assert "<!DOCTYPE html>" in html
        assert "<html" in html
        assert "<body>" in html
        assert "</body>" in html

    def test_includes_css(self):
        html = markdown_to_html("test")
        assert "<style>" in html


class TestExportPdf:
    def test_generates_pdf_bytes(self):
        md = "# Test Report\n\nThis is a test report."
        pdf_bytes = export_pdf(md)
        assert isinstance(pdf_bytes, bytes)
        assert len(pdf_bytes) > 0

    def test_pdf_magic_bytes(self):
        """PDF files start with %PDF."""
        md = "# Test\n\nContent here."
        pdf_bytes = export_pdf(md)
        assert pdf_bytes[:4] == b"%PDF"

    def test_complex_markdown(self):
        md = """# RCA Report

## Summary
| Field | Value |
|-------|-------|
| Service | checkout-service |
| Severity | critical |

## Findings
- Agent found DB timeouts
- Latency correlated with deploy

## Root Cause
DB connection pool was reduced from 100 to 10.
"""
        pdf_bytes = export_pdf(md)
        assert pdf_bytes[:4] == b"%PDF"
        assert len(pdf_bytes) > 500

    def test_empty_markdown(self):
        pdf_bytes = export_pdf("")
        assert isinstance(pdf_bytes, bytes)
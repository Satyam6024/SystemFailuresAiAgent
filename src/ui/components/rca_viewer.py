"""RCA report viewer component."""

from __future__ import annotations

import streamlit as st


def render_rca_report(report_markdown: str):
    """Render a markdown RCA report inline."""
    st.markdown(report_markdown)


def render_findings_cards(findings: list[dict]):
    """Render agent findings as expandable cards."""
    if not findings:
        st.info("No findings yet.")
        return

    for f in findings:
        agent = f.get("agent_name", "Unknown Agent")
        confidence = f.get("confidence", 0)
        summary = f.get("summary", "No summary")
        evidence = f.get("evidence", [])

        # Color based on confidence
        if confidence >= 0.7:
            color = "#2ecc71"
        elif confidence >= 0.4:
            color = "#f39c12"
        else:
            color = "#e74c3c"

        with st.expander(
            f"**{agent}** — Confidence: {confidence:.0%}",
            expanded=True,
        ):
            st.markdown(
                f'<div style="border-left: 4px solid {color}; padding-left: 12px;">'
                f"{summary}</div>",
                unsafe_allow_html=True,
            )
            if evidence:
                st.markdown("**Evidence:**")
                for e in evidence:
                    st.markdown(f"- {e}")


def render_reasoning_trace(trace: list[str]):
    """Render the reasoning trace as a numbered timeline."""
    if not trace:
        return

    st.markdown("#### Reasoning Trace")
    for i, step in enumerate(trace, 1):
        # Truncate long entries
        display = step[:300] + "..." if len(step) > 300 else step
        st.markdown(f"**{i}.** {display}")
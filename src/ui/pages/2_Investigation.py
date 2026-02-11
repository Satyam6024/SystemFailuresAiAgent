"""Investigation page — Live investigation view with Chain-of-Thought graph."""

import time

import streamlit as st

from src.ui.components.api_client import api_get, api_get_bytes
from src.ui.components.cot_graph import render_cot_graph, render_status_legend
from src.ui.components.rca_viewer import (
    render_findings_cards,
    render_reasoning_trace,
)

st.header("Investigation")

# ── Get active investigation ────────────────────────────────────

# Check if we have a stored active investigation
active_id = st.session_state.get("active_investigation_id")

# Also check the health endpoint for a running investigation
health = api_get("/health")
if health and health.get("current_investigation_id"):
    active_id = health["current_investigation_id"]
    st.session_state["active_investigation_id"] = active_id

# Let user input an investigation ID manually
col1, col2 = st.columns([3, 1])
with col1:
    manual_id = st.text_input(
        "Investigation ID",
        value=active_id or "",
        placeholder="Enter investigation ID or trigger from Dashboard",
    )
with col2:
    st.write("")  # spacing
    st.write("")
    if st.button("Load", use_container_width=True):
        active_id = manual_id
        st.session_state["active_investigation_id"] = manual_id

if not active_id:
    st.info(
        "No active investigation. Go to the **Dashboard** page to trigger one, "
        "or enter an investigation ID above."
    )
    st.stop()

# ── Fetch investigation data ────────────────────────────────────

inv = api_get(f"/api/v1/investigations/{active_id}")

if inv is None:
    st.error(f"Investigation `{active_id}` not found.")
    st.stop()

# ── Status bar ──────────────────────────────────────────────────

status = inv.get("status", "unknown")
confidence = inv.get("confidence")

col1, col2, col3, col4 = st.columns(4)
with col1:
    status_colors = {
        "detecting": "🟡", "investigating": "🔵", "planning": "🔵",
        "deciding": "🟠", "acting": "🟣", "reporting": "📝",
        "completed": "🟢", "failed": "🔴",
    }
    st.metric("Status", f"{status_colors.get(status, '❓')} {status.title()}")
with col2:
    st.metric("Confidence", f"{confidence:.0%}" if confidence else "—")
with col3:
    st.metric("Findings", len(inv.get("findings", [])))
with col4:
    duration = inv.get("duration_seconds")
    st.metric("Duration", f"{duration:.1f}s" if duration else "Running...")

# ── Chain-of-Thought Graph ──────────────────────────────────────

st.subheader("Investigation Flow")
render_status_legend()
render_cot_graph(inv)

# ── Agent Findings ──────────────────────────────────────────────

st.subheader("Agent Findings")
render_findings_cards(inv.get("findings", []))

# ── Root Cause & Recommendation ─────────────────────────────────

if inv.get("root_cause"):
    st.subheader("Root Cause")
    st.markdown(inv["root_cause"])

if inv.get("recommendation"):
    st.subheader("Recommendation")
    st.info(inv["recommendation"])

if inv.get("remediation_action"):
    st.subheader("Remediation Action")
    st.warning(inv["remediation_action"])

# ── Reasoning Trace ─────────────────────────────────────────────

with st.expander("Reasoning Trace", expanded=False):
    render_reasoning_trace(inv.get("reasoning_trace", []))

# ── Errors ──────────────────────────────────────────────────────

if inv.get("agent_errors"):
    with st.expander("Agent Errors", expanded=False):
        for err in inv["agent_errors"]:
            st.error(err)

# ── Full Report + PDF Download ─────────────────────────────────

if status == "completed":
    st.divider()
    col_report, col_pdf = st.columns([3, 1])
    with col_report:
        st.subheader("Full Report")
    with col_pdf:
        pdf_bytes = api_get_bytes(f"/api/v1/investigations/{active_id}/report/pdf")
        if pdf_bytes:
            st.download_button(
                label="Download PDF",
                data=pdf_bytes,
                file_name=f"rca_report_{active_id}.pdf",
                mime="application/pdf",
                use_container_width=True,
            )

    with st.expander("Markdown Report", expanded=False):
        report = api_get(f"/api/v1/investigations/{active_id}/report")
        if report:
            st.markdown(report)

# ── Auto-refresh while running ──────────────────────────────────

if status not in ("completed", "failed"):
    st.info("Investigation is running. Auto-refreshing every 3 seconds...")
    time.sleep(3)
    st.rerun()
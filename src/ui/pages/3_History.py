"""History page — Past investigations table with drill-down."""

import streamlit as st

from src.ui.components.api_client import api_get, api_get_bytes

st.header("Investigation History")

# ── Filters ─────────────────────────────────────────────────────

col1, col2, col3 = st.columns([2, 1, 1])
with col1:
    status_filter = st.selectbox(
        "Filter by Status",
        options=["all", "completed", "failed", "investigating", "detecting"],
        key="history_status_filter",
    )
with col2:
    limit = st.selectbox("Results per page", options=[10, 25, 50], index=0)
with col3:
    offset = st.number_input("Offset", value=0, min_value=0, step=limit)

# ── Fetch investigations ────────────────────────────────────────

params = {"limit": limit, "offset": offset}
if status_filter != "all":
    params["status"] = status_filter

data = api_get("/api/v1/investigations", **params)

if data is None:
    st.stop()

investigations = data.get("investigations", [])
total = data.get("total", 0)

st.caption(f"Showing {len(investigations)} of {total} investigations")

if not investigations:
    st.info("No investigations found. Trigger one from the Dashboard!")
    st.stop()

# ── Table ───────────────────────────────────────────────────────

for inv in investigations:
    status = inv.get("status", "unknown")
    status_emoji = {
        "completed": "🟢", "failed": "🔴", "investigating": "🔵",
        "detecting": "🟡",
    }.get(status, "❓")

    confidence = inv.get("confidence")
    confidence_str = f"{confidence:.0%}" if confidence is not None else "—"

    duration = inv.get("duration_seconds")
    duration_str = f"{duration:.1f}s" if duration is not None else "—"

    col1, col2, col3, col4, col5, col6 = st.columns([2, 2, 1, 1, 1, 1])
    with col1:
        st.markdown(f"**`{inv['id']}`**")
    with col2:
        desc = inv.get("alert_description", "")
        st.caption(desc[:60] + "..." if len(desc) > 60 else desc)
    with col3:
        st.markdown(f"{status_emoji} {status}")
    with col4:
        st.markdown(confidence_str)
    with col5:
        st.markdown(duration_str)
    with col6:
        if st.button("View", key=f"view_{inv['id']}"):
            st.session_state["active_investigation_id"] = inv["id"]
            st.switch_page("pages/2_Investigation.py")

    st.divider()

# ── Detail view ─────────────────────────────────────────────────

st.subheader("Investigation Detail")

detail_id = st.text_input(
    "Enter Investigation ID to view details",
    value=st.session_state.get("history_detail_id", ""),
    key="history_detail_id",
)

if detail_id:
    inv = api_get(f"/api/v1/investigations/{detail_id}")
    if inv:
        st.json(inv)

        if inv.get("status") == "completed":
            report = api_get(f"/api/v1/investigations/{detail_id}/report")
            if report:
                with st.expander("Markdown Report"):
                    st.markdown(report)

            pdf_bytes = api_get_bytes(f"/api/v1/investigations/{detail_id}/report/pdf")
            if pdf_bytes:
                st.download_button(
                    label="Download PDF Report",
                    data=pdf_bytes,
                    file_name=f"rca_report_{detail_id}.pdf",
                    mime="application/pdf",
                )
    else:
        st.warning("Investigation not found.")
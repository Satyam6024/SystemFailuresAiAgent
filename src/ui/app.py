"""System Failures AI Agent — Streamlit main entry point."""

import os

import streamlit as st

st.set_page_config(
    page_title="System Failures AI Agent",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Sidebar ─────────────────────────────────────────────────────

st.sidebar.title("System Failures AI Agent")
st.sidebar.caption("Autonomous First Responder for System Failures")

# API base URL (env var in Docker, default for local dev)
if "api_url" not in st.session_state:
    st.session_state.api_url = os.environ.get("SFA_API_URL", "http://127.0.0.1:8000")

st.sidebar.text_input(
    "API Base URL",
    key="api_url",
    help="FastAPI backend URL",
)

st.sidebar.divider()
st.sidebar.markdown(
    "**Navigation**\n\n"
    "Use the pages in the sidebar to navigate between views."
)

# ── Main page content ───────────────────────────────────────────

st.title("System Failures AI Agent")
st.markdown(
    """
    Welcome to the **System Failures AI Agent** — an autonomous multi-agent system
    that diagnoses complex infrastructure failures in real-time.

    ### How it works

    1. **Detect** — An alert triggers the investigation
    2. **Plan** — The Commander agent creates an investigation plan
    3. **Investigate** — Three specialist agents work in parallel:
       - **Logs Agent** — Scans application logs for error patterns
       - **Metrics Agent** — Analyzes performance telemetry for anomalies
       - **Deploy Agent** — Reviews recent deployments and config changes
    4. **Decide** — The Commander synthesizes all findings into a root cause
    5. **Act** — If confidence is high, recommends remediation
    6. **Report** — Generates a full Root Cause Analysis report

    ### Pages

    - **Dashboard** — System health overview and investigation trigger
    - **Investigation** — Live investigation view with Chain-of-Thought graph
    - **History** — Past investigations and RCA reports
    - **Configuration** — Tune alert thresholds and agent parameters
    - **Live Monitor** — Real-time agent status and streaming output

    ---
    *Navigate using the sidebar to get started.*
    """
)
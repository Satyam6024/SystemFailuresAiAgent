"""Live Monitor page — Real-time agent status and investigation progress."""

import time

import streamlit as st

from src.ui.components.api_client import api_get

st.header("Live Monitor")

# ── Auto-refresh toggle ─────────────────────────────────────────

auto_refresh = st.toggle("Auto-refresh (every 2s)", value=True, key="monitor_auto_refresh")

# ── System Status ───────────────────────────────────────────────

health = api_get("/health")

if health is None:
    st.error("API server is not reachable.")
    st.stop()

col1, col2 = st.columns(2)
with col1:
    api_status = "🟢 Connected" if health else "🔴 Disconnected"
    st.metric("API Server", api_status)
with col2:
    running = health.get("investigation_running", False)
    inv_status = "🔵 Running" if running else "⚪ Idle"
    st.metric("Investigation Engine", inv_status)

# ── Active Investigation Monitor ────────────────────────────────

st.divider()
st.subheader("Active Investigation")

current_id = health.get("current_investigation_id")

if not current_id:
    # Check for recent completed investigation
    data = api_get("/api/v1/investigations", limit=1)
    if data and data.get("investigations"):
        latest = data["investigations"][0]
        current_id = latest["id"]
        st.caption(f"Showing most recent investigation: `{current_id}`")
    else:
        st.info("No investigations found. Trigger one from the Dashboard!")
        st.stop()
else:
    st.caption(f"Active investigation: `{current_id}`")

inv = api_get(f"/api/v1/investigations/{current_id}")

if inv is None:
    st.warning("Could not fetch investigation details.")
    st.stop()

# ── Agent Status Cards ──────────────────────────────────────────

st.subheader("Agent Status")

status = inv.get("status", "unknown")
findings = inv.get("findings", [])
agent_errors = inv.get("agent_errors", [])

# Determine per-agent status
agents = {
    "Commander": {"icon": "🎖️", "status": "idle", "output": ""},
    "Logs Agent": {"icon": "📋", "status": "idle", "output": ""},
    "Metrics Agent": {"icon": "📊", "status": "idle", "output": ""},
    "Deploy Agent": {"icon": "🚀", "status": "idle", "output": ""},
}

# Infer statuses from investigation state
if status in ("detecting", "planning"):
    agents["Commander"]["status"] = "active"
elif status == "investigating":
    agents["Commander"]["status"] = "completed"
    agents["Logs Agent"]["status"] = "active"
    agents["Metrics Agent"]["status"] = "active"
    agents["Deploy Agent"]["status"] = "active"
elif status in ("deciding", "acting", "reporting", "completed"):
    agents["Commander"]["status"] = "completed"
    agents["Logs Agent"]["status"] = "completed"
    agents["Metrics Agent"]["status"] = "completed"
    agents["Deploy Agent"]["status"] = "completed"

# Apply findings
for f in findings:
    name_map = {
        "logs_agent": "Logs Agent",
        "metrics_agent": "Metrics Agent",
        "deploy_agent": "Deploy Agent",
    }
    display_name = name_map.get(f.get("agent_name"), "")
    if display_name in agents:
        agents[display_name]["status"] = "completed"
        agents[display_name]["output"] = f.get("summary", "")[:200]

# Apply errors
for err in agent_errors:
    for key in agents:
        if key.lower().replace(" ", "_") in err.lower():
            agents[key]["status"] = "error"

# Render cards
cols = st.columns(4)
status_icons = {
    "idle": "⚪", "active": "🔵", "completed": "🟢", "error": "🔴",
}

for i, (name, info) in enumerate(agents.items()):
    with cols[i]:
        icon = status_icons.get(info["status"], "❓")
        st.markdown(
            f"""
            <div style="
                border: 1px solid #ddd;
                border-radius: 8px;
                padding: 16px;
                text-align: center;
                min-height: 150px;
            ">
                <div style="font-size: 2em;">{info['icon']}</div>
                <div style="font-weight: bold; margin: 8px 0;">{name}</div>
                <div>{icon} {info['status'].title()}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

# ── Investigation Timeline ──────────────────────────────────────

st.divider()
st.subheader("Reasoning Trace (Live)")

trace = inv.get("reasoning_trace", [])
if trace:
    for i, step in enumerate(trace, 1):
        display = step[:250] + "..." if len(step) > 250 else step
        st.markdown(f"**{i}.** {display}")
else:
    st.caption("Waiting for reasoning trace...")

# ── Investigation Metrics ───────────────────────────────────────

st.divider()
st.subheader("Investigation Metrics")

col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("Status", status.title())
with col2:
    confidence = inv.get("confidence")
    st.metric("Confidence", f"{confidence:.0%}" if confidence else "—")
with col3:
    st.metric("Findings", len(findings))
with col4:
    duration = inv.get("duration_seconds")
    st.metric("Duration", f"{duration:.1f}s" if duration else "—")

# ── Errors Panel ────────────────────────────────────────────────

if agent_errors:
    st.divider()
    st.subheader("Errors")
    for err in agent_errors:
        st.error(err)

# ── Auto-refresh ────────────────────────────────────────────────

if auto_refresh and status not in ("completed", "failed"):
    time.sleep(2)
    st.rerun()
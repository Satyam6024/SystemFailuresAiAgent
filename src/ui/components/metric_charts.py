"""Plotly time-series metric charts component."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

import plotly.graph_objects as go
import streamlit as st

from src.core.models import MetricDataPoint


def render_metric_chart(
    data_points: list[MetricDataPoint],
    metric_name: str,
    title: Optional[str] = None,
    threshold: Optional[float] = None,
    height: int = 300,
):
    """Render a Plotly time-series chart for a specific metric."""
    # Group by service
    series: dict[str, tuple[list[datetime], list[float]]] = {}
    for p in data_points:
        if p.metric_name != metric_name:
            continue
        svc = p.service.value
        if svc not in series:
            series[svc] = ([], [])
        series[svc][0].append(p.timestamp)
        series[svc][1].append(p.value)

    if not series:
        st.info(f"No data for metric: {metric_name}")
        return

    fig = go.Figure()

    colors = [
        "#3498db", "#e74c3c", "#2ecc71", "#f39c12",
        "#9b59b6", "#1abc9c", "#e67e22", "#34495e",
    ]

    for i, (svc, (timestamps, values)) in enumerate(sorted(series.items())):
        fig.add_trace(go.Scatter(
            x=timestamps,
            y=values,
            mode="lines+markers",
            name=svc,
            line=dict(color=colors[i % len(colors)], width=2),
            marker=dict(size=4),
        ))

    if threshold is not None:
        fig.add_hline(
            y=threshold,
            line_dash="dash",
            line_color="red",
            annotation_text=f"Threshold: {threshold}",
        )

    fig.update_layout(
        title=title or metric_name,
        xaxis_title="Time",
        yaxis_title=metric_name,
        height=height,
        margin=dict(l=40, r=20, t=40, b=40),
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        template="plotly_white",
    )

    st.plotly_chart(fig, use_container_width=True)


def render_multi_metric_dashboard(
    data_points: list[MetricDataPoint],
    metrics: list[str] | None = None,
    thresholds: dict[str, float] | None = None,
):
    """Render charts for multiple metrics in a grid."""
    if metrics is None:
        metrics = sorted(set(p.metric_name for p in data_points))
    if thresholds is None:
        thresholds = {}

    cols_per_row = 2
    for i in range(0, len(metrics), cols_per_row):
        cols = st.columns(cols_per_row)
        for j, col in enumerate(cols):
            idx = i + j
            if idx >= len(metrics):
                break
            metric = metrics[idx]
            with col:
                render_metric_chart(
                    data_points,
                    metric,
                    threshold=thresholds.get(metric),
                    height=280,
                )
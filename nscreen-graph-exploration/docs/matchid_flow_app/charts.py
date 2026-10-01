"""Charts for matchid flow metrics."""

from __future__ import annotations

import altair as alt
import pandas as pd
from data import FLOW_ORDER

REASON_COLORS = {
    "LR": "#2563EB",
    "TH": "#F59E0B",
    "EX": "#8B5CF6",
    "LRTH": "#14B8A6",
    "LREX": "#6366F1",
    "THEX": "#D97706",
    "LRTHEX": "#0F766E",
    "IC": "#EF4444",
    "LU": "#64748B",
    "NA": "#CBD5E1",
}


def _compact_count(value: int) -> str:
    """Format counts compactly without hiding exact hover values."""
    if value >= 1_000_000_000:
        return f"{value / 1_000_000_000:.2f}B"
    if value >= 1_000_000:
        return f"{value / 1_000_000:.1f}M"
    if value >= 1_000:
        return f"{value / 1_000:.1f}K"
    return f"{value:,}"


def reason_attribution_chart(
    stage_reason: pd.DataFrame, final_reason: pd.DataFrame
) -> alt.Chart:
    """Show independent reason counts without implying conserved flow."""
    intermediate = stage_reason[["stage_label", "reason", "matchids", "rows"]].copy()
    final = final_reason[["reason", "matchids", "rows"]].copy()
    final["stage_label"] = "Final"
    plot = pd.concat([intermediate, final], ignore_index=True)
    largest = max(int(plot["matchids"].max()), 1)
    plot["visual_size"] = 500 + 1500 * (plot["matchids"] / largest) ** 0.5
    plot["label"] = plot["matchids"].map(_compact_count)

    stage_order = ["Vendor alignment", "IC stage 1", "IC stage 2", "LU", "Final"]
    reason_order = list(REASON_COLORS)
    color_scale = alt.Scale(
        domain=reason_order, range=[REASON_COLORS[item] for item in reason_order]
    )
    circles = (
        alt.Chart(plot)
        .mark_circle(opacity=0.24, strokeWidth=2)
        .encode(
            x=alt.X(
                "stage_label:N",
                sort=stage_order,
                title=None,
                axis=alt.Axis(labelAngle=0),
            ),
            y=alt.Y("reason:N", sort=reason_order, title="Reason"),
            size=alt.Size("visual_size:Q", scale=None, legend=None),
            color=alt.Color("reason:N", scale=color_scale, legend=None),
            stroke=alt.Color("reason:N", scale=color_scale, legend=None),
            tooltip=[
                alt.Tooltip("stage_label:N", title="Stage"),
                alt.Tooltip("reason:N", title="Reason"),
                alt.Tooltip("matchids:Q", title="Distinct matchids", format=","),
                alt.Tooltip("rows:Q", title="Rows", format=","),
            ],
        )
    )
    labels = (
        alt.Chart(plot)
        .mark_text(fontSize=12, fontWeight=600)
        .encode(
            x=alt.X("stage_label:N", sort=stage_order),
            y=alt.Y("reason:N", sort=reason_order),
            text="label:N",
        )
    )
    return (circles + labels).properties(height=330)


def flow_chart(flow: pd.DataFrame) -> alt.Chart:
    """Render cumulative exact-matchid checkpoints as connected points."""
    plot = flow.copy()
    plot["checkpoint"] = plot["checkpoint"].astype("string")
    plot["matchids_m"] = plot["matchids"] / 1_000_000
    plot["label"] = plot["matchids"].map(lambda value: f"{value / 1_000_000:,.1f}M")

    line = (
        alt.Chart(plot)
        .mark_line(color="#94A3B8", strokeWidth=3)
        .encode(
            x=alt.X(
                "checkpoint:N", sort=FLOW_ORDER, title=None, axis=alt.Axis(labelAngle=0)
            ),
            y=alt.Y(
                "matchids_m:Q",
                title="Distinct matchids (millions)",
                scale=alt.Scale(zero=False),
            ),
        )
    )
    points = (
        alt.Chart(plot)
        .mark_circle(size=650, color="#0F766E", stroke="white", strokeWidth=3)
        .encode(
            x=alt.X("checkpoint:N", sort=FLOW_ORDER, title=None),
            y=alt.Y("matchids_m:Q", title="Distinct matchids (millions)"),
            tooltip=[
                alt.Tooltip("checkpoint:N", title="Checkpoint"),
                alt.Tooltip("matchids:Q", title="Distinct matchids", format=","),
                alt.Tooltip("rows:Q", title="Rows", format=","),
                alt.Tooltip("retained_pct:Q", title="Source retained", format=".1%"),
            ],
        )
    )
    labels = (
        alt.Chart(plot)
        .mark_text(dy=-23, fontSize=13, fontWeight=600, color="#0F172A")
        .encode(
            x=alt.X("checkpoint:N", sort=FLOW_ORDER),
            y="matchids_m:Q",
            text="label:N",
        )
    )
    return (line + points + labels).properties(height=330)


def source_chart(sources: pd.DataFrame) -> alt.Chart:
    """Compare distinct source matchids across vendors."""
    return (
        alt.Chart(sources)
        .mark_bar(cornerRadiusEnd=5)
        .encode(
            y=alt.Y("vendor:N", title=None, sort="-x"),
            x=alt.X("matchids:Q", title="Distinct matchids"),
            color=alt.Color("vendor:N", title=None, legend=None),
            tooltip=[
                alt.Tooltip("vendor:N", title="Vendor"),
                alt.Tooltip("matchids:Q", title="Distinct matchids", format=","),
                alt.Tooltip("rows:Q", title="Rows", format=","),
            ],
        )
        .properties(height=235)
    )


def stage_reason_chart(stage_reason: pd.DataFrame) -> alt.Chart:
    """Show matchid attribution by intermediate stage and reason."""
    stage_order = ["Vendor alignment", "IC stage 1", "IC stage 2", "LU"]
    reasons = list(REASON_COLORS)
    return (
        alt.Chart(stage_reason)
        .mark_bar(cornerRadiusTopLeft=2, cornerRadiusTopRight=2)
        .encode(
            x=alt.X(
                "stage_label:N",
                sort=stage_order,
                title=None,
                axis=alt.Axis(labelAngle=0),
            ),
            y=alt.Y("matchids:Q", title="Distinct matchids within stage and reason"),
            color=alt.Color(
                "reason:N",
                title="Reason",
                scale=alt.Scale(
                    domain=reasons, range=[REASON_COLORS[item] for item in reasons]
                ),
                legend=alt.Legend(orient="bottom"),
            ),
            order=alt.Order("reason:N"),
            tooltip=[
                alt.Tooltip("stage_label:N", title="Stage"),
                alt.Tooltip("reason:N", title="Reason"),
                alt.Tooltip("matchids:Q", title="Distinct matchids", format=","),
                alt.Tooltip("rows:Q", title="Rows", format=","),
            ],
        )
        .properties(height=330)
    )


def final_reason_chart(final_reason: pd.DataFrame) -> alt.Chart:
    """Show final output's distinct matchids grouped by reason."""
    reasons = list(REASON_COLORS)
    return (
        alt.Chart(final_reason)
        .mark_bar(cornerRadiusEnd=5)
        .encode(
            y=alt.Y("reason:N", sort="-x", title=None),
            x=alt.X("matchids:Q", title="Distinct matchids"),
            color=alt.Color(
                "reason:N",
                title=None,
                scale=alt.Scale(
                    domain=reasons, range=[REASON_COLORS[item] for item in reasons]
                ),
                legend=None,
            ),
            tooltip=[
                alt.Tooltip("reason:N", title="Reason"),
                alt.Tooltip("matchids:Q", title="Distinct matchids", format=","),
                alt.Tooltip("rows:Q", title="Rows", format=","),
            ],
        )
        .properties(height=330)
    )

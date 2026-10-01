"""Daily NScreen identity metrics dashboard."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pandas as pd
import streamlit as st
from charts import (
    final_reason_chart,
    source_chart,
    stage_reason_chart,
)
from data import (
    TrinoConfigError,
    load_available_days,
    load_materialized_snapshot,
)
from pipeline_chart import identity_pipeline_chart

METRIC_GROUP_LABELS = {
    "source_liveramp": "LiveRamp source",
    "source_throtle": "Throtle source",
    "source_experian": "Experian source",
    "stage_flow": "pipeline stage totals",
    "stage_reason": "stage attribution",
    "final": "published output",
    "representation_source_liveramp": "LiveRamp alignment outcomes",
    "representation_source_throtle": "Throtle alignment outcomes",
    "representation_source_experian": "Experian alignment outcomes",
    "graph_clean": "clean collocation graph",
    "graph_remainder": "unassigned collocation graph",
    "stage_publication": "stage publication outcomes",
    "uid_membership": "UID vendor and reason overlap",
}

st.set_page_config(
    page_title="NScreen matchid flow",
    page_icon=":material/account_tree:",
    layout="wide",
)


@st.cache_data(ttl="10m", max_entries=4, show_spinner=False)
def cached_available_days() -> pd.DataFrame:
    """Cache tiny materialization-status lookup."""
    return load_available_days()


@st.cache_data(ttl="10m", max_entries=60, show_spinner=False)
def cached_materialized_snapshot(selected_day: str) -> dict[str, object]:
    """Cache one tiny materialized partition."""
    return load_materialized_snapshot(selected_day)


st.title("NScreen matchid flow")
st.caption(
    "Daily identity volume across vendor inputs, alignment, collocation, "
    "clustering, and published output."
)

st.session_state.setdefault("materialized_days", [])
st.session_state.setdefault("rendered_snapshot", None)
st.session_state.setdefault("rendered_day", None)

with st.sidebar:
    st.header("Daily snapshot")
    today = datetime.now(timezone.utc).date()
    if st.session_state.materialized_days:
        default_day = (
            st.session_state.rendered_day
            if st.session_state.rendered_day in st.session_state.materialized_days
            else st.session_state.materialized_days[0]
        )
        requested_day = st.selectbox(
            "Pipeline day",
            st.session_state.materialized_days,
            index=st.session_state.materialized_days.index(default_day),
            key="materialized_day_select",
        )
    else:
        requested_day = st.date_input(
            "Pipeline day",
            value=today - timedelta(days=1),
            max_value=today,
            key="materialized_day_input",
            help="Available dates load with the first snapshot.",
        )
    load_snapshot = st.button(
        "Load snapshot",
        type="primary",
        icon=":material/database:",
        width="stretch",
    )

if load_snapshot:
    try:
        available_days = cached_available_days()
    except (TrinoConfigError, OSError, RuntimeError):
        st.error(
            "Available dates could not be loaded. Confirm Trino access and try again.",
            icon=":material/error:",
        )
        st.stop()
    if available_days.empty:
        st.warning("No pipeline snapshots are available.")
        st.stop()
    day_options = available_days["day"].astype("string").tolist()
    st.session_state.materialized_days = day_options
    requested_day_string = str(requested_day)
    if requested_day_string not in day_options:
        st.warning(
            f"No snapshot is available for {requested_day_string}. "
            "Choose an available date."
        )
        st.stop()
    try:
        st.session_state.rendered_snapshot = cached_materialized_snapshot(
            requested_day_string
        )
    except (TrinoConfigError, OSError, RuntimeError):
        st.error(
            "Snapshot could not be loaded. Confirm Trino access and try again.",
            icon=":material/error:",
        )
        st.stop()
    st.session_state.rendered_day = requested_day_string
    st.rerun()

snapshot = st.session_state.rendered_snapshot
selected_day = st.session_state.rendered_day

if snapshot is None:
    st.info("Choose a pipeline day, then load its snapshot.", icon=":material/database:")
    st.stop()

filters_changed = str(requested_day) != selected_day
if filters_changed:
    st.warning("Pipeline day changed. Load its snapshot to refresh results.")

status = snapshot["status"]
metrics = snapshot["metrics"]
if status is None or metrics is None:
    st.warning(f"No snapshot data is available for {selected_day}.")
    st.stop()

state = str(status["state"])
missing_groups = list(status["missing_groups"])
if state == "partial":
    missing_labels = [
        METRIC_GROUP_LABELS.get(group, group.replace("_", " "))
        for group in missing_groups
    ]
    st.warning(
        "Snapshot incomplete. Unavailable metrics: " + ", ".join(missing_labels),
        icon=":material/warning:",
    )
elif state != "complete":
    st.error("Snapshot processing did not complete.", icon=":material/error:")
    st.stop()

sources = metrics["sources"]
flow = metrics["flow"]
stage_reason = metrics["stage_reason"]
final_reason = metrics["final_reason"]
representation = metrics.get("vendor_representation", pd.DataFrame())
graph_size = metrics.get("graph_size", pd.DataFrame())
publication = metrics.get("stage_publication", pd.DataFrame())
complete_flow = state == "complete" and set(flow["checkpoint"].astype("string")) == {
    "Vendor sources",
    "Vendor alignment",
    "After IC stage 1",
    "After IC stage 2",
    "After LU / final",
}

display_day = pd.Timestamp(str(selected_day)).date()
st.subheader(display_day.strftime("%A, %d %B %Y"))

if complete_flow:
    source_total = int(
        flow.loc[
            flow.checkpoint.astype("string").eq("Vendor sources"), "matchids"
        ].iloc[0]
    )
    aligned_total = int(
        flow.loc[
            flow.checkpoint.astype("string").eq("Vendor alignment"), "matchids"
        ].iloc[0]
    )
    final_total = int(
        flow.loc[
            flow.checkpoint.astype("string").eq("After LU / final"), "matchids"
        ].iloc[0]
    )
    reduction = source_total - final_total
    reduction_pct = reduction / source_total if source_total else 0.0
    with st.container(horizontal=True):
        st.metric(
            "Source matchids",
            source_total,
            format="compact",
            icon=":material/input:",
            border=True,
            help="Sum of exact per-vendor counts. Shared cross-vendor IDs remain additive.",
        )
        st.metric(
            "After vendor alignment",
            aligned_total,
            delta=aligned_total - source_total,
            delta_color="inverse",
            format="compact",
            icon=":material/hub:",
            border=True,
        )
        st.metric(
            "Final matchids",
            final_total,
            delta=final_total - aligned_total,
            delta_color="off",
            format="compact",
            icon=":material/account_tree:",
            border=True,
        )
        st.metric(
            "Net reduction",
            reduction,
            delta=reduction_pct,
            delta_color="off",
            format="compact",
            icon=":material/compress:",
            border=True,
        )

    matchid_tab, uid_tab = st.tabs(["Matchids", "UIDs"])
    with matchid_tab:
        st.subheader("Matchid identity pipeline")
        st.caption(
            "Band width represents exact matchid counts. Shared vendor attribution overlaps, "
            "so reason and stage totals are not additive. Stage-to-Final bands show measured "
            "stage counts and stack at Final for comparison. Dashed links show seed dependencies. "
            "Graph nodes report UIDs and relationships separately."
        )
        if representation.empty or graph_size.empty or publication.empty:
            st.warning(
                "Some pipeline breakdowns are unavailable for this day. "
                "Unmeasured flows are labeled in the chart."
            )
        pipeline_figure = identity_pipeline_chart(
            sources, flow, stage_reason, representation, graph_size
        )
        st.plotly_chart(
            pipeline_figure,
            theme=None,
            width="stretch",
            height=int(pipeline_figure.layout.height),
            config={"displayModeBar": False, "responsive": True},
        )
    with uid_tab:
        st.subheader("UID identity pipeline")
        uid_metrics = metrics["uids"]
        missing_uid_metrics = []
        for vendor in ("LiveRamp", "Throtle", "Experian"):
            if vendor not in set(uid_metrics["sources"].vendor):
                missing_uid_metrics.append(f"{vendor} source UIDs")
        for checkpoint in ("Vendor alignment", "After LU / final"):
            if checkpoint not in set(uid_metrics["flow"].checkpoint.astype("string")):
                missing_uid_metrics.append(f"{checkpoint} UIDs")
        if uid_metrics["stage_reason"].empty:
            missing_uid_metrics.append("stage attribution UIDs")
        if uid_metrics["membership"].empty:
            missing_uid_metrics.append("vendor and reason overlap UIDs")
        if missing_uid_metrics:
            st.info(
                "UID analysis is incomplete for this day:\n\n"
                + "\n".join(f"- {item}" for item in missing_uid_metrics)
            )
        else:
            if uid_metrics["membership"].reason.eq("multiple_reasons").any():
                st.warning(
                    "Some UIDs have multiple initial reasons. They appear once in the "
                    "'Multiple initial reasons' branch. Other reason branches show only "
                    "UIDs assigned exclusively to that reason; no reason is chosen arbitrarily."
                )
            st.caption(
                "Band width represents distinct UIDs. Vendor bands are exact at source, while "
                "overlap positions at receiving reasons are directional rather than set intersections. "
                "Dashed links show seed dependencies. Collocation branches show measured assignments "
                "and do not form an exhaustive partition of clean UIDs. Remainder shows "
                "same-geo UIDs still unassigned after IC2."
            )
            uid_figure = identity_pipeline_chart(
                uid_metrics["sources"],
                uid_metrics["flow"],
                uid_metrics["stage_reason"],
                graph_size=graph_size,
                unit="uids",
                membership=uid_metrics["membership"],
                aggregate_vendor_bands=True,
            )
            final_node = next(
                n for n in uid_figure.layout.meta["nodes"] if n["key"] == "final"
            )
            stage_uid_sum = sum(
                e["count"] or 0
                for e in uid_figure.layout.meta["links"]
                if e["target"] == "final"
            )
            if stage_uid_sum != final_node["count"]:
                st.warning(
                    f"Stage UID counts sum to {stage_uid_sum:,}, but Final has {final_node['count']:,} distinct UIDs. "
                    "The stacked bands are not a reconciled partition; stage overlap or publication differences need investigation."
                )
            st.plotly_chart(
                uid_figure,
                theme=None,
                width="stretch",
                height=int(uid_figure.layout.height),
                config={"displayModeBar": False, "responsive": True},
            )
elif state == "partial":
    st.info("Cumulative flow requires a complete daily snapshot.")

if state == "partial" and not sources.empty:
    with st.container(border=True):
        st.subheader("Vendor sources")
        st.altair_chart(source_chart(sources), width="stretch")

if state == "partial" and not stage_reason.empty:
    with st.container(border=True):
        st.subheader("Intermediate attribution")
        st.caption("Bars count exact matchids within each stage and reason.")
        st.altair_chart(stage_reason_chart(stage_reason), width="stretch")

if state == "partial" and not final_reason.empty:
    with st.container(border=True):
        st.subheader("Final matchids by reason")
        st.altair_chart(final_reason_chart(final_reason), width="stretch")

with st.expander("Metric definitions"):
    st.markdown(
        """
- **Vendor sources:** sum of exact per-vendor distinct `matchid` counts.
- **Vendor alignment:** exact distinct matchids after vendor reconciliation.
- **IC:** cumulative exact matchids after each identity-collocation stage.
- **LU / final:** published identities after graph clustering.
- **Reason counts are non-additive:** one matchid can occur under multiple reasons.
- **Data source:** daily Trino summary tables.
"""
    )

"""Read and normalize materialized NScreen matchid metrics from Trino."""

from __future__ import annotations

import getpass
import importlib
import os
import sys
from datetime import date
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv

CATALOG_SCHEMA = "iceberg.jteixeira_ipa"
METRICS_TABLE = f"{CATALOG_SCHEMA}.nscreen_matchid_metrics_daily"
STATUS_TABLE = f"{CATALOG_SCHEMA}.nscreen_matchid_metrics_daily_status"

FLOW_ORDER = [
    "Vendor sources",
    "Vendor alignment",
    "After IC stage 1",
    "After IC stage 2",
    "After LU / final",
]

STAGE_LABELS = {
    "initial": "Vendor alignment",
    "stage1": "IC stage 1",
    "stage2": "IC stage 2",
    "louvain": "LU",
}


class TrinoConfigError(RuntimeError):
    """Raised when local PulsePoint Trino configuration is incomplete."""


def iso_day(day: date | str) -> str:
    """Return validated ISO date text safe for SQL interpolation."""
    return date.fromisoformat(str(day)).isoformat()


def bootstrap_dbfuncs():
    """Load user-owned dbfuncs without permitting interactive prompts."""
    config_dir = Path(
        os.environ.get("PULSEPOINT_HOME", Path.home() / ".pulsepoint")
    ).expanduser()
    env_path = config_dir / ".env"
    if not env_path.is_file():
        raise TrinoConfigError(f"Missing Trino configuration: {env_path}")

    load_dotenv(env_path, override=False)
    required = [
        "TRINO_USER",
        "TRINO_HOST",
        "TRINO_PORT",
        "TRINO_CATALOG",
        "TRINO_PASSWORD",
    ]
    missing = [name for name in required if not os.environ.get(name)]
    if missing:
        raise TrinoConfigError(f"Missing Trino settings: {', '.join(missing)}")

    explicit = os.environ.get("PULSEPOINT_DBFUNCS")
    dbfuncs_path = (
        Path(explicit).expanduser() if explicit else config_dir / "dbfuncs.py"
    )
    if dbfuncs_path.is_dir():
        dbfuncs_path = dbfuncs_path / "dbfuncs.py"
    if not dbfuncs_path.is_file():
        raise TrinoConfigError(f"Missing dbfuncs.py: {dbfuncs_path}")

    def no_prompt(prompt: str = "Password: ") -> str:
        raise TrinoConfigError(
            "TRINO_PASSWORD must be configured before launching Streamlit."
        )

    original = getpass.getpass
    getpass.getpass = no_prompt
    sys.path.insert(0, str(dbfuncs_path.parent))
    try:
        return importlib.import_module("dbfuncs")
    finally:
        getpass.getpass = original


def build_available_days_query() -> str:
    """Return lightweight status query used by day selector."""
    return f"""
SELECT day, state, missing_groups, completed_at
FROM {STATUS_TABLE}
WHERE state IN ('complete', 'partial')
ORDER BY day DESC
""".strip()


def build_materialized_query(day: date | str) -> str:
    """Return one small query joining daily metrics and refresh status."""
    selected_day = iso_day(day)
    return f"""
SELECT
    s.day,
    s.state,
    s.available_groups,
    s.missing_groups,
    s.started_at,
    s.completed_at,
    s.error_message,
    m.metric_type,
    m.dimension_1,
    m.dimension_2,
    m.matchids,
    m.rows,
    m.count_method,
    m.computed_at
FROM {STATUS_TABLE} AS s
LEFT JOIN {METRICS_TABLE} AS m ON s.day = m.day
WHERE s.day = '{selected_day}'
ORDER BY m.metric_type, m.dimension_1, m.dimension_2
""".strip()


def normalize_metrics(raw: pd.DataFrame, *, include_uids=True) -> dict:
    """Split materialized rows into typed dashboard datasets."""
    expected = {"metric_type", "dimension_1", "dimension_2", "matchids", "rows"}
    missing = expected.difference(raw.columns)
    if missing:
        raise ValueError(f"Metrics query lacks columns: {', '.join(sorted(missing))}")

    frame = raw.loc[raw["metric_type"].notna(), list(expected)].copy()
    for column in ("matchids", "rows"):
        numeric = pd.to_numeric(frame[column], errors="raise")
        frame[column] = numeric.astype("Int64" if numeric.isna().any() else "int64")

    sources = frame.loc[frame.metric_type.eq("source")].rename(
        columns={"dimension_1": "vendor"}
    )
    flow = frame.loc[frame.metric_type.eq("flow")].rename(
        columns={"dimension_1": "checkpoint"}
    )
    stage_reason = frame.loc[frame.metric_type.eq("stage_reason")].rename(
        columns={"dimension_1": "stage", "dimension_2": "reason"}
    )
    final_reason = frame.loc[frame.metric_type.eq("final_reason")].rename(
        columns={"dimension_1": "reason"}
    )

    if not sources.empty and not flow.checkpoint.eq("Vendor sources").any():
        source_total = pd.DataFrame(
            [
                {
                    "checkpoint": "Vendor sources",
                    "matchids": sources["matchids"].sum(),
                    "rows": sources["rows"].sum(),
                }
            ]
        )
        flow = pd.concat([flow, source_total], ignore_index=True)

    flow["checkpoint"] = pd.Categorical(
        flow.get("checkpoint", pd.Series(dtype="string")), FLOW_ORDER, ordered=True
    )
    flow = flow.sort_values("checkpoint").reset_index(drop=True)
    flow["previous_matchids"] = flow["matchids"].shift(1)
    flow["change"] = flow["matchids"] - flow["previous_matchids"]
    source_rows = flow.loc[flow.checkpoint.astype("string").eq("Vendor sources")]
    source_count = int(source_rows.matchids.iloc[0]) if not source_rows.empty else 0
    flow["retained_pct"] = flow["matchids"] / source_count if source_count else pd.NA

    stage_reason["stage_label"] = (
        stage_reason["stage"].map(STAGE_LABELS).fillna(stage_reason["stage"])
    )
    stage_reason["stage_order"] = stage_reason["stage"].map(
        {name: index for index, name in enumerate(STAGE_LABELS)}
    )
    stage_reason = stage_reason.sort_values(["stage_order", "reason"]).reset_index(
        drop=True
    )

    result = {
        "membership": frame.loc[
            frame.metric_type.eq("membership"),
            ["dimension_1", "dimension_2", "matchids"],
        ].rename(
            columns={
                "dimension_1": "reason",
                "dimension_2": "mask",
                "matchids": "count",
            }
        ),
        "vendor_representation": frame.loc[
            frame.metric_type.eq("vendor_representation"),
            ["dimension_1", "dimension_2", "matchids", "rows"],
        ].rename(columns={"dimension_1": "vendor", "dimension_2": "outcome"}),
        "graph_size": frame.loc[
            frame.metric_type.eq("graph_size"),
            ["dimension_1", "dimension_2", "rows"],
        ].rename(
            columns={"dimension_1": "graph", "dimension_2": "unit", "rows": "count"}
        ),
        "stage_publication": frame.loc[
            frame.metric_type.eq("stage_publication"),
            ["dimension_1", "dimension_2", "matchids", "rows"],
        ].rename(columns={"dimension_1": "stage", "dimension_2": "outcome"}),
        "sources": sources[["vendor", "matchids", "rows"]].reset_index(drop=True),
        "flow": flow[["checkpoint", "matchids", "rows", "change", "retained_pct"]],
        "stage_reason": stage_reason[
            ["stage", "stage_label", "reason", "matchids", "rows"]
        ],
        "final_reason": final_reason[["reason", "matchids", "rows"]].sort_values(
            "matchids", ascending=False
        ),
    }
    if include_uids:
        uid_rows = raw.loc[raw.metric_type.fillna("").str.startswith("uid_")].copy()
        uid_rows["metric_type"] = uid_rows.metric_type.str.removeprefix("uid_")
        result["uids"] = normalize_metrics(uid_rows, include_uids=False)
    return result


def load_available_days(dbfuncs=None) -> pd.DataFrame:
    """Load committed materialized days."""
    client = dbfuncs or bootstrap_dbfuncs()
    return client.query2df(build_available_days_query(), print_time=False)


def load_materialized_snapshot(day: date | str, dbfuncs=None) -> dict[str, object]:
    """Load one committed materialized day and normalize its metrics."""
    client = dbfuncs or bootstrap_dbfuncs()
    raw = client.query2df(build_materialized_query(day), print_time=False)
    if raw.empty:
        return {"status": None, "metrics": None}

    first = raw.iloc[0]
    status = {
        "day": str(first["day"]),
        "state": first["state"],
        "available_groups": list(first["available_groups"] or []),
        "missing_groups": list(first["missing_groups"] or []),
        "started_at": first["started_at"],
        "completed_at": first["completed_at"],
        "error_message": first["error_message"],
    }
    return {"status": status, "metrics": normalize_metrics(raw)}

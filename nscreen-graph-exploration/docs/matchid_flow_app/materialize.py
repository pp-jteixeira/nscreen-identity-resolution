"""Materialize exact daily matchid metrics into sandbox Iceberg tables."""

from __future__ import annotations

import argparse
import time
from collections.abc import Iterable
from datetime import date, datetime, timezone

from data import (
    METRICS_TABLE,
    STATUS_TABLE,
    bootstrap_dbfuncs,
    iso_day,
)
from flow_metrics import GRAPH_TABLES, graph_sql, publication_sql, representation_sql
from uid_membership import membership_sql

SOURCE_TABLES = {
    "source_liveramp": ("LiveRamp", "iceberg.crossscreen.liveramp_source"),
    "source_throtle": ("Throtle", "iceberg.crossscreen.throtle_source"),
    "source_experian": ("Experian", "iceberg.crossscreen.experian_source"),
}
STAGED_TABLE = "iceberg.crossscreen.nscreen_liveramp_throtle_ex_reason_staged"
FINAL_TABLE = "iceberg.crossscreen.nscreen_lr_throtle_ex_reason_result"
EXPECTED_GROUPS = [
    *SOURCE_TABLES,
    "stage_flow",
    "stage_reason",
    "final",
    *[f"representation_{group}" for group in SOURCE_TABLES],
    *GRAPH_TABLES,
    "stage_publication",
    "uid_membership",
]
COMMITTED_STATES = {"complete", "partial"}

METRICS_DDL = f"""
CREATE TABLE IF NOT EXISTS {METRICS_TABLE} (
    day VARCHAR,
    metric_type VARCHAR,
    dimension_1 VARCHAR,
    dimension_2 VARCHAR,
    matchids BIGINT,
    rows BIGINT,
    count_method VARCHAR,
    computed_at TIMESTAMP(3) WITH TIME ZONE
)
WITH (partitioning = ARRAY['day'])
""".strip()

STATUS_DDL = f"""
CREATE TABLE IF NOT EXISTS {STATUS_TABLE} (
    day VARCHAR,
    state VARCHAR,
    available_groups ARRAY(VARCHAR),
    missing_groups ARRAY(VARCHAR),
    started_at TIMESTAMP(3) WITH TIME ZONE,
    completed_at TIMESTAMP(3) WITH TIME ZONE,
    error_message VARCHAR
)
WITH (partitioning = ARRAY['day'])
""".strip()


def sql_string(value: str) -> str:
    """Quote one SQL string literal."""
    return "'" + value.replace("'", "''") + "'"


def sql_array(values: Iterable[str]) -> str:
    """Build typed Trino varchar-array syntax."""
    items = list(values)
    if not items:
        return "CAST(ARRAY[] AS ARRAY(VARCHAR))"
    return "ARRAY[" + ", ".join(sql_string(value) for value in items) + "]"


def build_availability_query() -> str:
    """Read cheap Iceberg partition metadata for every required input."""
    graph_metadata = "\nUNION ALL\n".join(
        f"SELECT '{group}', partition.day FROM "
        f'iceberg.crossscreen."{table.rsplit(".", 1)[1]}$partitions"'
        for group, table in GRAPH_TABLES.items()
    )
    return """
SELECT group_name, day
FROM (
    SELECT 'source_liveramp' AS group_name, partition.day AS day
    FROM iceberg.crossscreen."liveramp_source$partitions"

    UNION ALL
    SELECT 'source_throtle', partition.day
    FROM iceberg.crossscreen."throtle_source$partitions"

    UNION ALL
    SELECT 'source_experian', partition.day
    FROM iceberg.crossscreen."experian_source$partitions"

    UNION ALL
    SELECT 'stage_flow', partition.day
    FROM iceberg.crossscreen."nscreen_liveramp_throtle_ex_reason_staged$partitions"
    WHERE partition.stage IN ('initial', 'stage1', 'stage2')
    GROUP BY partition.day
    HAVING count(DISTINCT partition.stage) = 3

    UNION ALL
    SELECT 'stage_reason', partition.day
    FROM iceberg.crossscreen."nscreen_liveramp_throtle_ex_reason_staged$partitions"
    WHERE partition.stage IN ('initial', 'stage1', 'stage2', 'louvain')
    GROUP BY partition.day
    HAVING count(DISTINCT partition.stage) = 4

    UNION ALL
    SELECT 'final', partition.day
    FROM iceberg.crossscreen."nscreen_lr_throtle_ex_reason_result$partitions"
    UNION ALL
    SELECT 'initial', partition.day
    FROM iceberg.crossscreen."nscreen_liveramp_throtle_ex_reason_staged$partitions"
    WHERE partition.stage = 'initial'
    UNION ALL
    {graph_metadata}
)
ORDER BY day, group_name
""".replace("{graph_metadata}", graph_metadata).strip()


def load_availability(dbfuncs) -> dict[str, set[str]]:
    """Map each available day to complete input groups."""
    frame = dbfuncs.query2df(build_availability_query(), print_time=False)
    availability: dict[str, set[str]] = {}
    for row in frame.itertuples(index=False):
        availability.setdefault(str(row.day), set()).add(str(row.group_name))
    for groups in availability.values():
        if "initial" in groups:
            groups.update(
                f"representation_{group}" for group in SOURCE_TABLES if group in groups
            )
        if {"stage_reason", "final"}.issubset(groups):
            groups.add("stage_publication")
        if {"initial", *SOURCE_TABLES}.issubset(groups):
            groups.add("uid_membership")
    return availability


def ensure_tables(dbfuncs) -> None:
    """Create sandbox tables idempotently."""
    dbfuncs.run_query(METRICS_DDL, print_time=False)
    dbfuncs.run_query(STATUS_DDL, print_time=False)


def current_state(dbfuncs, day: str) -> str | None:
    """Return existing committed status for one day."""
    frame = dbfuncs.query2df(
        f"SELECT state FROM {STATUS_TABLE} WHERE day = {sql_string(day)}",
        print_time=False,
    )
    return None if frame.empty else str(frame.iloc[0]["state"])


def replace_status(
    dbfuncs,
    *,
    day: str,
    state: str,
    available: list[str],
    missing: list[str],
    error_message: str | None = None,
    finished: bool = False,
    started_at: datetime | None = None,
) -> None:
    """Replace one status partition with current refresh state."""
    dbfuncs.run_query(
        f"DELETE FROM {STATUS_TABLE} WHERE day = {sql_string(day)}",
        print_time=False,
    )
    completed_at = (
        "current_timestamp" if finished else "CAST(NULL AS TIMESTAMP(3) WITH TIME ZONE)"
    )
    started_at_sql = (
        "current_timestamp"
        if started_at is None
        else f"from_iso8601_timestamp({sql_string(started_at.isoformat())})"
    )
    error_sql = (
        "CAST(NULL AS VARCHAR)" if error_message is None else sql_string(error_message)
    )
    dbfuncs.run_query(
        f"""
INSERT INTO {STATUS_TABLE}
SELECT
    {sql_string(day)},
    {sql_string(state)},
    {sql_array(available)},
    {sql_array(missing)},
    {started_at_sql},
    {completed_at},
    {error_sql}
""".strip(),
        print_time=False,
    )


def source_insert(day: str, vendor: str, table: str, *, uid: bool = False) -> str:
    """Build one exact vendor-source insert."""
    return f"""
INSERT INTO {METRICS_TABLE}
SELECT
    {sql_string(day)},
    '{"uid_source" if uid else "source"}',
    {sql_string(vendor)},
    CAST(NULL AS VARCHAR),
    count(DISTINCT {"uid" if uid else "matchid"}),
    count(*),
    'exact',
    current_timestamp
FROM {table}
WHERE day = {sql_string(day)}
""".strip()


def flow_insert(
    day: str, checkpoint: str, stages: list[str], *, uid: bool = False
) -> str:
    """Build one exact cumulative stage checkpoint insert."""
    stage_list = ", ".join(sql_string(stage) for stage in stages)
    identity = (
        "uid"
        if uid
        else "IF(stable, 'S_' || CAST(matchid AS VARCHAR), CAST(matchid AS VARCHAR))"
    )
    return f"""
INSERT INTO {METRICS_TABLE}
SELECT
    {sql_string(day)},
    '{"uid_flow" if uid else "flow"}',
    {sql_string(checkpoint)},
    CAST(NULL AS VARCHAR),
    count(DISTINCT {identity}),
    count(*),
    'exact',
    current_timestamp
FROM {STAGED_TABLE}
WHERE day = {sql_string(day)}
  AND stage IN ({stage_list})
  AND matchid <> 0
  AND NOT (regexp_like(uid, '^LR_.*$') AND reason = 'IC')
  AND NOT regexp_like(uid, '^[01\\-_!*]*$')
""".strip()


def stage_reason_insert(day: str, *, uid: bool = False) -> str:
    """Build exact stage-and-reason insert."""
    identity = (
        "uid"
        if uid
        else "IF(stable, 'S_' || CAST(matchid AS VARCHAR), CAST(matchid AS VARCHAR))"
    )
    return f"""
INSERT INTO {METRICS_TABLE}
SELECT
    {sql_string(day)},
    '{"uid_stage_reason" if uid else "stage_reason"}',
    stage,
    reason,
    count(DISTINCT {identity}),
    count(*),
    'exact',
    current_timestamp
FROM {STAGED_TABLE}
WHERE day = {sql_string(day)}
  AND stage IN ('initial', 'stage1', 'stage2', 'louvain')
  AND matchid <> 0
  AND NOT (regexp_like(uid, '^LR_.*$') AND reason = 'IC')
  AND NOT regexp_like(uid, '^[01\\-_!*]*$')
GROUP BY stage, reason
""".strip()


def final_insert(day: str, *, uid: bool = False) -> str:
    """Build exact final-total and final-reason insert."""
    return f"""
INSERT INTO {METRICS_TABLE}
WITH final_metrics AS (
    SELECT
        reason,
        grouping(reason) AS total_level,
        count(DISTINCT {"uid" if uid else "matchid"}) AS matchids,
        count(*) AS rows
    FROM {FINAL_TABLE}
    WHERE day = {sql_string(day)}
    GROUP BY GROUPING SETS ((reason), ())
)
SELECT
    {sql_string(day)},
    IF(total_level = 1, '{"uid_flow" if uid else "flow"}', '{"uid_final_reason" if uid else "final_reason"}'),
    IF(total_level = 1, 'After LU / final', reason),
    CAST(NULL AS VARCHAR),
    matchids,
    rows,
    'exact',
    current_timestamp
FROM final_metrics
""".strip()


def build_day_queries(day: date | str, available: set[str]) -> list[tuple[str, str]]:
    """Return ordered exact inserts for available groups."""
    selected_day = iso_day(day)
    queries: list[tuple[str, str]] = []
    for group, (vendor, table) in SOURCE_TABLES.items():
        if group in available:
            queries.append((group, source_insert(selected_day, vendor, table)))
    if "stage_flow" in available:
        queries.extend(
            [
                (
                    "vendor_alignment",
                    flow_insert(selected_day, "Vendor alignment", ["initial"]),
                ),
                (
                    "ic_stage_1",
                    flow_insert(
                        selected_day, "After IC stage 1", ["initial", "stage1"]
                    ),
                ),
                (
                    "ic_stage_2",
                    flow_insert(
                        selected_day,
                        "After IC stage 2",
                        ["initial", "stage1", "stage2"],
                    ),
                ),
            ]
        )
    if "stage_reason" in available:
        queries.append(("stage_reason", stage_reason_insert(selected_day)))
    if "final" in available:
        queries.append(("final", final_insert(selected_day)))
    for group, (vendor, table) in SOURCE_TABLES.items():
        if f"representation_{group}" in available:
            queries.append(
                (
                    f"representation_{group}",
                    representation_sql(
                        selected_day, vendor, table, STAGED_TABLE, METRICS_TABLE
                    ),
                )
            )
    for group, table in GRAPH_TABLES.items():
        if group in available:
            queries.append(
                (group, graph_sql(selected_day, group, table, METRICS_TABLE))
            )
    if "stage_publication" in available:
        queries.append(
            (
                "stage_publication",
                publication_sql(selected_day, STAGED_TABLE, FINAL_TABLE, METRICS_TABLE),
            )
        )
    # UID aggregates run separately and sequentially; never treat rows as UIDs.
    for group, (vendor, table) in SOURCE_TABLES.items():
        if group in available:
            queries.append(
                (f"uid_{group}", source_insert(selected_day, vendor, table, uid=True))
            )
    if "stage_flow" in available:
        queries.append(
            (
                "uid_initial",
                flow_insert(selected_day, "Vendor alignment", ["initial"], uid=True),
            )
        )
    if "stage_reason" in available:
        queries.append(
            ("uid_stage_reason", stage_reason_insert(selected_day, uid=True))
        )
    if "final" in available:
        queries.append(("uid_final", final_insert(selected_day, uid=True)))
    if "uid_membership" in available:
        queries.append(
            (
                "uid_membership",
                membership_sql(
                    selected_day, SOURCE_TABLES, STAGED_TABLE, METRICS_TABLE
                ),
            )
        )
    return queries


def materialize_day(
    dbfuncs,
    day: date | str,
    available: set[str],
    *,
    force: bool = False,
) -> str:
    """Replace one day using sequential exact queries."""
    selected_day = iso_day(day)
    existing = current_state(dbfuncs, selected_day)
    if existing in COMMITTED_STATES and not force:
        return "skipped"

    available_ordered = [group for group in EXPECTED_GROUPS if group in available]
    missing = [group for group in EXPECTED_GROUPS if group not in available]
    started_at = datetime.now(timezone.utc)
    replace_status(
        dbfuncs,
        day=selected_day,
        state="refreshing",
        available=available_ordered,
        missing=missing,
        started_at=started_at,
    )
    try:
        dbfuncs.run_query(
            f"DELETE FROM {METRICS_TABLE} WHERE day = {sql_string(selected_day)}",
            print_time=False,
        )
        for label, query in build_day_queries(selected_day, available):
            print(f"[{selected_day}] {label}")
            dbfuncs.run_query(query, print_time=False)
    except Exception as exc:
        replace_status(
            dbfuncs,
            day=selected_day,
            state="failed",
            available=available_ordered,
            missing=missing,
            error_message=f"{type(exc).__name__}: {exc}"[:4000],
            finished=True,
            started_at=started_at,
        )
        raise

    final_state = "complete" if not missing else "partial"
    replace_status(
        dbfuncs,
        day=selected_day,
        state=final_state,
        available=available_ordered,
        missing=missing,
        finished=True,
        started_at=started_at,
    )
    return final_state


def backfill(dbfuncs, days: int, pause_seconds: float = 5.0) -> None:
    """Backfill latest final-output days, oldest first."""
    availability = load_availability(dbfuncs)
    final_days = sorted(
        day for day, groups in availability.items() if "final" in groups
    )[-days:]
    if not final_days:
        raise RuntimeError("No final-output partitions found.")
    for index, selected_day in enumerate(final_days):
        state = materialize_day(dbfuncs, selected_day, availability[selected_day])
        print(f"[{selected_day}] {state}")
        if index < len(final_days) - 1 and state != "skipped":
            time.sleep(pause_seconds)


def parse_args() -> argparse.Namespace:
    """Parse materializer command line."""
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    backfill_parser = subparsers.add_parser("backfill")
    backfill_parser.add_argument("--days", type=int, default=30)
    backfill_parser.add_argument("--pause-seconds", type=float, default=5.0)

    refresh_parser = subparsers.add_parser("refresh")
    refresh_parser.add_argument("--day", required=True)
    refresh_parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def main() -> int:
    """Run requested materialization command."""
    args = parse_args()
    dbfuncs = bootstrap_dbfuncs()
    ensure_tables(dbfuncs)
    if args.command == "backfill":
        if args.days < 1:
            raise ValueError("--days must be positive")
        backfill(dbfuncs, args.days, args.pause_seconds)
        return 0

    selected_day = iso_day(args.day)
    availability = load_availability(dbfuncs)
    state = materialize_day(
        dbfuncs,
        selected_day,
        availability.get(selected_day, set()),
        force=args.force,
    )
    print(f"[{selected_day}] {state}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

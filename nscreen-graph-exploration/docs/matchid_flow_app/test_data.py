from datetime import date

import pandas as pd
import pytest
from data import (
    METRICS_TABLE,
    STATUS_TABLE,
    build_available_days_query,
    build_materialized_query,
    load_materialized_snapshot,
    normalize_metrics,
)


class QueryClient:
    def __init__(self, frame: pd.DataFrame):
        self.frame = frame
        self.queries: list[str] = []

    def query2df(self, query: str, print_time: bool = False) -> pd.DataFrame:
        self.queries.append(query)
        return self.frame.copy()


def test_materialized_queries_are_small_and_partitioned():
    days_query = build_available_days_query()
    snapshot_query = build_materialized_query(date(2026, 9, 17))

    assert STATUS_TABLE in days_query
    assert METRICS_TABLE in snapshot_query
    assert STATUS_TABLE in snapshot_query
    assert "WHERE s.day = '2026-09-17'" in snapshot_query
    assert "crossscreen.liveramp_source" not in snapshot_query
    assert "count(DISTINCT" not in snapshot_query


def test_query_rejects_non_iso_day():
    with pytest.raises(ValueError):
        build_materialized_query("2026-09-17' OR TRUE --")


def test_partial_snapshot_preserves_missing_groups():
    frame = pd.DataFrame(
        [
            {
                "day": "2026-09-17",
                "state": "partial",
                "available_groups": ["final"],
                "missing_groups": ["source_liveramp", "stage_flow"],
                "started_at": None,
                "completed_at": None,
                "error_message": None,
                "metric_type": "final_reason",
                "dimension_1": "LR",
                "dimension_2": None,
                "matchids": 42,
                "rows": 100,
                "count_method": "exact",
                "computed_at": None,
            }
        ]
    )
    snapshot = load_materialized_snapshot("2026-09-17", QueryClient(frame))

    assert snapshot["status"]["state"] == "partial"
    assert snapshot["status"]["missing_groups"] == [
        "source_liveramp",
        "stage_flow",
    ]
    assert snapshot["metrics"]["flow"].empty
    assert snapshot["metrics"]["final_reason"].iloc[0]["matchids"] == 42


def test_missing_snapshot_returns_empty_marker():
    snapshot = load_materialized_snapshot("2026-09-17", QueryClient(pd.DataFrame()))

    assert snapshot == {"status": None, "metrics": None}


def test_normalize_rejects_incomplete_query_shape():
    with pytest.raises(ValueError, match="lacks columns"):
        normalize_metrics(pd.DataFrame({"metric_type": ["flow"]}))

import materialize
import pandas as pd
import pytest


class FakeDbfuncs:
    def __init__(self, state: str | None = None, fail_on: str | None = None):
        self.state = state
        self.fail_on = fail_on
        self.queries: list[str] = []

    def query2df(self, query: str, print_time: bool = False) -> pd.DataFrame:
        self.queries.append(query)
        if "SELECT state" in query and self.state:
            return pd.DataFrame({"state": [self.state]})
        return pd.DataFrame(columns=["state"])

    def run_query(self, query: str, print_time: bool = False):
        self.queries.append(query)
        if self.fail_on and self.fail_on in query:
            raise RuntimeError("planned failure")


COMPLETE_GROUPS = set(materialize.EXPECTED_GROUPS)


def test_availability_query_dereferences_partition_rows():
    query = materialize.build_availability_query()

    assert "partition.day" in query
    assert "partition.stage" in query
    assert "SELECT 'source_liveramp' AS group_name, day" not in query


def test_table_creation_is_idempotent_and_partitioned():
    client = FakeDbfuncs()

    materialize.ensure_tables(client)
    materialize.ensure_tables(client)

    assert len(client.queries) == 4
    assert all("CREATE TABLE IF NOT EXISTS" in query for query in client.queries)
    assert all("partitioning = ARRAY['day']" in query for query in client.queries)


def test_complete_day_builds_exact_queries_in_order():
    queries = materialize.build_day_queries("2026-09-17", COMPLETE_GROUPS)

    assert [label for label, _ in queries] == [
        "source_liveramp",
        "source_throtle",
        "source_experian",
        "vendor_alignment",
        "ic_stage_1",
        "ic_stage_2",
        "stage_reason",
        "final",
        "representation_source_liveramp",
        "representation_source_throtle",
        "representation_source_experian",
        "graph_clean",
        "graph_remainder",
        "stage_publication",
        "uid_source_liveramp",
        "uid_source_throtle",
        "uid_source_experian",
        "uid_initial",
        "uid_stage_reason",
        "uid_final",
        "uid_membership",
    ]
    assert all("count(DISTINCT" in query for _, query in queries[:8])
    assert all("approx_distinct" not in query for _, query in queries)
    assert all("day = '2026-09-17'" in query for _, query in queries)


def test_source_queries_never_join_raw_tables():
    queries = dict(materialize.build_day_queries("2026-09-17", COMPLETE_GROUPS))
    source_tables = [table for _, table in materialize.SOURCE_TABLES.values()]

    for group in materialize.SOURCE_TABLES:
        query = queries[group]
        assert sum(table in query for table in source_tables) == 1
        assert " JOIN " not in query.upper()


def test_uid_aggregations_are_exact_sequential_partition_scans():
    queries = materialize.build_day_queries("2026-09-17", COMPLETE_GROUPS)
    uid_queries = [
        sql
        for label, sql in queries
        if label.startswith("uid_") and label != "uid_membership"
    ]
    assert len(uid_queries) == 6
    for sql in uid_queries:
        assert "count(DISTINCT uid)" in sql
        assert "day = '2026-09-17'" in sql
        assert " JOIN " not in sql.upper()
        assert "approx_distinct" not in sql


def test_completed_day_skips_without_force():
    client = FakeDbfuncs(state="complete")

    state = materialize.materialize_day(
        client, "2026-09-17", COMPLETE_GROUPS, force=False
    )

    assert state == "skipped"
    assert not any(query.startswith("DELETE") for query in client.queries)


def test_uid_membership_deduplicates_uids_without_raw_joins():
    sql = dict(materialize.build_day_queries("2026-09-17", COMPLETE_GROUPS))[
        "uid_membership"
    ]
    assert sql.count("day = '2026-09-17'") == 4
    assert "GROUP BY uid" in sql
    assert "bitwise_or_agg(vendor_mask)" in sql
    assert "multiple_reasons" in sql
    assert "unrepresented" in sql
    assert " JOIN " not in sql.upper()


def test_partial_day_records_missing_groups():
    client = FakeDbfuncs()

    state = materialize.materialize_day(client, "2026-09-17", {"final"})

    assert state == "partial"
    inserts = [query for query in client.queries if "INSERT INTO" in query]
    assert any("'partial'" in query for query in inserts)
    assert any("'source_liveramp'" in query for query in inserts)
    raw_inserts = [
        query
        for query in inserts
        if f"INSERT INTO {materialize.METRICS_TABLE}\n" in query
    ]
    assert len(raw_inserts) == 2
    assert materialize.FINAL_TABLE in raw_inserts[0]


def test_failure_records_failed_status():
    client = FakeDbfuncs(fail_on="FROM iceberg.crossscreen.liveramp_source")

    with pytest.raises(RuntimeError, match="planned failure"):
        materialize.materialize_day(client, "2026-09-17", COMPLETE_GROUPS)

    assert any("'failed'" in query for query in client.queries)
    assert any("planned failure" in query for query in client.queries)


def test_force_replaces_committed_day():
    client = FakeDbfuncs(state="partial")

    state = materialize.materialize_day(
        client, "2026-09-17", COMPLETE_GROUPS, force=True
    )

    assert state == "complete"
    assert any(
        query.startswith(f"DELETE FROM {materialize.METRICS_TABLE}")
        for query in client.queries
    )


def test_backfill_runs_oldest_first_and_pauses(monkeypatch):
    processed: list[str] = []
    pauses: list[float] = []
    availability = {
        "2026-09-17": {"final"},
        "2026-09-18": {"final"},
        "2026-09-19": {"final"},
    }
    monkeypatch.setattr(materialize, "load_availability", lambda client: availability)
    monkeypatch.setattr(
        materialize,
        "materialize_day",
        lambda client, day, groups: processed.append(day) or "complete",
    )
    monkeypatch.setattr(materialize.time, "sleep", pauses.append)

    materialize.backfill(FakeDbfuncs(), days=2, pause_seconds=5.0)

    assert processed == ["2026-09-18", "2026-09-19"]
    assert pauses == [5.0]

"""SQL safety checks and optional tiny Trino VALUES-fixture integration tests."""

import os
import sys
from pathlib import Path

import pandas as pd
import pytest
from data import normalize_metrics
from flow_metrics import graph_sql, publication_sql, representation_sql

DAY = "2026-09-19"


def test_graph_counts_preserve_units_and_nullable_matchids():
    raw = pd.DataFrame(
        [
            ["graph_size", "graph_clean", "uids", None, 3],
            ["graph_size", "graph_clean", "relationships", None, 2],
        ],
        columns=["metric_type", "dimension_1", "dimension_2", "matchids", "rows"],
    )
    metrics = normalize_metrics(raw)
    assert metrics["graph_size"].set_index("unit")["count"].to_dict() == {
        "uids": 3,
        "relationships": 2,
    }
    assert metrics["sources"].empty


def test_representation_does_not_use_reason_subtraction_or_raw_join():
    query = representation_sql(DAY, "LiveRamp", "source", "staged", "metrics")
    assert "source_id" in query and "initial_id" in query
    assert "reason" not in query
    assert "JOIN staged" not in query
    assert query.count(f"day = '{DAY}'") == 2


@pytest.fixture
def trino():
    if os.environ.get("MATCHID_TRINO_TESTS") != "1":
        pytest.skip("Set MATCHID_TRINO_TESTS=1 for tiny VALUES-only Trino checks")
    sys.path.insert(0, str(Path.home() / ".codex/skills/pulsepoint-trino/scripts"))
    from ppconfig import bootstrap

    client, _ = bootstrap()
    return client


def run_select(client, sql):
    # Drop the INSERT header: integration tests never write warehouse data.
    return client.query2df(sql.split("\n", 1)[1], print_time=False)


def test_representation_fixture(trino):
    source = f"""(VALUES
        ('{DAY}', 'u1', 1), ('{DAY}', 'u1', 1), ('{DAY}', 'u2', 2),
        ('{DAY}', 'u3', 3), ('{DAY}', 'u4', 4), ('{DAY}', 'u5', 4),
        ('{DAY}', CAST(NULL AS VARCHAR), 5)
    ) AS source(day, uid, matchid)"""
    staged = f"""(VALUES
        ('{DAY}', 'u1', 1, 'initial'), ('{DAY}', 'u2', 99, 'initial'),
        ('{DAY}', 'u4', 4, 'initial'), ('{DAY}', 'u5', 99, 'initial')
    ) AS staged(day, uid, matchid, stage)"""
    result = run_select(trino, representation_sql(DAY, "LR", source, staged, "unused"))
    counts = {row[3]: row[4] for row in result.itertuples(index=False, name=None)}
    assert counts == {"same_id": 2, "reassigned_only": 1, "unrepresented": 2}


def test_graph_fixture(trino):
    graph = f"""(VALUES ('{DAY}', 'a', 'b'), ('{DAY}', 'b', 'c'))
        AS graph(day, uid1, uid2)"""
    result = run_select(trino, graph_sql(DAY, "graph_clean", graph, "unused"))
    assert {r[3]: r[5] for r in result.itertuples(index=False, name=None)} == {
        "uids": 3,
        "relationships": 2,
    }
    assert result.iloc[:, 4].isna().all()


def test_publication_fixture(trino):
    staged = f"""(VALUES
        ('{DAY}', 'a', 1, true, 'initial'),
        ('{DAY}', 'b', 1, true, 'stage1'),
        ('{DAY}', 'c', 2, false, 'stage2'),
        ('{DAY}', 'd', 0, false, 'louvain'),
        ('{DAY}', 'e', 1, false, 'initial')
    ) AS staged(day, uid, matchid, stable, stage)"""
    final = f"""(VALUES ('{DAY}', 'a', 'S_1'), ('{DAY}', 'b', 'S_1'),
        ('{DAY}', 'e', '1')) AS final(day, uid, matchid)"""
    result = run_select(trino, publication_sql(DAY, staged, final, "unused"))
    assert {
        (r[2], r[3]): (r[4], r[5]) for r in result.itertuples(index=False, name=None)
    } == {
        ("initial", "published"): (2, 2),
        ("stage1", "published"): (1, 1),
        ("stage2", "not_published"): (1, 1),
        ("louvain", "not_published"): (1, 1),
    }

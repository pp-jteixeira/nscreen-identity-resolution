import base64
import importlib.util
import json
import os
import subprocess
from collections import Counter
from pathlib import Path

import pytest
import sqlglot

from replay import java, runner
from replay.runner import typed_day_literal
from replay.sql import (
    FILES,
    INPUTS,
    REMAINDER,
    STAGED,
    canonical_result,
    compile_stage,
    literal,
    multiset_diff,
    production_ref,
    qualified_table,
    versioned_ref,
)
from replay.warehouse import Warehouse, check_write

FORGE = Path(os.environ.get("NSCREEN_FORGE", str(Path.home() / "forge")))
SQL = FORGE / "nscreen-graph/src/nscreen_graph/spark/sparksql"
REFS = {t: production_ref(t, 123) for t in INPUTS}
REFS.update(
    {
        STAGED: "iceberg.jteixeira_ipa.nscreen2_test_staged",
        REMAINDER: "iceberg.jteixeira_ipa.nscreen2_test_remainder",
    }
)


@pytest.mark.parametrize("stage", FILES)
def test_all_stages_compile(stage):
    mapping, query = compile_stage(
        SQL,
        stage,
        "2026-09-18",
        REFS,
        mapping_table="iceberg.jteixeira_ipa.nscreen2_mapping",
        cluster_table="iceberg.jteixeira_ipa.nscreen2_clusters",
    )
    sqlglot.parse_one(query, read="trino")
    assert "hudf_" not in query
    assert "NAMED_STRUCT" not in query
    assert "INLINE(" not in query
    if stage in ("lrth", "initial"):
        assert "bool_or" in mapping.lower()
        assert "FOR VERSION AS OF 123" in mapping
    if stage == "lrth":
        assert query.startswith(
            "SELECT uid, matchid, householdid, stable, reason, '2026-09-18' AS day, 'lrth' AS stage"
        )
    if stage in ("stage1", "stage2"):
        assert "SUM(CAST(weight AS DOUBLE))" in query


def test_modified_expansion_is_not_silently_discarded(tmp_path):
    name = FILES["stage1"]
    source = (
        (SQL / name)
        .read_text()
        .replace(
            "where day = '{{ var('day') }}'",
            "where day = '{{ var('day') }}' and weight > 1",
            1,
        )
    )
    (tmp_path / name).write_text(source)
    with pytest.raises(ValueError, match="Source ns_dbl changed"):
        compile_stage(tmp_path, "stage1", "2026-09-18", REFS)


def test_modified_clustering_is_not_silently_discarded(tmp_path):
    name = FILES["louvain"]
    source = (
        (SQL / name).read_text().replace("group by geo", "group by geo, samedevice")
    )
    (tmp_path / name).write_text(source)
    with pytest.raises(ValueError, match="Source raw changed"):
        compile_stage(
            tmp_path, "louvain", "2026-09-18", REFS, cluster_table="fixture_clusters"
        )


@pytest.mark.parametrize(
    "statement",
    [
        "DROP TABLE iceberg.jteixeira_ipa.nscreen2_x",
        "CREATE TABLE iceberg.crossscreen.nscreen2_x AS SELECT 1",
        "INSERT INTO iceberg.jteixeira_ipa.nscreen_toy SELECT 1",
        "DELETE FROM iceberg.jteixeira_ipa.nscreen2_x",
        "CREATE OR REPLACE VIEW iceberg.jteixeira_ipa.nscreen2_x AS SELECT 1",
    ],
)
def test_write_guard(statement):
    with pytest.raises(ValueError):
        check_write(statement)


def test_writes_scoped_and_literals():
    check_write(
        "/* replay */ CREATE TABLE iceberg.jteixeira_ipa.nscreen2_x AS SELECT 1"
    )
    assert literal("o'neil") == "'o''neil'"
    assert literal(None) == "NULL"
    with pytest.raises(ValueError):
        production_ref("source; DROP TABLE x", 1)


def test_stream_batches_accepts_read_tag(monkeypatch):
    class Cursor:
        query_id = "query"
        _query = None

        def execute(self, sql):
            assert sql.startswith("/* tagged */")

        def fetchmany(self, count):
            return []

        def close(self):
            pass

    class Connection:
        def cursor(self):
            return Cursor()

        def close(self):
            pass

    monkeypatch.setattr("replay.warehouse.connect", Connection)
    assert list(Warehouse().stream_batches("/* tagged */\nSELECT 1")) == []


def test_qualified_table_and_versioned_ref():
    assert qualified_table("iceberg.jteixeira_ipa.sample") == (
        "iceberg.jteixeira_ipa.sample"
    )
    assert versioned_ref("iceberg.jteixeira_ipa.sample", 42) == (
        "iceberg.jteixeira_ipa.sample FOR VERSION AS OF 42"
    )
    for unsafe in ("sample", "iceberg.schema.table.extra", "iceberg.schema.bad-name"):
        with pytest.raises(ValueError):
            qualified_table(unsafe)


def test_day_literal_follows_warehouse_type():
    assert typed_day_literal([("day", "date")], "2026-09-16") == (
        "DATE '2026-09-16'"
    )
    assert typed_day_literal([("day", "varchar")], "2026-09-16") == (
        "'2026-09-16'"
    )
    with pytest.raises(ValueError, match="Unsupported day column type"):
        typed_day_literal([("day", "timestamp(3)")], "2026-09-16")


def test_date_input_ref_normalizes_day_for_forge_sql(tmp_path, monkeypatch):
    monkeypatch.setattr(runner, "ROOT", tmp_path)
    replay = runner.Replay(
        "date_input",
        FORGE,
        "2026-09-16",
        warehouse=object(),
        input_tables={
            "liveramp_source": "iceberg.jteixeira_ipa.sample_liveramp"
        },
    )
    replay.state["snapshots"]["liveramp_source"] = {
        "source_table": "iceberg.jteixeira_ipa.sample_liveramp",
        "snapshot_id": 42,
        "schema": [
            ("day", "date"),
            ("vendor", "varchar"),
            ("uid", "varchar"),
            ("matchid", "bigint"),
            ("householdid", "bigint"),
            ("stable", "boolean"),
        ],
    }
    reference = replay.ref("liveramp_source")
    assert "CAST(day AS VARCHAR) AS day" in reference
    assert "FOR VERSION AS OF 42" in reference
    mapping, query = compile_stage(
        SQL,
        "lrth",
        "2026-09-16",
        {**REFS, "liveramp_source": reference},
        mapping_table="iceberg.jteixeira_ipa.nscreen2_mapping",
    )
    for statement in (mapping, query):
        assert "CAST(day AS VARCHAR) AS day" in statement
        sqlglot.parse_one(statement, read="trino")
    replay.lock.close()


def test_input_overrides_are_persisted_and_immutable(tmp_path, monkeypatch):
    monkeypatch.setattr(runner, "ROOT", tmp_path)
    sample = "iceberg.jteixeira_ipa.nscreen_membership_sample_liveramp"
    replay = runner.Replay(
        "sample_inputs",
        FORGE,
        "2026-09-16",
        warehouse=object(),
        input_tables={"liveramp_source": sample},
        profile="sample-v1",
    )
    assert replay.state["input_tables"]["liveramp_source"] == sample
    assert replay.state["profile"] == "sample-v1"
    replay.lock.close()
    resumed = runner.Replay("sample_inputs", FORGE, warehouse=object())
    assert resumed.input_tables["liveramp_source"] == sample
    resumed.lock.close()
    with pytest.raises(ValueError, match="another input configuration"):
        runner.Replay(
            "sample_inputs",
            FORGE,
            warehouse=object(),
            input_tables={"liveramp_source": "iceberg.other.sample"},
        )


def test_resume_does_not_republish_completed_stage(tmp_path, monkeypatch):
    from replay import runner

    class FakeWarehouse:
        last_query_id = "fixture-query"

        def __init__(self):
            self.writes = []

        def rows(self, sql):
            return []

        def execute(self, sql):
            self.writes.append(sql)

    monkeypatch.setattr(runner, "ROOT", tmp_path)
    db = FakeWarehouse()
    replay = runner.Replay("resume_test", FORGE, "2026-09-18", warehouse=db)
    first = replay.artifact("fixture", "SELECT 1 AS value")
    assert replay.artifact("fixture", "SELECT 1 AS value") == first
    assert len(db.writes) == 1
    with pytest.raises(RuntimeError, match="Compiled query changed"):
        replay.artifact("fixture", "SELECT 2 AS value")


def test_upload_resume_reconciles_lost_acknowledgement(tmp_path, monkeypatch):
    from replay import runner

    class FakeWarehouse:
        def rows(self, sql):
            return [] if "system.runtime.queries" in sql else [[1]]

        def execute(self, sql):
            raise AssertionError("Already committed batch must not be written twice")

    monkeypatch.setattr(runner, "ROOT", tmp_path)
    replay = runner.Replay(
        "upload_test", FORGE, "2026-09-18", warehouse=FakeWarehouse()
    )
    replay.state["clusters"]["key"] = {
        "geo": "G",
        "packed_upload": {
            "config": {"batch_rows": 5000, "shards": 1},
            "batches": {"0": "pending"},
        },
    }
    output = tmp_path / "output.tsv"
    output.write_text("dWlk\t1\t2\t3\t4\n")
    replay.upload_geo("iceberg.jteixeira_ipa.nscreen2_upload", "key", output, 5000)
    assert (
        replay.state["clusters"]["key"]["packed_upload"]["batches"]["0"]
        == "complete"
    )


def test_upload_reconciles_commit_error_without_restart(tmp_path, monkeypatch):
    from replay import runner

    class FakeWarehouse:
        def rows(self, sql):
            return [] if "system.runtime.queries" in sql else [[1]]

        def execute(self, sql):
            raise RuntimeError("HIVE_WRITER_CLOSE_ERROR")

    monkeypatch.setattr(runner, "ROOT", tmp_path)
    replay = runner.Replay(
        "upload_commit_error", FORGE, "2026-09-18", warehouse=FakeWarehouse()
    )
    replay.state["clusters"]["key"] = {"geo": "G"}
    output = tmp_path / "output.tsv"
    output.write_text("dWlk\t1\t2\t3\t4\n")
    replay.upload_geo(
        "iceberg.jteixeira_ipa.nscreen2_upload", "key", output, 5000
    )
    assert (
        replay.state["clusters"]["key"]["packed_upload"]["batches"]["0"]
        == "complete"
    )


def test_packed_upload_compacts_numeric_columns_and_preserves_nulls():
    lines = [
        [base64.b64encode(b"uid-1").decode(), "1", "2", "null", "4"],
        [base64.b64encode(b"uid-2").decode(), "-5", "-6", "-7", "null"],
    ]
    sql = runner.Replay.packed_upload_sql(
        "iceberg.jteixeira_ipa.nscreen2_upload",
        "/* packed */",
        "G",
        9,
        lines,
    )
    assert "from_base64" in sql
    assert "from_big_endian_64" in sql
    assert "split(uids,chr(31))" in sql
    assert "uid-1\x1fuid-2" in sql
    assert "'24'" in sql


def test_local_parquet_preserves_cluster_rows(tmp_path, monkeypatch):
    import polars as pl

    monkeypatch.setattr(runner, "ROOT", tmp_path)
    replay = runner.Replay(
        "local_parquet", FORGE, "2026-09-18", warehouse=object()
    )
    replay.state["clusters"]["key"] = {"geo": "G", "edges": 2}
    source = replay.directory / "cluster.output.tsv"
    source.write_text(
        "\t".join(
            [base64.b64encode(b"uid-1").decode(), "1", "2", "null", "4"]
        )
        + "\n"
        + "\t".join(
            [base64.b64encode(b"uid-2").decode(), "-5", "null", "-7", "null"]
        )
        + "\n"
    )
    replay.persist_geo_parquet("key", source, chunk_rows=1)
    metadata = replay.state["clusters"]["key"]["local_parquet"]
    directory = replay.directory / metadata["path"]
    frame = pl.read_parquet(sorted(directory.glob("part-*.parquet")))
    assert metadata["rows"] == 2
    assert metadata["parts"] == 2
    assert frame.to_dicts() == [
        {
            "geo": "G",
            "uid": "uid-1",
            "uidhash": 1,
            "deviceid": 2,
            "matchid": None,
            "householdid": 4,
        },
        {
            "geo": "G",
            "uid": "uid-2",
            "uidhash": -5,
            "deviceid": None,
            "matchid": -7,
            "householdid": None,
        },
    ]
    assert replay.local_parquet_complete(replay.state["clusters"]["key"])
    replay.write_local_cluster_manifest()
    summary = json.loads(
        (replay.directory / "clustering/parquet/_manifest.json").read_text()
    )
    assert summary["rows"] == 2
    assert summary["geographies"] == 1
    replay.state["cluster_output"] = "parquet"
    replay.state["clustering_capacity"] = {"geos": 3}
    assert runner.local_cluster_progress(replay.state) == {
        "completed_geographies": 1,
        "total_geographies": 3,
        "rows": 2,
        "bytes": metadata["bytes"],
    }
    replay.write_report()
    report = (replay.directory / "report.md").read_text()
    assert "through local Java mappings" in report
    assert "Local Parquet progress: 1/3 geographies, 2 rows" in report
    assert "Production parity remains unverified" in report
    replay.lock.close()


def test_local_parquet_run_stops_before_louvain_sql(tmp_path, monkeypatch):
    monkeypatch.setattr(runner, "ROOT", tmp_path)
    replay = runner.Replay(
        "local_stop", FORGE, "2026-09-18", warehouse=object()
    )
    for stage in ("lrth", "initial", "connected_ns", "stage1", "stage2", "remainder"):
        replay.state["artifacts"][stage] = {"status": "complete"}
    calls = []
    replay.pin = lambda: None
    replay.refs = lambda stage: {}
    replay.cluster = lambda *args, **kwargs: calls.append(kwargs["output"])
    replay.run(
        until=runner.LOCAL_CLUSTER_STAGE,
        cluster_output="parquet",
        remainder_output="trino",
    )
    assert calls == ["parquet"]
    assert replay.state["status"] == "clustered_local"
    assert "louvain" not in replay.state["artifacts"]
    replay.lock.close()


def test_local_result_run_stays_outside_trino(tmp_path, monkeypatch):
    monkeypatch.setattr(runner, "ROOT", tmp_path)
    replay = runner.Replay(
        "local_result_stop", FORGE, "2026-09-18", warehouse=object()
    )
    for stage in ("lrth", "initial", "connected_ns", "stage1", "stage2", "remainder"):
        replay.state["artifacts"][stage] = {"status": "complete"}
    calls = []
    replay.pin = lambda: None
    replay.refs = lambda stage: {}
    replay.cluster = lambda *args, **kwargs: calls.append(kwargs["output"])
    replay.local_downstream = lambda memory, threads: calls.append((memory, threads))
    replay.run(
        until=runner.LOCAL_RESULT_STAGE,
        cluster_output="parquet",
        remainder_output="trino",
    )
    assert calls == ["parquet", ("8GB", 2)]
    assert replay.state["local_sql_threads"] == 2
    assert replay.state["status"] == "computed_local"
    assert "louvain" not in replay.state["artifacts"]
    replay.lock.close()


def test_local_clustering_counts_geographies_without_trino_write(
    tmp_path, monkeypatch
):
    class FakeWarehouse:
        def __init__(self):
            self.reads = []

        def rows(self, sql):
            self.reads.append(sql)
            return []

    monkeypatch.setattr(runner, "ROOT", tmp_path)
    monkeypatch.setattr(runner.java, "command", lambda *args: ["java"])
    database = FakeWarehouse()
    replay = runner.Replay(
        "local_geo_counts", FORGE, "2026-09-18", warehouse=database
    )
    replay.state["artifacts"]["remainder"] = {
        "status": "complete",
        "table": "remainder_table",
    }
    replay.cluster("1GB", 1, 10, 1, 1, output="parquet")
    assert "geo_counts" not in replay.state["artifacts"]
    assert database.reads == [
        (
            "SELECT geo,count(*) AS edges FROM remainder_table "
            "GROUP BY geo ORDER BY edges ASC,geo"
        )
    ]
    replay.lock.close()


def test_local_remainder_streams_into_partitioned_parquet(tmp_path, monkeypatch):
    import polars as pl

    class FakeWarehouse:
        last_query_id = "query-local-remainder"

        def stream_batches(self, sql, batch_rows):
            assert "SELECT remainder" in sql
            assert batch_rows == 2
            yield [
                ("u1", "u2", 1.5, True, False, "G1", "2026-09-18"),
                ("u2", "u3", 2.5, False, True, "G2", "2026-09-18"),
            ]
            yield [("u3", "u4", 3.5, True, True, "G1", "2026-09-18")]

    monkeypatch.setattr(runner, "ROOT", tmp_path)
    replay = runner.Replay(
        "local_remainder", FORGE, "2026-09-18", warehouse=FakeWarehouse()
    )
    state = replay.persist_local_remainder(
        "SELECT remainder", "256MB", batch_rows=2
    )
    assert state["rows"] == 3
    assert state["status"] == "complete"
    assert replay.state["local_remainder_export"]["query_id"] == (
        "query-local-remainder"
    )
    geographies = {item["geo"]: item for item in state["geographies"]}
    assert {name: item["edges"] for name, item in geographies.items()} == {
        "G1": 2,
        "G2": 1,
    }
    rows = list(replay.iter_local_remainder_edges(geographies["G1"]))
    assert rows == [
        ("u1", "u2", 1.5, True, False),
        ("u3", "u4", 3.5, True, True),
    ]
    directory = replay.directory / state["path"]
    assert pl.scan_parquet(directory / "**/*.parquet").select(
        pl.len()
    ).collect().item() == 3
    assert not (replay.directory / "local/remainder.partial.duckdb").exists()
    replay.lock.close()


def test_local_remainder_bypasses_trino_artifact(tmp_path, monkeypatch):
    monkeypatch.setattr(runner, "ROOT", tmp_path)
    replay = runner.Replay(
        "local_remainder_run", FORGE, "2026-09-18", warehouse=object()
    )
    for stage in ("lrth", "initial", "connected_ns", "stage1", "stage2"):
        replay.state["artifacts"][stage] = {
            "status": "complete",
            "table": stage + "_table",
        }
    calls = []
    replay.pin = lambda: None
    replay.refs = lambda stage: REFS
    replay.persist_local_remainder = lambda query, memory: calls.append(
        ("remainder", query, memory)
    )
    replay.cluster = lambda *args, **kwargs: calls.append(
        ("cluster", kwargs["output"])
    )
    replay.run(
        until=runner.LOCAL_CLUSTER_STAGE,
        cluster_output="parquet",
        remainder_output="parquet",
    )
    assert calls[0][0] == "remainder"
    assert calls[0][2] == "8GB"
    assert calls[1] == ("cluster", "parquet")
    assert replay.state["artifacts"].get("remainder", {}).get("status") != (
        "complete"
    )
    replay.lock.close()


def test_local_downstream_preserves_hash_join_and_final_filters(
    tmp_path, monkeypatch
):
    import polars as pl

    class FakeWarehouse:
        def __init__(self):
            self.rows = {
                "initial_table": [("stable", 3, 4, True, "LR")],
                "stage1_table": [("LR_filtered", 5, 0, False, "IC")],
                "stage2_table": [("01-_!*", 6, 0, False, "LU")],
            }

        def stream(self, sql):
            for table, rows in self.rows.items():
                if table in sql:
                    yield from rows
                    return
            raise AssertionError(sql)

    monkeypatch.setattr(runner, "ROOT", tmp_path)
    replay = runner.Replay(
        "local_downstream", FORGE, "2026-09-18", warehouse=FakeWarehouse()
    )
    replay.state["artifacts"].update(
        {
            "initial": {"status": "complete", "table": "initial_table"},
            "stage1": {"status": "complete", "table": "stage1_table"},
            "stage2": {"status": "complete", "table": "stage2_table"},
        }
    )
    cluster_rows = {
        "a": [("u1", 7, 1, 11, 0), ("u2", 7, 1, 11, 0)],
        "b": [("u1", 7, 2, 22, 0)],
    }
    for key, rows in cluster_rows.items():
        replay.state["clusters"][key] = {"geo": key.upper(), "edges": 1}
        source = replay.directory / f"{key}.tsv"
        source.write_text(
            "".join(
                "\t".join(
                    [
                        base64.b64encode(uid.encode()).decode(),
                        str(uidhash),
                        str(device),
                        str(match),
                        str(household),
                    ]
                )
                + "\n"
                for uid, uidhash, device, match, household in rows
            )
        )
        replay.persist_geo_parquet(key, source, chunk_rows=1)
    replay.write_local_cluster_manifest()
    replay.local_downstream("256MB", 2)
    louvain = pl.read_parquet(replay.directory / "local/louvain/*.parquet")
    assert Counter(zip(louvain["uid"], louvain["matchid"])) == Counter(
        [("u1", 11), ("u1", 22), ("u2", 11), ("u2", 22)]
    )
    result = pl.read_parquet(replay.directory / "local/result/*.parquet")
    assert Counter(
        zip(result["uid"], result["matchid"], result["householdid"])
    ) == Counter(
        [
            ("stable", "S_3", "S_4"),
            ("u1", "11", ""),
            ("u1", "22", ""),
            ("u2", "11", ""),
            ("u2", "22", ""),
        ]
    )
    assert replay.state["local_output"]["status"] == "complete"
    local_manifest = json.loads(
        (replay.directory / "local/_manifest.json").read_text()
    )
    assert local_manifest["threads"] == 2
    replay.lock.close()


def test_resume_local_downstream_uses_only_completed_local_inputs(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(runner, "ROOT", tmp_path)
    replay = runner.Replay(
        "local_resume", FORGE, "2026-09-18", warehouse=object()
    )
    replay.state["cluster_output"] = "parquet"
    replay.state["clustering_capacity"] = {"geos": 1}
    replay.state["clusters"] = {
        "geo": {"local_parquet": {"status": "complete", "rows": 1, "bytes": 1}}
    }
    replay.state["local_stage_exports"] = {}
    for stage in ("initial", "stage1", "stage2"):
        directory = replay.directory / "local" / "staged" / stage
        directory.mkdir(parents=True)
        metadata = replay.publish_metadata(directory, 0, [])
        replay.state["local_stage_exports"][stage] = replay.dataset_state(
            directory, metadata
        )
    calls = []
    replay.local_downstream = lambda memory, threads: calls.append((memory, threads))
    replay.state["last_error"] = "old failure"
    replay.resume_local_downstream(None, 2)
    assert calls == [("8GB", 2)]
    assert replay.state["status"] == "computed_local"
    assert "last_error" not in replay.state
    replay.lock.close()


def test_packed_upload_routes_concurrent_batches_across_shards(
    tmp_path, monkeypatch
):
    from replay import runner

    class FakeWarehouse:
        def __init__(self):
            self.writes = []

        def rows(self, sql):
            return []

        def execute(self, sql):
            self.writes.append(sql)

    monkeypatch.setattr(runner, "ROOT", tmp_path)
    db = FakeWarehouse()
    replay = runner.Replay(
        "packed_shards", FORGE, "2026-09-18", warehouse=db
    )
    replay.state["clusters"]["key"] = {"geo": "G"}
    output = tmp_path / "output.tsv"
    rows = [
        [base64.b64encode(f"uid-{i}".encode()).decode(), str(i), "2", "3", "4"]
        for i in range(3)
    ]
    output.write_text("".join("\t".join(row) + "\n" for row in rows))
    replay.upload_geo(
        [
            "iceberg.jteixeira_ipa.nscreen2_upload_0",
            "iceberg.jteixeira_ipa.nscreen2_upload_1",
        ],
        "key",
        output,
        batch_rows=1,
        upload_workers=2,
    )
    assert len(db.writes) == 3
    assert "nscreen2_upload_0" in db.writes[0] + db.writes[1]
    assert "nscreen2_upload_1" in db.writes[0] + db.writes[1]
    assert set(replay.state["clusters"]["key"]["packed_upload"]["batches"].values()) == {
        "complete"
    }


def test_failed_table_can_resume_as_view_without_changing_select(tmp_path, monkeypatch):
    from replay import runner

    class FakeWarehouse:
        last_query_id = "fixture-query"

        def __init__(self):
            self.writes = []
            self.reads = []

        def rows(self, sql):
            self.reads.append(sql)
            return []

        def execute(self, sql):
            self.writes.append(sql)
            if "CREATE TABLE" in sql:
                raise RuntimeError("HIVE_WRITER_DATA_ERROR")

    monkeypatch.setattr(runner, "ROOT", tmp_path)
    db = FakeWarehouse()
    replay = runner.Replay("view_retry", FORGE, "2026-09-18", warehouse=db)
    query = "SELECT 1 AS value UNION ALL SELECT 1 UNION ALL SELECT NULL"
    with pytest.raises(RuntimeError, match="HIVE_WRITER_DATA_ERROR"):
        replay.artifact("initial", query, partition_columns=["day"])
    failed = dict(replay.state["artifacts"]["initial"])
    target = replay.artifact("initial", query, view=True)
    current = replay.state["artifacts"]["initial"]
    assert target.endswith("initial_a2")
    assert current["kind"] == "view"
    assert current["sql_hash"] == failed["sql_hash"]
    assert current["previous_attempts"] == [failed["table"]]
    assert db.writes[-1].endswith("AS\n" + query)
    assert "CREATE VIEW" in db.writes[-1]
    assert "partitioning" not in db.writes[-1]
    assert not any("$snapshots" in sql for sql in db.reads)
    assert replay.artifact("initial", query, view=True) == target
    assert len(db.writes) == 2
    with pytest.raises(RuntimeError, match="storage kind cannot change"):
        replay.artifact("initial", query)


def test_initial_view_choice_persists_and_other_stages_remain_tables(
    tmp_path, monkeypatch
):
    from replay import runner

    class FakeWarehouse:
        last_query_id = "fixture-query"

        def __init__(self):
            self.writes = []

        def rows(self, sql):
            return []

        def execute(self, sql):
            self.writes.append(sql)

    monkeypatch.setattr(runner, "ROOT", tmp_path)
    monkeypatch.setattr(
        runner, "FILES", {"initial": "unused", "connected_ns": "unused"}
    )
    monkeypatch.setattr(runner.Replay, "pin", lambda self: None)
    monkeypatch.setattr(runner.Replay, "refs", lambda self, stage: {})
    monkeypatch.setattr(
        runner, "compile_stage", lambda *a, **kw: (None, "SELECT 1 AS value")
    )
    db = FakeWarehouse()
    replay = runner.Replay("remember_view", FORGE, "2026-09-18", warehouse=db)
    replay.run(until="initial", initial_as_view=True)
    assert replay.state["stage_storage"] == {"initial": "view"}
    replay.state["artifacts"]["initial"]["status"] = "failed"
    replay.save()
    replay.lock.close()
    resumed = runner.Replay("remember_view", FORGE, warehouse=db)
    resumed.run(until="connected_ns")
    assert ["CREATE VIEW" in sql for sql in db.writes] == [True, True, False]
    resumed.write_report()
    assert "Virtual stages: initial" in (resumed.directory / "report.md").read_text()


def test_initial_view_does_not_replace_completed_table(tmp_path, monkeypatch):
    from replay import runner

    monkeypatch.setattr(runner, "ROOT", tmp_path)
    replay = runner.Replay("keep_table", FORGE, "2026-09-18", warehouse=object())
    replay.state["artifacts"]["initial"] = {"status": "complete"}
    with pytest.raises(RuntimeError, match="already materialized"):
        replay.run(initial_as_view=True)
    assert "stage_storage" not in replay.state


@pytest.mark.skipif(
    not os.environ.get("NSCREEN_JAVA_TEST"),
    reason="Run build-java, then set NSCREEN_JAVA_TEST=1",
)
def test_original_java_bridge(tmp_path):
    path = tmp_path / "edges.tsv"
    path.write_text(
        "\t".join([base64.b64encode(x.encode()).decode() for x in ("v19", "v21")])
        + "\t4.0\tfalse\tfalse\n"
    )
    out = tmp_path / "result.tsv"
    subprocess.run([*java.command(FORGE, "512m"), str(path), str(out)], check=True)
    rows = [line.split("\t") for line in out.read_text().splitlines()]
    assert {base64.b64decode(r[0]).decode() for r in rows} == {"v19", "v21"}
    assert len({r[3] for r in rows}) == 1
    assert rows[0][3] != "0"


LIVE = pytest.mark.skipif(
    not os.environ.get("NSCREEN_LIVE_TEST"),
    reason="Opt-in read-only Trino fixture checks",
)


@LIVE
def test_multisets_nulls_and_duplicates_live():
    query = multiset_diff(
        "SELECT * FROM (VALUES (1),(1),(NULL)) AS t(x)",
        "SELECT * FROM (VALUES (1),(NULL),(NULL)) AS t(x)",
        ["x"],
    )
    assert set(map(tuple, Warehouse().rows(query))) == {(1, 1), (None, -1)}


@LIVE
def test_source_stages_against_existing_verified_fixture():
    fixture = (
        Path(__file__).resolve().parents[2]
        / "nscreen-graph-exploration/docs/provider_alignment_app/alignment_example.py"
    )
    spec = importlib.util.spec_from_file_location("alignment_fixture", fixture)
    f = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(f)
    expected = f.build_example()
    db = Warehouse()
    refs = {table: "fixture_" + table for table in (*INPUTS, STAGED, REMAINDER)}
    staged = []

    def values(name, rows, columns, types):
        tuples = []
        for row in rows:
            fields = []
            for key, kind in zip(columns, types):
                val = row.get(key)
                text = repr(val) if isinstance(val, float) else literal(val)
                fields.append(f"CAST({text} AS {kind})")
            tuples.append("(" + ",".join(fields) + ")")
        return f"{name}({','.join(columns)}) AS (VALUES " + ",".join(tuples) + ")"

    source = []
    provider_cols = ["uid", "matchid", "householdid", "stable", "day"]
    provider_types = ["varchar", "bigint", "bigint", "boolean", "varchar"]
    for table, rows in [
        ("liveramp_source", f.LIVERAMP),
        ("throtle_source", f.THROTLE),
        ("experian_source", f.EXPERIAN),
    ]:
        source.append(
            values(
                refs[table],
                [dict(r, day=f.DAY) for r in rows],
                provider_cols,
                provider_types,
            )
        )
    source.append(
        values(
            refs[INPUTS[3]],
            [dict(r, day=f.DAY) for r in f.EDGES],
            ["uid1", "uid2", "weight", "samedevice", "differentusers", "day"],
            ["varchar", "varchar", "real", "boolean", "boolean", "varchar"],
        )
    )
    source.append(
        values(
            refs[INPUTS[4]],
            [dict(r, day=f.DAY) for r in f.GEO],
            ["uid", "geo", "day"],
            ["varchar", "varchar", "varchar"],
        )
    )
    cols = ["uid", "matchid", "householdid", "stable", "reason", "day", "stage"]
    types = ["varchar", "bigint", "bigint", "boolean", "varchar", "varchar", "varchar"]
    for stage, reference in [
        ("lrth", "raw1"),
        ("initial", "initial"),
        ("connected_ns", "connected"),
        ("stage1", "stage1"),
        ("stage2", "stage2"),
        ("remainder", "remainder"),
    ]:
        ctes = list(source)
        if staged:
            ctes.append(values(refs[STAGED], staged, cols, types))
        mapping, query = compile_stage(
            SQL, stage, f.DAY, refs, mapping_table="fixture_mapping"
        )
        if mapping:
            ctes.append(f"fixture_mapping AS ({mapping})")
        rows = db.rows("WITH " + ",\n".join(ctes) + "\n" + query)
        keys = (
            cols
            if stage != "remainder"
            else [
                "uid1",
                "uid2",
                "weight",
                "samedevice",
                "differentusers",
                "geo",
                "day",
            ]
        )
        want = [dict(r, day=f.DAY, stage=stage) for r in expected[reference]]
        assert Counter(map(tuple, rows)) == Counter(
            tuple(r[k] for k in keys) for r in want
        ), stage
        if stage != "remainder":
            staged.extend(dict(zip(keys, row)) for row in rows)


@LIVE
def test_final_sql_filters_and_nulls_live():
    refs = {STAGED: "fixture_staged"}
    _, query = compile_stage(SQL, "result", "2026-09-18", refs)
    rows = Warehouse().rows(
        "WITH fixture_staged(uid,matchid,householdid,stable,reason,day,stage) AS (VALUES "
        "('kept',12,0,true,'LR','2026-09-18','initial'),"
        "('kept',12,0,true,'LR','2026-09-18','initial'),"
        "('nullhh',13,NULL,false,'LU','2026-09-18','louvain'),"
        "('LR_filtered',14,0,true,'IC','2026-09-18','stage1'),"
        "('000---!!**',15,0,true,'EX','2026-09-18','initial'),"
        "('zero',0,0,false,'LU','2026-09-18','louvain'),"
        "('notfinal',16,0,true,'NA','2026-09-18','connected_ns')) " + query
    )
    assert Counter(map(tuple, rows)) == Counter(
        [("kept", "S_12", "", "LR", "2026-09-18")] * 2
        + [("nullhh", "13", None, "LU", "2026-09-18")]
    )


@LIVE
def test_structural_comparison_detects_membership_changes_live():
    def data(match_b):
        return (
            "SELECT * FROM (VALUES ('a','x','','LU'),"
            f"('b','{match_b}','','LU')) AS t(uid,matchid,householdid,reason)"
        )

    original = canonical_result(data("x"))
    renamed = canonical_result(data("x").replace("'x'", "'y'"))
    split = canonical_result(data("y"))
    columns = [
        "uid",
        "match_members",
        "household_members",
        "match_kind",
        "household_kind",
        "reason",
    ]
    db = Warehouse()
    assert db.rows(multiset_diff(original, renamed, columns)) == []
    assert len(db.rows(multiset_diff(original, split, columns))) == 4


@LIVE
def test_louvain_preserves_global_hash_join_live():
    _, query = compile_stage(
        SQL, "louvain", "2026-09-18", {}, cluster_table="fixture_cluster"
    )
    rows = Warehouse().rows(
        "WITH fixture_cluster(geo,uid,uidhash,deviceid,matchid,householdid) AS (VALUES "
        "('A','u1',7,1,11,0),('A','u2',7,1,11,0),('B','u1',7,2,22,0)) " + query
    )
    # Two unique UID mappings cross both per-geography results for the same hash.
    assert len(rows) == 4
    assert {(r[0], r[1]) for r in rows} == {
        ("u1", 11),
        ("u1", 22),
        ("u2", 11),
        ("u2", 22),
    }

"""Resumable prepared-source replay. All graph SQL executes on Trino."""

import base64
import concurrent.futures
import datetime as dt
import fcntl
import hashlib
import json
import math
import os
import re
import shutil
import struct
import subprocess
from pathlib import Path

from . import java
from .sql import (
    FILES,
    INPUTS,
    REMAINDER,
    RESULT,
    STAGE_COLUMNS,
    STAGED,
    canonical_result,
    compile_stage,
    identifier,
    literal,
    multiset_diff,
    qualified_table,
    source_hashes,
    versioned_ref,
)
from .warehouse import Warehouse

ROOT = Path(__file__).resolve().parents[1]
LOCAL_CLUSTER_STAGE = "local-clusters"
LOCAL_RESULT_STAGE = "local-result"
DEFAULT_INPUT_TABLES = {
    name: f"iceberg.crossscreen.{name}" for name in INPUTS
}


def stamp():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def save_json(path, obj):
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(obj, indent=2, default=str) + "\n")
    temp.replace(path)


def local_cluster_progress(state):
    datasets = [
        entry["local_parquet"]
        for entry in state.get("clusters", {}).values()
        if entry.get("local_parquet", {}).get("status") == "complete"
    ]
    return {
        "completed_geographies": len(datasets),
        "total_geographies": state.get("clustering_capacity", {}).get("geos"),
        "rows": sum(item["rows"] for item in datasets),
        "bytes": sum(item["bytes"] for item in datasets),
    }


def column_type(schema, name):
    for row in schema:
        if str(row[0]).lower() == name.lower():
            return str(row[1]).lower()
    raise ValueError(f"Missing required column: {name}")


def typed_day_literal(schema, day):
    kind = column_type(schema, "day")
    if kind == "date":
        dt.date.fromisoformat(day)
        return f"DATE {literal(day)}"
    if kind.startswith(("varchar", "char")):
        return literal(day)
    raise ValueError(f"Unsupported day column type: {kind}")


class Replay:
    def __init__(
        self,
        run_id,
        forge,
        day=None,
        warehouse=None,
        accept_engine_change=False,
        input_tables=None,
        profile=None,
    ):
        self.run_id = identifier(run_id)
        self.forge = Path(forge).expanduser().resolve()
        self.source_root = self.forge / "nscreen-graph/src/nscreen_graph/spark/sparksql"
        self.directory = ROOT / "runs" / run_id
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.lock = (self.directory / ".lock").open("w")
        fcntl.flock(self.lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        self.path = self.directory / "manifest.json"
        self.db = warehouse or Warehouse()
        requested_inputs = dict(DEFAULT_INPUT_TABLES)
        for name, table in (input_tables or {}).items():
            if name not in INPUTS:
                raise ValueError(f"Unknown replay input: {name}")
            requested_inputs[name] = qualified_table(table)
        if self.path.exists():
            self.state = json.loads(self.path.read_text())
            if day and self.state["day"] != day:
                raise ValueError("Run ID belongs to another processing day")
            if self.state["sql_hashes"] != source_hashes(self.source_root):
                raise ValueError("SQL sources changed; use a new run ID")
            if self.state["java_hash"] != java.fingerprint(self.forge):
                raise ValueError("Java sources changed; use a new run ID")
            persisted_inputs = self.state.get("input_tables", DEFAULT_INPUT_TABLES)
            if input_tables is not None and persisted_inputs != requested_inputs:
                raise ValueError("Run ID belongs to another input configuration")
            if profile and self.state.get("profile") != profile:
                raise ValueError("Run ID belongs to another input profile")
            if self.state["engine_hash"] != self.engine_hash():
                if not accept_engine_change:
                    raise ValueError(
                        "Replay implementation changed; use a new run ID or reviewed --accept-engine-change"
                    )
                self.state.setdefault("engine_migrations", []).append(
                    {
                        "previous": self.state["engine_hash"],
                        "current": self.engine_hash(),
                        "at": stamp(),
                    }
                )
                self.state["engine_hash"] = self.engine_hash()
        else:
            if not day:
                day = self.db.rows(
                    f'SELECT max(partition.day) FROM iceberg.crossscreen."{RESULT}$partitions"'
                )[0][0]
            dt.date.fromisoformat(day)
            self.state = {
                "run_id": run_id,
                "day": day,
                "created_at": stamp(),
                "forge": str(self.forge),
                "sql_hashes": source_hashes(self.source_root),
                "java_hash": java.fingerprint(self.forge),
                "engine_hash": self.engine_hash(),
                "artifacts": {},
                "snapshots": {},
                "clusters": {},
                "status": "created",
                "scope": "prepared sources through final graph",
                "input_tables": requested_inputs,
                "profile": profile,
            }
            self.save()
        self.state.setdefault("input_tables", dict(DEFAULT_INPUT_TABLES))
        self.state.setdefault("profile", None)
        self.input_tables = self.state["input_tables"]
        self.day = self.state["day"]
        session = json.loads(os.environ.get("NSCREEN_TRINO_SESSION", "{}"))
        self.state.setdefault("invocations", []).append(
            {"at": stamp(), "session_properties": session}
        )
        self.save()

    @staticmethod
    def engine_hash():
        files = sorted((ROOT / "replay").glob("*.py"))
        return hashlib.sha256(b"".join(f.read_bytes() for f in files)).hexdigest()

    def save(self):
        self.state["updated_at"] = stamp()
        save_json(self.path, self.state)

    def table(self, suffix):
        return (
            "iceberg.jteixeira_ipa.nscreen2_" + self.run_id + "_" + identifier(suffix)
        )

    def pin(self):
        if self.state.get("pinned"):
            return
        for table in (*INPUTS, STAGED, REMAINDER, RESULT):
            if table in self.state["snapshots"]:
                continue
            source_table = self.input_tables.get(
                table, f"iceberg.crossscreen.{table}"
            )
            catalog, schema, physical_name = source_table.split(".")
            snapshot = self.db.rows(
                f'SELECT snapshot_id FROM {catalog}.{schema}."{physical_name}$history" '
                "ORDER BY made_current_at DESC LIMIT 1"
            )[0][0]
            table_schema = self.db.rows(f"DESCRIBE {source_table}")
            sample = self.db.rows(
                f"SELECT * FROM {versioned_ref(source_table, snapshot)} "
                f"WHERE day={typed_day_literal(table_schema, self.day)} LIMIT 1"
            )
            if not sample:
                raise RuntimeError(
                    f"No input partition for {table} day={self.day}"
                )
            self.state["snapshots"][table] = {
                "snapshot_id": snapshot,
                "schema": table_schema,
                "source_table": source_table,
            }
            self.save()
        self.state["trino_version"] = self.db.rows("SELECT version()")[0][0]
        self.state["pinned"] = True
        self.state["input_provenance"] = (
            "Current snapshots pin the chosen day. Production jobs' historical read snapshot IDs "
            "are unavailable; comparisons measure selected inputs against current production outputs."
        )
        self.save()

    def ref(self, table):
        snapshot = self.state["snapshots"][table]
        source_table = snapshot.get("source_table", f"iceberg.crossscreen.{table}")
        reference = versioned_ref(source_table, snapshot["snapshot_id"])
        if table not in INPUTS or column_type(snapshot["schema"], "day") != "date":
            return reference
        columns = []
        for row in snapshot["schema"]:
            name = identifier(str(row[0]).lower())
            columns.append(
                f"CAST({name} AS VARCHAR) AS {name}" if name == "day" else name
            )
        return (
            f"(SELECT {','.join(columns)} FROM {reference}) "
            f"AS {identifier(table)}"
        )

    def production(self, stage):
        table = (
            REMAINDER
            if stage == "remainder"
            else RESULT
            if stage == "result"
            else STAGED
        )
        where = f"day={literal(self.day)}"
        if table == STAGED:
            where += f" AND stage={literal(stage)}"
        return f"SELECT * FROM {self.ref(table)} WHERE {where}"

    def artifact(self, key, query, view=False, partition_columns=None):
        """Atomic CTAS publication; failed attempts remain isolated, never dropped."""
        identifier(key)
        digest = hashlib.sha256(query.encode()).hexdigest()
        prior = self.state["artifacts"].get(key)
        if prior and prior["sql_hash"] != digest:
            raise RuntimeError(f"Compiled query changed for {key}; use a new run ID")
        if prior and prior["status"] == "complete":
            if prior.get("kind") and prior["kind"] != ("view" if view else "table"):
                raise RuntimeError(f"Completed {key} storage kind cannot change")
            self.db.rows(f"SELECT * FROM {prior['table']} LIMIT 0")
            return prior["table"]
        if prior:
            # A killed client can leave a server query running. Never launch a duplicate.
            tag = f"/* nscreen-replay:{self.run_id}:{key}:"
            active = self.db.rows(
                "SELECT query_id,state FROM system.runtime.queries "
                f"WHERE query LIKE {literal(tag + '%')} AND state NOT IN ('FINISHED','FAILED')"
            )
            if active:
                raise RuntimeError(f"Previous {key} query still active: {active}")
        attempt = 1 + (prior or {}).get("attempt", 0)
        target = self.table(f"{key}_a{attempt}")
        entry = {
            "table": target,
            "attempt": attempt,
            "sql_hash": digest,
            "started_at": stamp(),
            "status": "running",
            "kind": "view" if view else "table",
        }
        if prior:
            entry["previous_attempts"] = [
                *prior.get("previous_attempts", []),
                prior["table"],
            ]
        self.state["artifacts"][key] = entry
        sql_dir = self.directory / "sql"
        sql_dir.mkdir(exist_ok=True)
        properties = ""
        if not view:
            properties = " WITH (format='PARQUET'"
            if partition_columns:
                properties += (
                    ", partitioning=ARRAY["
                    + ",".join(map(literal, partition_columns))
                    + "]"
                )
            properties += ")"
        statement = (
            f"CREATE {'VIEW' if view else 'TABLE'} {target}{properties} AS\n{query}"
        )
        (sql_dir / f"{key}_a{attempt}.sql").write_text(statement + ";\n")
        self.save()
        print(f"{stamp()} START {key}: {target}", flush=True)
        try:
            self.db.execute(
                f"/* nscreen-replay:{self.run_id}:{key}:{attempt} */\n" + statement
            )
        except BaseException as error:
            entry.update(status="failed", error=str(error), ended_at=stamp())
            self.save()
            raise
        entry.update(
            status="complete", query_id=self.db.last_query_id, ended_at=stamp()
        )
        if not view:
            metadata = self.db.rows(
                f'SELECT snapshot_id,summary FROM {target.rsplit(".", 1)[0]}."{target.rsplit(".", 1)[1]}$snapshots" ORDER BY committed_at DESC LIMIT 1'
            )
            if metadata:
                entry["snapshot_id"], entry["summary"] = metadata[0]
        self.save()
        print(f"{stamp()} DONE {key}", flush=True)
        return target

    def refs(self, stage):
        refs = {table: self.ref(table) for table in INPUTS}
        completed = [
            name
            for name in (
                "lrth",
                "initial",
                "connected_ns",
                "stage1",
                "stage2",
                "louvain",
            )
            if self.state["artifacts"].get(name, {}).get("status") == "complete"
        ]
        if completed:
            query = "\nUNION ALL\n".join(
                f"SELECT {STAGE_COLUMNS},day,stage FROM {self.state['artifacts'][name]['table']}"
                for name in completed
            )
            refs[STAGED] = self.artifact("staged_before_" + stage, query, view=True)
        if self.state["artifacts"].get("remainder", {}).get("status") == "complete":
            refs[REMAINDER] = self.state["artifacts"]["remainder"]["table"]
        return refs

    def run(
        self,
        until="result",
        heap="6g",
        max_edges=2_000_000,
        batch_rows=10_000,
        upload_shards=32,
        upload_workers=8,
        initial_as_view=False,
        largest_first=False,
        cluster_output="trino",
        remainder_output=None,
        local_sql_memory="8GB",
        local_sql_threads=2,
    ):
        if cluster_output not in {"trino", "parquet"}:
            raise ValueError("cluster_output must be trino or parquet")
        remainder_output = remainder_output or (
            "parquet" if cluster_output == "parquet" else "trino"
        )
        if remainder_output not in {"trino", "parquet"}:
            raise ValueError("remainder_output must be trino or parquet")
        if remainder_output == "parquet" and cluster_output != "parquet":
            raise ValueError("Parquet remainder requires parquet cluster output")
        local_sql_memory = local_sql_memory.upper()
        if not re.fullmatch(r"[1-9][0-9]*(?:MB|GB)", local_sql_memory):
            raise ValueError("local_sql_memory must use positive MB or GB units")
        if not 1 <= local_sql_threads <= 16:
            raise ValueError("local_sql_threads must be between 1 and 16")
        if until == LOCAL_CLUSTER_STAGE and cluster_output != "parquet":
            raise ValueError("local-clusters requires parquet cluster output")
        if cluster_output == "parquet" and until not in {
            LOCAL_CLUSTER_STAGE,
            LOCAL_RESULT_STAGE,
        }:
            raise ValueError("Parquet output requires a local stage boundary")
        if until == LOCAL_RESULT_STAGE and cluster_output != "parquet":
            raise ValueError("local-result requires parquet cluster output")
        recorded_output = self.state.get("cluster_output")
        if recorded_output and recorded_output != cluster_output:
            raise RuntimeError("Cluster output mode cannot change during resume")
        self.state["cluster_output"] = cluster_output
        recorded_remainder = self.state.get("remainder_output")
        if recorded_remainder and recorded_remainder != remainder_output:
            raise RuntimeError("Remainder output mode cannot change during resume")
        self.state["remainder_output"] = remainder_output
        self.save()
        if initial_as_view:
            prior = self.state["artifacts"].get("initial", {})
            if prior.get("status") == "complete" and prior.get("kind") != "view":
                raise RuntimeError(
                    "initial is already materialized; keep its checkpoint or use a new run ID"
                )
            self.state.setdefault("stage_storage", {})["initial"] = "view"
            self.save()
        self.pin()
        self.state["status"] = "running"
        self.state.pop("last_error", None)
        self.save()
        for stage in FILES:
            stage_complete = self.state["artifacts"].get(stage, {}).get(
                "status"
            ) == "complete"
            if stage == "remainder" and remainder_output == "parquet":
                stage_complete = self.local_dataset_complete(
                    self.state.get("local_remainder", {})
                )
            if stage_complete:
                if stage == until:
                    self.state["status"] = (
                        "computed" if stage == "result" else f"computed_through_{stage}"
                    )
                    self.save()
                    return
                continue
            cluster_table = None
            if stage == "louvain":
                cluster_table = self.cluster(
                    heap,
                    max_edges,
                    batch_rows,
                    upload_shards,
                    upload_workers,
                    largest_first=largest_first,
                    output=cluster_output,
                )
                if cluster_output == "parquet":
                    if until == LOCAL_CLUSTER_STAGE:
                        self.state["status"] = "clustered_local"
                        self.save()
                        return
                    recorded_memory = self.state.get("local_sql_memory")
                    if recorded_memory and recorded_memory != local_sql_memory:
                        raise RuntimeError(
                            "Local SQL memory cannot change during resume"
                        )
                    self.state["local_sql_memory"] = local_sql_memory
                    self.state["local_sql_threads"] = local_sql_threads
                    self.save()
                    self.local_downstream(local_sql_memory, local_sql_threads)
                    self.state["status"] = "computed_local"
                    self.save()
                    return
            refs = self.refs(stage)
            mapping, _ = compile_stage(
                self.source_root,
                stage,
                self.day,
                refs,
                mapping_table=self.table("mapping_placeholder"),
                cluster_table=cluster_table,
            )
            mapping_table = (
                self.artifact(stage + "_mapping", mapping) if mapping else None
            )
            _, query = compile_stage(
                self.source_root,
                stage,
                self.day,
                refs,
                mapping_table=mapping_table,
                cluster_table=cluster_table,
            )
            if stage == "remainder" and remainder_output == "parquet":
                self.persist_local_remainder(query, local_sql_memory)
                if stage == until:
                    break
                continue
            self.artifact(
                stage,
                query,
                view=self.state.get("stage_storage", {}).get(stage) == "view",
                partition_columns=["day"],
            )
            if stage == until:
                break
        self.state["status"] = (
            "computed" if until == "result" else f"computed_through_{until}"
        )
        self.save()

    def persist_local_remainder(self, query, memory_limit, batch_rows=100_000):
        import duckdb
        import polars as pl

        digest = hashlib.sha256(query.encode()).hexdigest()
        prior = self.state.get("local_remainder", {})
        if prior and prior.get("sql_hash") not in {None, digest}:
            raise RuntimeError("Compiled remainder query changed; use new run ID")
        if self.local_dataset_complete(prior):
            return prior
        root = self.directory / "local"
        root.mkdir(exist_ok=True)
        target = root / "remainder"
        partial = root / "remainder.partial"
        database = root / "remainder.partial.duckdb"
        if target.exists():
            metadata = json.loads((target / "_metadata.json").read_text())
            state = {
                **self.dataset_state(target, metadata),
                "sql_hash": digest,
                "geographies": metadata.get("geographies", []),
            }
            self.state["local_remainder"] = state
            self.save()
            return state
        if partial.exists():
            shutil.rmtree(partial)
        if database.exists():
            database.unlink()
        progress = {
            "status": "running",
            "rows_streamed": 0,
            "started_at": stamp(),
            "updated_at": stamp(),
            "sql_hash": digest,
        }
        self.state["local_remainder_export"] = progress
        self.save()
        sql_dir = self.directory / "sql"
        sql_dir.mkdir(exist_ok=True)
        (sql_dir / "remainder_local.sql").write_text(query + ";\n")
        connection = duckdb.connect(str(database))
        try:
            escaped_temp = str(root / "duckdb-temp").replace("'", "''")
            (root / "duckdb-temp").mkdir(exist_ok=True)
            connection.execute(f"SET temp_directory='{escaped_temp}'")
            connection.execute(f"SET memory_limit='{memory_limit}'")
            connection.execute("SET preserve_insertion_order=false")
            connection.execute(
                "CREATE TABLE remainder(uid1 VARCHAR,uid2 VARCHAR,weight DOUBLE,"
                "samedevice BOOLEAN,differentusers BOOLEAN,geo VARCHAR,day VARCHAR)"
            )
            schema = {
                "uid1": pl.String,
                "uid2": pl.String,
                "weight": pl.Float64,
                "samedevice": pl.Boolean,
                "differentusers": pl.Boolean,
                "geo": pl.String,
                "day": pl.String,
            }
            last_checkpoint = 0
            tagged_query = (
                f"/* nscreen-replay:{self.run_id}:remainder-local */\n" + query
            )
            for rows in self.db.stream_batches(
                tagged_query, batch_rows=batch_rows
            ):
                frame = pl.DataFrame(rows, schema=schema, orient="row")
                connection.register("remainder_batch", frame.to_arrow())
                connection.execute("INSERT INTO remainder SELECT * FROM remainder_batch")
                connection.unregister("remainder_batch")
                progress["rows_streamed"] += len(rows)
                if progress["rows_streamed"] - last_checkpoint >= 1_000_000:
                    progress["updated_at"] = stamp()
                    progress["query_id"] = self.db.last_query_id
                    self.save()
                    last_checkpoint = progress["rows_streamed"]
                    print(
                        f"{stamp()} REMAINDER {progress['rows_streamed']:,} rows",
                        flush=True,
                    )
            geographies = []
            for geo, edges in connection.execute(
                "SELECT geo,count(*) FROM remainder GROUP BY geo ORDER BY geo"
            ).fetchall():
                if geo is None:
                    raise RuntimeError(
                        "Unexpected null geography after production equality join"
                    )
                geographies.append(
                    {
                        "geo": geo,
                        "geo_key": hashlib.sha256(geo.encode()).hexdigest()[:20],
                        "edges": edges,
                    }
                )
            escaped_partial = str(partial).replace("'", "''")
            connection.execute(
                "COPY (SELECT uid1,uid2,weight,samedevice,differentusers,geo,day,"
                "substr(sha256(geo),1,20) AS geo_key FROM remainder) "
                f"TO '{escaped_partial}' (FORMAT parquet, PARTITION_BY (geo_key), "
                "COMPRESSION zstd, ROW_GROUP_SIZE 100000)"
            )
        except BaseException as error:
            progress.update(status="failed", error=str(error), updated_at=stamp())
            self.save()
            raise
        finally:
            connection.close()
        part_paths = sorted(partial.glob("**/*.parquet"))
        if progress["rows_streamed"] and not part_paths:
            raise RuntimeError("Local remainder produced no Parquet files")
        parts = []
        by_key = {}
        for path in part_paths:
            relative = str(path.relative_to(partial))
            key = path.parent.name.removeprefix("geo_key=")
            rows = pl.scan_parquet(path).select(pl.len()).collect().item()
            part = {
                "name": relative,
                "rows": rows,
                "bytes": path.stat().st_size,
                "sha256": self.file_hash(path),
            }
            parts.append(part)
            by_key.setdefault(key, []).append(relative)
        for geography in geographies:
            geography["parts"] = by_key.get(geography["geo_key"], [])
        metadata = self.publish_metadata(
            partial,
            rows=progress["rows_streamed"],
            parts=parts,
            extra={
                "schema": {
                    "uid1": "string",
                    "uid2": "string",
                    "weight": "float64",
                    "samedevice": "boolean",
                    "differentusers": "boolean",
                    "geo": "string",
                    "day": "string",
                },
                "partitioning": "geo_key=sha256(geo)[:20]",
                "geographies": geographies,
                "sql_hash": digest,
            },
        )
        partial.replace(target)
        database.unlink()
        state = {
            **self.dataset_state(target, metadata),
            "sql_hash": digest,
            "geographies": geographies,
        }
        self.state["local_remainder"] = state
        progress.update(
            status="complete",
            rows_streamed=metadata["rows"],
            query_id=self.db.last_query_id,
            updated_at=stamp(),
        )
        self.save()
        return state

    def iter_local_remainder_edges(self, geography, batch_rows=100_000):
        import pyarrow.parquet as pq

        root = self.directory / self.state["local_remainder"]["path"]
        columns = ["uid1", "uid2", "weight", "samedevice", "differentusers"]
        for name in geography["parts"]:
            parquet = pq.ParquetFile(root / name)
            for batch in parquet.iter_batches(batch_size=batch_rows, columns=columns):
                values = [batch.column(index).to_pylist() for index in range(5)]
                yield from zip(*values, strict=True)

    def cluster(
        self,
        heap,
        max_edges,
        batch_rows,
        upload_shards,
        upload_workers,
        largest_first=False,
        output="trino",
    ):
        direction = "DESC" if largest_first else "ASC"
        local_remainder = self.state.get("local_remainder", {})
        if self.local_dataset_complete(local_remainder):
            geography_entries = local_remainder.get("geographies", [])
            geos = [(item["geo"], item["edges"]) for item in geography_entries]
            geos.sort(key=lambda row: ((-row[1] if largest_first else row[1]), row[0]))
            geography_by_name = {item["geo"]: item for item in geography_entries}
            remainder = None
        else:
            remainder = self.state["artifacts"]["remainder"]["table"]
            geos = self.db.rows(
                f"SELECT geo,count(*) AS edges FROM {remainder} "
                f"GROUP BY geo ORDER BY edges {direction},geo"
            )
            geography_by_name = {}
        if any(geo is None for geo, _ in geos):
            raise RuntimeError(
                "Unexpected null geography after production equality join"
            )
        largest = max((count for _, count in geos), default=0)
        self.state["clustering_capacity"] = {
            "geos": len(geos),
            "largest_edges": largest,
            "max_edges": max_edges,
            "heap": heap,
            "order": "largest_first" if largest_first else "smallest_first",
        }
        self.save()
        if largest > max_edges:
            raise RuntimeError(
                f"Largest geography has {largest:,} edges; guard is {max_edges:,}. "
                "Whole-geo Java aggregation cannot be split without changing semantics. "
                "Provide sufficient heap and explicitly raise --max-geo-edges."
            )
        bridge = java.command(self.forge, heap)
        ingest = []
        if output == "trino":
            empty_upload = (
                "SELECT CAST(NULL AS VARCHAR) AS geo,"
                "CAST(NULL AS BIGINT) AS batch_id,CAST(NULL AS VARCHAR) AS uid,"
                "CAST(NULL AS BIGINT) AS uidhash,"
                "CAST(NULL AS BIGINT) AS deviceid,CAST(NULL AS BIGINT) AS matchid,"
                "CAST(NULL AS BIGINT) AS householdid WHERE false"
            )
            ingest = [
                self.artifact(
                    f"cluster_packed_{shard:02d}",
                    empty_upload,
                    partition_columns=["geo"],
                )
                for shard in range(upload_shards)
            ]
        work = self.directory / "clustering"
        work.mkdir(exist_ok=True)
        for geo, edges in geos:
            geo_key = hashlib.sha256(geo.encode()).hexdigest()[:20]
            entry = self.state["clusters"].setdefault(
                geo_key, {"geo": geo, "edges": edges}
            )
            input_path, output_path = (
                work / (geo_key + ".input.tsv"),
                work / (geo_key + ".output.tsv"),
            )
            if output == "trino" and entry.get("packed_status") == "complete":
                continue
            if output == "parquet" and self.local_parquet_complete(entry):
                for temporary in (input_path, output_path):
                    if temporary.exists():
                        temporary.unlink()
                continue
            if output_path.exists() and not entry.get("output_sha256"):
                raise RuntimeError(
                    f"Uncommitted Java output for {geo}; preserve for inspection and use a new run"
                )
            if not output_path.exists():
                if shutil.disk_usage(work).free < max(edges * 512, 2 * 1024**3):
                    raise RuntimeError("Insufficient disk headroom for next geography")
                count = 0
                with input_path.open("w") as edge_file:
                    edge_rows = (
                        self.iter_local_remainder_edges(geography_by_name[geo])
                        if remainder is None
                        else self.db.stream(
                            f"SELECT uid1,uid2,weight,samedevice,differentusers FROM {remainder} WHERE geo={literal(geo)}"
                        )
                    )
                    for uid1, uid2, weight, same, different in edge_rows:
                        if any(
                            v is None for v in (uid1, uid2, weight, same, different)
                        ) or not math.isfinite(weight):
                            raise RuntimeError(
                                "Null/nonfinite clustering inputs require explicit Hive compatibility handling"
                            )
                        fields = [
                            base64.b64encode(uid.encode()).decode()
                            for uid in (uid1, uid2)
                        ]
                        edge_file.write(
                            "\t".join(
                                [
                                    *fields,
                                    repr(weight),
                                    str(same).lower(),
                                    str(different).lower(),
                                ]
                            )
                            + "\n"
                        )
                        count += 1
                if count != edges:
                    raise RuntimeError("Remainder changed during export")
                temporary = output_path.with_suffix(".partial")
                subprocess.run([*bridge, str(input_path), str(temporary)], check=True)
                temporary.replace(output_path)
                entry["output_sha256"] = self.file_hash(output_path)
                self.save()
            elif self.file_hash(output_path) != entry["output_sha256"]:
                raise RuntimeError(
                    "Clustering output changed; refusing mismatched resume"
                )
            if output == "parquet":
                self.persist_geo_parquet(geo_key, output_path)
                if output_path.exists():
                    output_path.unlink()
                entry["local_status"] = "complete"
            else:
                self.upload_geo(
                    ingest,
                    geo_key,
                    output_path,
                    batch_rows,
                    upload_workers,
                )
                entry["packed_status"] = "complete"
            entry["status"] = "complete"
            self.save()
            # Trino keeps Java output; both modes release downloaded edges.
            if input_path.exists():
                input_path.unlink()
            print(f"{stamp()} CLUSTER {geo}: {edges:,} edges complete", flush=True)
        if output == "parquet":
            self.write_local_cluster_manifest()
            return None
        union = "\nUNION ALL\n".join(f"SELECT * FROM {table}" for table in ingest)
        return self.artifact("cluster_packed", union, view=True)

    def local_parquet_complete(self, entry):
        metadata = entry.get("local_parquet", {})
        if metadata.get("status") != "complete":
            return False
        directory = self.directory / metadata["path"]
        sidecar = directory / "_metadata.json"
        if not sidecar.is_file():
            raise RuntimeError("Local Parquet metadata is missing")
        recorded = json.loads(sidecar.read_text())
        for part in recorded.get("parts", []):
            path = directory / part["name"]
            if not path.is_file() or path.stat().st_size != part["bytes"]:
                raise RuntimeError("Local Parquet dataset is incomplete")
        digest = hashlib.sha256(
            json.dumps(
                recorded.get("parts", []),
                sort_keys=True,
                separators=(",", ":"),
            ).encode()
        ).hexdigest()
        if (
            digest != recorded.get("dataset_sha256")
            or digest != metadata.get("dataset_sha256")
            or recorded.get("rows") != metadata.get("rows")
            or recorded.get("bytes") != metadata.get("bytes")
        ):
            raise RuntimeError("Local Parquet metadata changed")
        return True

    def persist_geo_parquet(self, geo_key, source_path, chunk_rows=250_000):
        import polars as pl

        entry = self.state["clusters"][geo_key]
        root = self.directory / "clustering" / "parquet"
        root.mkdir(parents=True, exist_ok=True)
        target = root / geo_key
        partial = root / (geo_key + ".partial")
        if target.exists():
            sidecar = target / "_metadata.json"
            if not sidecar.is_file():
                raise RuntimeError("Uncommitted local Parquet output already exists")
            metadata = json.loads(sidecar.read_text())
            entry["local_parquet"] = {
                "status": "complete",
                "path": str(target.relative_to(self.directory)),
                "rows": metadata["rows"],
                "bytes": metadata["bytes"],
                "parts": len(metadata["parts"]),
                "dataset_sha256": metadata["dataset_sha256"],
            }
            self.save()
            if not self.local_parquet_complete(entry):
                raise RuntimeError("Local Parquet reconciliation failed")
            return
        if partial.exists():
            shutil.rmtree(partial)
        partial.mkdir()
        schema = {
            "geo": pl.String,
            "uid": pl.String,
            "uidhash": pl.Int64,
            "deviceid": pl.Int64,
            "matchid": pl.Int64,
            "householdid": pl.Int64,
        }
        parts = []
        rows = []
        total_rows = 0

        def nullable_int(value):
            return None if value == "null" else int(value)

        def flush():
            nonlocal rows, total_rows
            if not rows:
                return
            name = f"part-{len(parts):05d}.parquet"
            path = partial / name
            frame = pl.DataFrame(rows, schema=schema, orient="row")
            frame.write_parquet(
                path,
                compression="zstd",
                compression_level=3,
                statistics=True,
                row_group_size=min(100_000, len(rows)),
            )
            size = path.stat().st_size
            parts.append(
                {
                    "name": name,
                    "rows": len(rows),
                    "bytes": size,
                    "sha256": self.file_hash(path),
                }
            )
            total_rows += len(rows)
            rows = []

        with source_path.open() as source:
            for line in source:
                fields = line.rstrip("\n").split("\t")
                if len(fields) != 5:
                    raise RuntimeError("Unexpected clustering output shape")
                encoded_uid, uid_hash, device, match, household = fields
                rows.append(
                    (
                        entry["geo"],
                        base64.b64decode(encoded_uid, validate=True).decode(),
                        int(uid_hash),
                        nullable_int(device),
                        nullable_int(match),
                        nullable_int(household),
                    )
                )
                if len(rows) >= chunk_rows:
                    flush()
        flush()
        digest = hashlib.sha256(
            json.dumps(parts, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        metadata = {
            "format": "parquet_dataset",
            "compression": "zstd",
            "geo": entry["geo"],
            "rows": total_rows,
            "bytes": sum(part["bytes"] for part in parts),
            "dataset_sha256": digest,
            "parts": parts,
        }
        save_json(partial / "_metadata.json", metadata)
        partial.replace(target)
        entry["local_parquet"] = {
            "status": "complete",
            "path": str(target.relative_to(self.directory)),
            "rows": total_rows,
            "bytes": metadata["bytes"],
            "parts": len(parts),
            "dataset_sha256": digest,
        }
        self.save()

    def write_local_cluster_manifest(self):
        datasets = [
            entry["local_parquet"]
            for entry in self.state["clusters"].values()
            if entry.get("local_parquet", {}).get("status") == "complete"
        ]
        manifest = {
            "format": "parquet_dataset",
            "compression": "zstd",
            "schema": {
                "geo": "string",
                "uid": "string",
                "uidhash": "int64",
                "deviceid": "int64 nullable",
                "matchid": "int64 nullable",
                "householdid": "int64 nullable",
            },
            "glob": "*/part-*.parquet",
            "geographies": len(datasets),
            "rows": sum(item["rows"] for item in datasets),
            "bytes": sum(item["bytes"] for item in datasets),
            "created_at": stamp(),
        }
        root = self.directory / "clustering" / "parquet"
        root.mkdir(parents=True, exist_ok=True)
        path = root / "_manifest.json"
        save_json(path, manifest)
        self.state["local_clusters"] = {
            **manifest,
            "path": str(path.relative_to(self.directory)),
        }
        self.save()

    def local_dataset_complete(self, metadata):
        if metadata.get("status") != "complete":
            return False
        directory = self.directory / metadata["path"]
        sidecar = directory / "_metadata.json"
        if not sidecar.is_file():
            raise RuntimeError("Local dataset metadata is missing")
        recorded = json.loads(sidecar.read_text())
        for part in recorded.get("parts", []):
            path = directory / part["name"]
            if not path.is_file() or path.stat().st_size != part["bytes"]:
                raise RuntimeError("Local dataset is incomplete")
        digest = hashlib.sha256(
            json.dumps(
                recorded.get("parts", []),
                sort_keys=True,
                separators=(",", ":"),
            ).encode()
        ).hexdigest()
        if (
            digest != recorded.get("dataset_sha256")
            or digest != metadata.get("dataset_sha256")
            or recorded.get("rows") != metadata.get("rows")
            or recorded.get("bytes") != metadata.get("bytes")
        ):
            raise RuntimeError("Local dataset metadata changed")
        return True

    def reconcile_local_dataset(self, directory):
        sidecar = directory / "_metadata.json"
        if not sidecar.is_file():
            raise RuntimeError(f"Uncommitted local dataset exists: {directory.name}")
        state = self.dataset_state(directory, json.loads(sidecar.read_text()))
        if not self.local_dataset_complete(state):
            raise RuntimeError(f"Local dataset reconciliation failed: {directory.name}")
        return state

    def export_local_stage(self, stage, chunk_rows=250_000):
        import polars as pl

        exports = self.state.setdefault("local_stage_exports", {})
        prior = exports.get(stage, {})
        if self.local_dataset_complete(prior):
            return prior
        root = self.directory / "local" / "staged"
        root.mkdir(parents=True, exist_ok=True)
        target = root / stage
        partial = root / (stage + ".partial")
        if target.exists():
            exports[stage] = self.reconcile_local_dataset(target)
            self.save()
            return exports[stage]
        if partial.exists():
            shutil.rmtree(partial)
        partial.mkdir()
        schema = {
            "uid": pl.String,
            "matchid": pl.Int64,
            "householdid": pl.Int64,
            "stable": pl.Boolean,
            "reason": pl.String,
        }
        parts = []
        rows = []
        total_rows = 0

        def flush():
            nonlocal rows, total_rows
            if not rows:
                return
            name = f"part-{len(parts):05d}.parquet"
            path = partial / name
            pl.DataFrame(rows, schema=schema, orient="row").write_parquet(
                path,
                compression="zstd",
                compression_level=3,
                statistics=True,
                row_group_size=min(100_000, len(rows)),
            )
            size = path.stat().st_size
            parts.append(
                {
                    "name": name,
                    "rows": len(rows),
                    "bytes": size,
                    "sha256": self.file_hash(path),
                }
            )
            total_rows += len(rows)
            rows = []

        table = self.state["artifacts"][stage]["table"]
        for uid, matchid, householdid, stable, reason in self.db.stream(
            f"SELECT uid,matchid,householdid,stable,reason FROM {table}"
        ):
            rows.append(
                (
                    uid,
                    None if matchid is None else int(matchid),
                    None if householdid is None else int(householdid),
                    stable,
                    reason,
                )
            )
            if len(rows) >= chunk_rows:
                flush()
        flush()
        if not parts:
            path = partial / "part-00000.parquet"
            pl.DataFrame(schema=schema).write_parquet(
                path,
                compression="zstd",
                compression_level=3,
                statistics=True,
            )
            parts.append(
                {
                    "name": path.name,
                    "rows": 0,
                    "bytes": path.stat().st_size,
                    "sha256": self.file_hash(path),
                }
            )
        metadata = self.publish_metadata(
            partial,
            rows=total_rows,
            parts=parts,
            extra={"stage": stage},
        )
        partial.replace(target)
        exports[stage] = self.dataset_state(target, metadata)
        self.save()
        return exports[stage]

    def publish_duckdb_dataset(self, connection, name, query):
        import polars as pl

        root = self.directory / "local"
        root.mkdir(exist_ok=True)
        target = root / name
        partial = root / (name + ".partial")
        if target.exists():
            return self.reconcile_local_dataset(target)
        if partial.exists():
            shutil.rmtree(partial)
        escaped = str(partial).replace("'", "''")
        connection.execute(
            f"COPY ({query}) TO '{escaped}' "
            "(FORMAT parquet, COMPRESSION zstd, PER_THREAD_OUTPUT true, "
            "ROW_GROUP_SIZE 100000)"
        )
        part_paths = sorted(partial.glob("*.parquet"))
        if not part_paths:
            raise RuntimeError(f"Local dataset produced no files: {name}")
        parts = []
        for path in part_paths:
            rows = pl.scan_parquet(path).select(pl.len()).collect().item()
            parts.append(
                {
                    "name": path.name,
                    "rows": rows,
                    "bytes": path.stat().st_size,
                    "sha256": self.file_hash(path),
                }
            )
        metadata = self.publish_metadata(
            partial,
            rows=sum(part["rows"] for part in parts),
            parts=parts,
        )
        partial.replace(target)
        return self.dataset_state(target, metadata)

    def publish_metadata(self, directory, rows, parts, extra=None):
        digest = hashlib.sha256(
            json.dumps(parts, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        metadata = {
            "format": "parquet_dataset",
            "compression": "zstd",
            "rows": rows,
            "bytes": sum(part["bytes"] for part in parts),
            "dataset_sha256": digest,
            "parts": parts,
            **(extra or {}),
        }
        save_json(directory / "_metadata.json", metadata)
        return metadata

    def dataset_state(self, directory, metadata):
        return {
            "status": "complete",
            "path": str(directory.relative_to(self.directory)),
            "rows": metadata["rows"],
            "bytes": metadata["bytes"],
            "parts": len(metadata["parts"]),
            "dataset_sha256": metadata["dataset_sha256"],
        }

    def local_downstream(self, memory_limit, threads=2):
        import duckdb

        for stage in ("initial", "stage1", "stage2"):
            self.export_local_stage(stage)
        local = self.directory / "local"
        temp = local / "duckdb-temp"
        temp.mkdir(parents=True, exist_ok=True)
        database = local / "downstream.duckdb"
        connection = duckdb.connect(str(database))
        try:
            quoted_temp = str(temp).replace("'", "''")
            connection.execute(f"SET temp_directory='{quoted_temp}'")
            connection.execute(f"SET memory_limit='{memory_limit}'")
            connection.execute(f"SET threads={threads}")
            connection.execute("SET preserve_insertion_order=false")
            cluster_glob = str(
                self.directory
                / "clustering"
                / "parquet"
                / "*"
                / "part-*.parquet"
            ).replace("'", "''")
            stage_glob = str(
                self.directory / "local" / "staged" / "*" / "part-*.parquet"
            ).replace("'", "''")
            louvain = self.state.get("local_louvain", {})
            if not self.local_dataset_complete(louvain):
                louvain_query = f"""
WITH clusters AS (
  SELECT geo,uid,uidhash,deviceid,matchid,householdid
  FROM read_parquet('{cluster_glob}')
),
inlined AS (
  SELECT DISTINCT geo,uidhash,deviceid,matchid,householdid FROM clusters
),
uid_to_hash AS (
  SELECT DISTINCT uid,uidhash FROM clusters
)
SELECT u.uid,i.matchid,i.householdid,false AS stable,'LU' AS reason,
       '{self.day}' AS day,'louvain' AS stage
FROM inlined i
INNER JOIN uid_to_hash u ON i.uidhash=u.uidhash
"""
                self.state["local_louvain"] = self.publish_duckdb_dataset(
                    connection, "louvain", louvain_query
                )
                self.save()
            result = self.state.get("local_result", {})
            if not self.local_dataset_complete(result):
                louvain_glob = str(
                    self.directory / "local" / "louvain" / "*.parquet"
                ).replace("'", "''")
                result_query = f"""
WITH all_stages AS (
  SELECT uid,matchid,householdid,stable,reason FROM read_parquet('{stage_glob}')
  UNION ALL
  SELECT uid,matchid,householdid,stable,reason FROM read_parquet('{louvain_glob}')
)
SELECT uid,
       CASE WHEN stable THEN 'S_' || CAST(matchid AS VARCHAR)
            ELSE CAST(matchid AS VARCHAR) END AS matchid,
       CASE WHEN householdid=0 THEN ''
            WHEN stable THEN 'S_' || CAST(householdid AS VARCHAR)
            ELSE CAST(householdid AS VARCHAR) END AS householdid,
       reason,'{self.day}' AS day
FROM all_stages
WHERE matchid<>0
  AND NOT (regexp_matches(uid,'^LR_.*$') AND reason='IC')
  AND NOT regexp_matches(uid,'^[01_!*\\-]*$')
"""
                self.state["local_result"] = self.publish_duckdb_dataset(
                    connection, "result", result_query
                )
                self.save()
        finally:
            connection.close()
        manifest = {
            "format": "parquet_datasets",
            "engine": f"duckdb {duckdb.__version__}",
            "memory_limit": memory_limit,
            "threads": threads,
            "stage_exports": self.state["local_stage_exports"],
            "louvain": self.state["local_louvain"],
            "result": self.state["local_result"],
            "created_at": stamp(),
        }
        path = local / "_manifest.json"
        save_json(path, manifest)
        self.state["local_output"] = {
            "status": "complete",
            "path": str(path.relative_to(self.directory)),
        }
        self.save()

    def resume_local_downstream(self, memory_limit=None, threads=2):
        if self.state.get("cluster_output") != "parquet":
            raise RuntimeError("Local resume requires Parquet cluster output")
        progress = local_cluster_progress(self.state)
        if progress["completed_geographies"] != progress["total_geographies"]:
            raise RuntimeError("Local resume requires complete clustering output")
        missing = [
            stage
            for stage in ("initial", "stage1", "stage2")
            if not self.local_dataset_complete(
                self.state.get("local_stage_exports", {}).get(stage, {})
            )
        ]
        if missing:
            raise RuntimeError(
                "Local resume requires complete stage exports: " + ", ".join(missing)
            )
        memory_limit = memory_limit or self.state.get("local_sql_memory", "8GB")
        memory_limit = memory_limit.upper()
        if not re.fullmatch(r"[1-9][0-9]*(?:MB|GB)", memory_limit):
            raise ValueError("memory_limit must use positive MB or GB units")
        if not 1 <= threads <= 16:
            raise ValueError("threads must be between 1 and 16")
        self.state.update(
            status="running",
            local_sql_memory=memory_limit,
            local_sql_threads=threads,
        )
        self.state.pop("last_error", None)
        self.save()
        self.local_downstream(memory_limit, threads)
        self.state["status"] = "computed_local"
        self.save()

    @staticmethod
    def file_hash(path):
        with path.open("rb") as stream:
            return hashlib.file_digest(stream, "sha256").hexdigest()

    @staticmethod
    def packed_upload_sql(target, tag, geo, batch_id, lines):
        packed = bytearray()
        nulls = []
        uids = []
        for fields in lines:
            if len(fields) == 5:
                encoded_uid, uid_hash, device, match, household = fields
            else:
                raise RuntimeError("Unexpected clustering output shape")
            uid = base64.b64decode(encoded_uid).decode()
            if "\x1f" in uid:
                raise RuntimeError("UID contains packed upload delimiter")
            uids.append(uid)
            if uid_hash == "null":
                raise RuntimeError("Null UID hash cannot be uploaded")
            nullable = (device, match, household)
            mask = sum(1 << index for index, value in enumerate(nullable) if value == "null")
            values = [int(uid_hash), *[0 if value == "null" else int(value) for value in nullable]]
            packed.extend(struct.pack(">qqqq", *values))
            nulls.append(str(mask))
        payload = base64.b64encode(packed).decode()
        null_mask = "".join(nulls)
        uid_payload = "\x1f".join(uids)
        count = len(lines)
        return (
            f"{tag}\nINSERT INTO {target}\n"
            f"WITH encoded(data,nulls,uids) AS (VALUES (from_base64({literal(payload)}),"
            f"{literal(null_mask)},{literal(uid_payload)}))\n"
            f"SELECT {literal(geo)},{batch_id},element_at(split(uids,chr(31)),i+1),"
            "from_big_endian_64(substr(data,i*32+1,8)),"
            "IF(substr(nulls,i+1,1) IN ('1','3','5','7'),NULL,"
            "from_big_endian_64(substr(data,i*32+9,8))),"
            "IF(substr(nulls,i+1,1) IN ('2','3','6','7'),NULL,"
            "from_big_endian_64(substr(data,i*32+17,8))),"
            "IF(substr(nulls,i+1,1) IN ('4','5','6','7'),NULL,"
            "from_big_endian_64(substr(data,i*32+25,8)))\n"
            f"FROM encoded CROSS JOIN UNNEST(sequence(0,{count - 1})) AS t(i)"
        )

    def upload_geo(self, targets, geo_key, path, batch_rows, upload_workers=1):
        if isinstance(targets, str):
            targets = [targets]
        entry = self.state["clusters"][geo_key]
        config = {"batch_rows": batch_rows, "shards": len(targets)}
        upload = entry.setdefault("packed_upload", {"config": config, "batches": {}})
        if upload.get("config") != config:
            raise RuntimeError("Packed upload configuration cannot change during resume")
        batches = upload["batches"]

        def committed_rows(batch_id):
            target = targets[batch_id % len(targets)]
            return self.db.rows(
                f"SELECT count(*) FROM {target} "
                f"WHERE geo={literal(entry['geo'])} AND batch_id={batch_id}"
            )[0][0]

        def reconcile(batch_id, count):
            key = str(batch_id)
            tag = f"/* nscreen-replay:{self.run_id}:packed:{geo_key}:{batch_id} */"
            active = self.db.rows(
                "SELECT query_id FROM system.runtime.queries WHERE "
                f"query LIKE {literal(tag + '%')} AND state NOT IN ('FINISHED','FAILED')"
            )
            if active:
                raise RuntimeError(f"Upload still running: {active}")
            uploaded = committed_rows(batch_id)
            if uploaded == count:
                batches[key] = "complete"
                self.save()
                return True
            if uploaded:
                raise RuntimeError(
                    "Partial/duplicate packed upload detected; no automatic destructive repair"
                )
            return False

        def flush(wave):
            if not wave:
                return
            for batch_id, _, _ in wave:
                batches[str(batch_id)] = "pending"
            self.save()
            errors = {}
            with concurrent.futures.ThreadPoolExecutor(
                max_workers=min(upload_workers, len(wave))
            ) as pool:
                futures = {
                    pool.submit(self.db.execute, sql): (batch_id, len(lines))
                    for batch_id, lines, sql in wave
                }
                for future in concurrent.futures.as_completed(futures):
                    batch_id, count = futures[future]
                    try:
                        future.result()
                    # Every remote failure needs commit reconciliation before retry.
                    except Exception as error:  # noqa: BLE001
                        errors[batch_id] = (error, count)
                    else:
                        batches[str(batch_id)] = "complete"
                        self.save()
            for batch_id, (error, count) in errors.items():
                if not reconcile(batch_id, count):
                    raise error

        with path.open() as source:
            batch_id = 0
            wave = []
            wave_shards = set()
            while True:
                lines = []
                for _ in range(batch_rows):
                    line = source.readline()
                    if not line:
                        break
                    lines.append(line.rstrip("\n").split("\t"))
                if not lines:
                    break
                key = str(batch_id)
                if batches.get(key) == "complete":
                    batch_id += 1
                    continue
                if batches.get(key) == "pending" and reconcile(batch_id, len(lines)):
                    batch_id += 1
                    continue
                shard = batch_id % len(targets)
                if len(wave) >= upload_workers or shard in wave_shards:
                    flush(wave)
                    wave = []
                    wave_shards = set()
                tag = f"/* nscreen-replay:{self.run_id}:packed:{geo_key}:{batch_id} */"
                sql = self.packed_upload_sql(
                    targets[shard], tag, entry["geo"], batch_id, lines
                )
                if len(sql) > 950_000:
                    raise RuntimeError(
                        "Packed upload exceeds safe Trino query length; lower --batch-rows"
                    )
                wave.append((batch_id, lines, sql))
                wave_shards.add(shard)
                batch_id += 1
            flush(wave)

    def compare(self, stages=None, structural=True):
        self.pin()
        comparisons = self.state.setdefault("comparisons", {})
        for stage in stages or list(FILES):
            if self.state["artifacts"].get(stage, {}).get("status") != "complete":
                raise RuntimeError(f"Stage {stage} has not completed")
            table = (
                REMAINDER
                if stage == "remainder"
                else RESULT
                if stage == "result"
                else STAGED
            )
            columns = [r[0] for r in self.state["snapshots"][table]["schema"]]
            local = f"SELECT * FROM {self.state['artifacts'][stage]['table']}"
            diff = self.artifact(
                "diff_" + stage, multiset_diff(local, self.production(stage), columns)
            )
            counts = self.db.rows(
                f"SELECT coalesce(sum(greatest(delta,0)),0),"
                f"coalesce(sum(greatest(-delta,0)),0),count(*) FROM {diff}"
            )[0]
            comparisons[stage] = {
                "extra_rows": counts[0],
                "missing_rows": counts[1],
                "different_distinct_rows": counts[2],
                "exact": counts[2] == 0,
                "diff_table": diff,
                "checked_at": stamp(),
            }
            self.save()
            print(f"COMPARE {stage}: {comparisons[stage]}", flush=True)
        if structural and "result" in (stages or FILES):
            left = canonical_result(
                f"SELECT * FROM {self.state['artifacts']['result']['table']}"
            )
            right = canonical_result(self.production("result"))
            cols = [
                "uid",
                "match_members",
                "household_members",
                "match_kind",
                "household_kind",
                "reason",
            ]
            # Materialize each representation once; comparisons preserve duplicates.
            lc = self.artifact("canonical_local", left)
            rc = self.artifact("canonical_production", right)
            diff = self.artifact(
                "diff_structural",
                multiset_diff(f"SELECT * FROM {lc}", f"SELECT * FROM {rc}", cols),
            )
            counts = self.db.rows(
                f"SELECT coalesce(sum(greatest(delta,0)),0),coalesce(sum(greatest(-delta,0)),0) FROM {diff}"
            )[0]
            comparisons["structural"] = {
                "extra_rows": counts[0],
                "missing_rows": counts[1],
                "equivalent": counts == [0, 0],
                "diff_table": diff,
            }
            self.save()
        self.write_report()

    def write_report(self):
        cluster_output = self.state.get("cluster_output", "trino")
        remainder_output = self.state.get("remainder_output", "trino")
        local_progress = local_cluster_progress(self.state)
        local_result_complete = (
            self.state.get("local_output", {}).get("status") == "complete"
        )
        if local_result_complete:
            scope = "provider sources through local Parquet final output."
        elif cluster_output == "parquet":
            scope = (
                "provider sources plus prepared collocation and geo, "
                "through local Java mappings."
            )
        else:
            scope = "provider sources plus prepared collocation and geo, through final output."
        lines = [
            f"# NScreen prepared-source replay: {self.run_id}",
            "",
            f"Processing day: {self.day}. Updated: {stamp()}.",
            f"Execution status: {self.state['status']}.",
            "",
            f"Scope: {scope}",
            "Raw ingestion, source preparation, and hourly evidence are not replayed.",
            f"Remainder output: {remainder_output}.",
            f"Clustering output: {cluster_output}.",
            f"Input profile: {self.state.get('profile') or 'production defaults'}.",
            "Input tables: "
            + ", ".join(
                f"{name}={table}"
                for name, table in self.state.get("input_tables", {}).items()
            )
            + ".",
            "",
            "Virtual stages: "
            + (
                ", ".join(
                    key
                    for key, value in self.state.get("stage_storage", {}).items()
                    if value == "view"
                )
                or "none"
            )
            + ". A completed view means its definition was published, not its rows materialized. "
            "Downstream queries execute the view SQL again.",
            "",
            self.state.get("input_provenance", "Input snapshots have not been pinned."),
            "",
            "Strict comparison uses full-row multisets, including duplicates and nulls.",
            "Structural comparison replaces IDs with exact sorted UID membership arrays.",
            "Random labels, random clustering order, floating-point aggregation, and SQL tie handling can differ.",
            "",
            "| Comparison | Extra rows | Missing rows | Outcome |",
            "|---|---:|---:|---|",
        ]
        for stage, result in self.state.get("comparisons", {}).items():
            passed = result.get("exact", result.get("equivalent", False))
            lines.append(
                f"| {stage} | {result['extra_rows']} | {result['missing_rows']} | {'PASS' if passed else 'DIFFERENT'} |"
            )
        if not self.state.get("comparisons"):
            lines.append("| None completed | — | — | UNVERIFIED |")
        if cluster_output == "parquet":
            completed = local_progress["completed_geographies"]
            total = local_progress["total_geographies"]
            remainder = self.state.get("local_remainder", {})
            remainder_progress = self.state.get("local_remainder_export", {})
            lines.extend(
                [
                    "",
                    (
                        f"Local remainder: {remainder['rows']:,} rows, "
                        f"{len(remainder.get('geographies', [])):,} geographies, "
                        f"{remainder['bytes']:,} bytes."
                        if remainder.get("status") == "complete"
                        else f"Local remainder export: {remainder_progress.get('status', 'not started')}, "
                        f"{remainder_progress.get('rows_streamed', 0):,} rows streamed."
                    ),
                    (
                        f"Local Parquet progress: {completed}/{total or '?'} geographies, "
                        f"{local_progress['rows']:,} rows, {local_progress['bytes']:,} bytes."
                    ),
                    (
                        f"Local Louvain rows: {self.state['local_louvain']['rows']:,}. "
                        f"Local final rows: {self.state['local_result']['rows']:,}."
                        if local_result_complete
                        else "Local Louvain and final result remain incomplete."
                    ),
                    "Production parity remains unverified.",
                ]
            )
        if self.state["status"] in ("failed", "interrupted"):
            lines.extend(
                [
                    "",
                    "Execution stopped before successful completion.",
                    self.state.get(
                        "last_error", "See artifact failure details in manifest.json."
                    ).split("\\n", 1)[0][:1000],
                ]
            )
        lines.extend(
            [
                "",
                "See manifest.json for snapshots, query IDs, source hashes, failures, and output tables.",
                "Rendered queries are saved in sql/. No production tables are modified.",
                "",
            ]
        )
        (self.directory / "report.md").write_text("\n".join(lines))

"""CLI for the Trino/Java replay."""

import argparse
import json
import os
from pathlib import Path

from . import java
from .runner import (
    LOCAL_CLUSTER_STAGE,
    LOCAL_RESULT_STAGE,
    ROOT,
    Replay,
    local_cluster_progress,
)
from .sql import FILES, INPUTS, REMAINDER, STAGED, compile_stage
from .warehouse import Warehouse


def load_profile(path):
    if not path:
        return None
    profile_path = Path(path).expanduser().resolve()
    data = json.loads(profile_path.read_text())
    if not isinstance(data, dict) or not isinstance(data.get("inputs", {}), dict):
        raise TypeError("Profile must contain an inputs object")
    data["path"] = str(profile_path)
    return data


def parse_input_overrides(values):
    result = {}
    for value in values or []:
        if "=" not in value:
            raise ValueError("Input override must use logical_name=catalog.schema.table")
        name, table = value.split("=", 1)
        result[name] = table
    return result


def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--forge", type=Path, default=Path.home() / "forge")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("doctor", help="Check credentials, Trino, Java, source files")
    commands.add_parser(
        "build-java", help="Download pinned fastutil and compile unchanged Forge code"
    )
    render = commands.add_parser(
        "render", help="Render all adapted queries locally without warehouse writes"
    )
    render.add_argument("--day", required=True)
    for name in ("run", "compare"):
        child = commands.add_parser(name)
        child.add_argument("--run-id", required=True)
        child.add_argument(
            "--accept-engine-change",
            action="store_true",
            help="Record a reviewed runner-only change; SQL/Java source changes still require a new run",
        )
        child.add_argument(
            "--day",
            help="Default: latest production result day; fixed after first invocation",
        )
        if name == "run":
            child.add_argument(
                "--until",
                choices=[*FILES, LOCAL_CLUSTER_STAGE, LOCAL_RESULT_STAGE],
                help="Default: result, or local-result with Parquet output",
            )
            child.add_argument("--java-heap", default="6g")
            child.add_argument("--max-geo-edges", type=int, default=2_000_000)
            child.add_argument("--batch-rows", type=int, default=10_000)
            child.add_argument("--upload-shards", type=int, default=32)
            child.add_argument("--upload-workers", type=int, default=8)
            child.add_argument(
                "--cluster-output",
                choices=["trino", "parquet"],
                default="trino",
                help="Store Java mappings in Trino, or local partitioned Parquet",
            )
            child.add_argument(
                "--remainder-output",
                choices=["trino", "parquet"],
                help="Store remainder in Trino or local Parquet; defaults with cluster output",
            )
            child.add_argument(
                "--local-sql-memory",
                default="8GB",
                help="DuckDB memory limit for local Louvain and final result",
            )
            child.add_argument(
                "--local-sql-threads",
                type=int,
                default=2,
                help="DuckDB worker limit for local Louvain and final result",
            )
            child.add_argument(
                "--largest-first",
                action="store_true",
                help="Process largest geography first to test local capacity early",
            )
            child.add_argument(
                "--initial-as-view",
                action="store_true",
                help="Publish initial as an ordinary view; remembered on resume, no HDFS row write for this stage",
            )
            child.add_argument(
                "--profile",
                type=Path,
                help="JSON profile containing day and logical input-table overrides",
            )
            child.add_argument(
                "--input",
                action="append",
                default=[],
                metavar="NAME=CATALOG.SCHEMA.TABLE",
                help="Override one prepared input; repeat for multiple inputs",
            )
        else:
            child.add_argument("--stages", nargs="+", choices=FILES)
            child.add_argument("--skip-structural", action="store_true")
    status = commands.add_parser("status")
    status.add_argument("--run-id", required=True)
    local_resume = commands.add_parser(
        "resume-local", help="Resume downstream work using existing local files only"
    )
    local_resume.add_argument("--run-id", required=True)
    local_resume.add_argument("--accept-engine-change", action="store_true")
    local_resume.add_argument("--local-sql-memory")
    local_resume.add_argument("--local-sql-threads", type=int, default=2)
    args = parser.parse_args()
    if args.command == "doctor":
        db = Warehouse()
        print("Trino:", db.rows("SELECT version(),current_user"))
        print("Java:", java.java_home())
        print("Java source fingerprint:", java.fingerprint(args.forge))
        for name in INPUTS:
            print(
                name,
                db.rows(
                    f'SELECT max(partition.day) FROM iceberg.crossscreen."{name}$partitions"'
                ),
            )
    elif args.command == "build-java":
        print(*java.build(args.forge), sep="\n")
    elif args.command == "render":
        root = args.forge / "nscreen-graph/src/nscreen_graph/spark/sparksql"
        refs = {
            name: f"iceberg.crossscreen.{name} FOR VERSION AS OF 1" for name in INPUTS
        }
        refs[STAGED] = "iceberg.jteixeira_ipa.nscreen2_example_staged"
        refs[REMAINDER] = "iceberg.jteixeira_ipa.nscreen2_example_remainder"
        for stage in FILES:
            mapping, query = compile_stage(
                root,
                stage,
                args.day,
                refs,
                mapping_table="iceberg.jteixeira_ipa.nscreen2_example_mapping",
                cluster_table="iceberg.jteixeira_ipa.nscreen2_example_clusters",
            )
            print(f"-- {stage}\n{mapping or ''}\n{query};\n")
    elif args.command == "status":
        from .sql import identifier

        manifest = ROOT / "runs" / identifier(args.run_id) / "manifest.json"
        state = json.loads(manifest.read_text())
        result = {
            key: state.get(key)
            for key in (
                "run_id",
                "day",
                "status",
                "updated_at",
                "cluster_output",
                "remainder_output",
                "artifacts",
                "comparisons",
                "clustering_capacity",
                "local_clusters",
                "local_remainder",
                "local_remainder_export",
                "local_stage_exports",
                "local_louvain",
                "local_result",
                "local_output",
            )
        }
        if state.get("cluster_output") == "parquet":
            result["local_cluster_progress"] = local_cluster_progress(state)
        print(
            json.dumps(result, indent=2)
        )
    elif args.command == "resume-local":
        replay = Replay(
            args.run_id,
            args.forge,
            accept_engine_change=args.accept_engine_change,
        )
        try:
            replay.resume_local_downstream(
                args.local_sql_memory,
                args.local_sql_threads,
            )
        except BaseException as error:
            replay.state["status"] = (
                "interrupted" if isinstance(error, KeyboardInterrupt) else "failed"
            )
            replay.state["last_error"] = str(error)
            replay.save()
            raise
        finally:
            replay.write_report()
    else:
        if (
            args.command == "compare"
            and not (ROOT / "runs" / args.run_id / "manifest.json").is_file()
        ):
            parser.error("compare requires an existing run")
        profile = load_profile(args.profile) if args.command == "run" else None
        inputs = dict(profile.get("inputs", {})) if profile else {}
        if args.command == "run":
            inputs.update(parse_input_overrides(args.input))
            profile_day = profile.get("day") if profile else None
            if args.day and profile_day and args.day != profile_day:
                parser.error("--day conflicts with profile day")
            day = args.day or profile_day
            profile_name = profile.get("name", profile["path"]) if profile else None
        else:
            day = args.day
            profile_name = None
        replay = Replay(
            args.run_id,
            args.forge,
            day,
            accept_engine_change=args.accept_engine_change,
            input_tables=inputs or None,
            profile=profile_name,
        )
        try:
            if args.command == "run":
                until = args.until or (
                    LOCAL_RESULT_STAGE
                    if args.cluster_output == "parquet"
                    else "result"
                )
                if (
                    args.cluster_output == "parquet"
                    and until not in {LOCAL_CLUSTER_STAGE, LOCAL_RESULT_STAGE}
                ):
                    parser.error(
                        "--cluster-output parquet requires a local stage boundary"
                    )
                if (
                    until in {LOCAL_CLUSTER_STAGE, LOCAL_RESULT_STAGE}
                    and args.cluster_output != "parquet"
                ):
                    parser.error(
                        "local stage boundaries require --cluster-output parquet"
                    )
                if (
                    args.max_geo_edges <= 0
                    or not 1 <= args.batch_rows <= 20_000
                    or not 1 <= args.upload_workers <= args.upload_shards <= 64
                    or not 1 <= args.local_sql_threads <= 16
                ):
                    parser.error(
                        "max-geo-edges must be positive; batch-rows must be 1..20000; "
                        "upload-workers must be 1..upload-shards; upload-shards must be 1..64; "
                        "local-sql-threads must be 1..16"
                    )
                replay.run(
                    until,
                    args.java_heap,
                    args.max_geo_edges,
                    args.batch_rows,
                    args.upload_shards,
                    args.upload_workers,
                    initial_as_view=args.initial_as_view,
                    largest_first=args.largest_first,
                    cluster_output=args.cluster_output,
                    remainder_output=args.remainder_output,
                    local_sql_memory=args.local_sql_memory,
                    local_sql_threads=args.local_sql_threads,
                )
            else:
                replay.compare(args.stages, not args.skip_structural)
        except BaseException as error:
            replay.state["status"] = (
                "interrupted" if isinstance(error, KeyboardInterrupt) else "failed"
            )
            replay.state["last_error"] = str(error)
            replay.save()
            raise
        finally:
            replay.write_report()


if __name__ == "__main__":
    main()

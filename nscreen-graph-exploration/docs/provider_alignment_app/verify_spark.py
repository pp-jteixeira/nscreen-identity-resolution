"""Execute repository SQL and the actual Java UDAF on local toy tables.

Requires the repository-root .venv, a JDK, and --fastutil /path/to/fastutil.jar.
The external murmur3 UDF alone is replaced by unique numeric toy UID labels.
No production catalog, SQL writes, or credentials are used.
"""

import argparse
import os
import subprocess
import tempfile
from collections import Counter
from pathlib import Path

import pyspark
from alignment_example import (
    CONNECTED,
    DAY,
    EDGES,
    EXPERIAN,
    GEO,
    JOB1,
    JOB2,
    LIVERAMP,
    LOUVAIN,
    PROPAGATE,
    REMAINDER,
    REPO_ROOT,
    RESULT,
    SQL_ROOT,
    THROTLE,
    build_example,
)
from pyspark.sql import SparkSession

SCHEMA = "uid string, matchid long, householdid long, stable boolean, reason string, day string, stage string"
TABLE_NAMES = [
    "throtle_source",
    "liveramp_source",
    "experian_source",
    "nscreen_liveramp_throtle_ex_reason_staged",
    "nscreen_ipcollocation_daily_clean",
    "nscreen_geo_daily_ua",
    "nscreen_ipcollocation_daily_remainder_ex",
]


def compile_udaf(directory, fastutil):
    jdk = Path(os.environ["JAVA_HOME"]) / "bin"
    jars = Path(pyspark.__file__).parent / "jars"
    source_root = REPO_ROOT / "src/jvm/com/pulsepoint/hive/udf"
    sources = sorted((source_root / "calcscreen7ids").rglob("*.java")) + sorted(
        (source_root / "louvain").glob("*.java")
    )
    classes = directory / "classes"
    classes.mkdir()
    subprocess.run(
        [str(jdk / "javac"), "-cp", f"{jars}/*:{fastutil}", "-d", str(classes), *map(str, sources)], check=True
    )
    jar = directory / "screen7-fixture.jar"
    subprocess.run([str(jdk / "jar"), "cf", str(jar), "-C", str(classes), "."], check=True)
    return jar


def verify(fastutil):
    with tempfile.TemporaryDirectory(prefix="provider-alignment-check-") as temp:
        jar = compile_udaf(Path(temp), fastutil)
        spark = (
            SparkSession.builder.master("local[2]")
            .appName("provider-alignment-example-check")
            .config("spark.ui.enabled", "false")
            .config("spark.sql.shuffle.partitions", "2")
            .config("spark.jars", f"{jar},{fastutil}")
            .config("spark.sql.warehouse.dir", str(Path(temp) / "warehouse"))
            .config("spark.hadoop.javax.jdo.option.ConnectionURL", "jdbc:derby:memory:provider_alignment;create=true")
            .enableHiveSupport()
            .getOrCreate()
        )
        spark.sparkContext.setLogLevel("ERROR")
        # Hash identity is irrelevant to this 2-node membership test; no collision.
        spark.udf.register("murmur3", lambda uid: int(uid[1:]), "long")
        spark.sql(
            "CREATE TEMPORARY FUNCTION hudf_calc_screen7_ids_udaf AS 'com.pulsepoint.hive.udf.calcscreen7ids.UDAFCalcScreen7IdsResolver'"
        )
        d = build_example()

        def table(name, rows, schema=SCHEMA):
            spark.createDataFrame(
                [dict(r, day=DAY, stage=r.get("stage", "source")) for r in rows], schema
            ).createOrReplaceTempView(name)

        def sql(file, cte=None, current_stage="stage1"):
            query = (REPO_ROOT / SQL_ROOT / file).read_text()
            query = query.replace("{{ var('day') }}", DAY).replace("{{ var('current_stage') }}", current_stage)
            for name in TABLE_NAMES:
                query = query.replace("iceberg.crossscreen." + name, name)
            if cte:
                query = query.split("\nselect\n", 1)[0] + "\nselect * from " + cte
            return [row.asDict() for row in spark.sql(query).collect()]

        def same(actual, expected, keys):
            got = Counter(tuple(r[k] for k in keys) for r in actual)
            want = Counter(tuple(r[k] for k in keys) for r in expected)
            assert got == want, {"keys": keys, "missing": want - got, "unexpected": got - want}

        keys = ["uid", "matchid", "householdid", "stable", "reason"]
        for name, rows in [("throtle_source", THROTLE), ("liveramp_source", LIVERAMP), ("experian_source", EXPERIAN)]:
            table(name, rows)
        table(
            "nscreen_ipcollocation_daily_clean",
            EDGES,
            "uid1 string, uid2 string, weight float, samedevice boolean, differentusers boolean, day string",
        )
        table("nscreen_geo_daily_ua", GEO, "uid string, geo string, day string")
        raw1 = sql(JOB1)
        same(raw1, d["raw1"], [*keys, "stage"])
        same(
            sql(JOB1, "grouped"),
            [dict(r, throtmatchid=r["left"], lrmatchid=r["right"]) for r in d["job1"]["grouped"]],
            ["throtmatchid", "lrmatchid", "cnt"],
        )
        same(
            sql(JOB1, "limited"),
            [dict(r, throtmatchid=r["left"], lrmatchid=r["right"]) for r in d["job1"]["limited"]],
            ["throtmatchid", "lrmatchid", "count1", "count2"],
        )
        staged = [dict(r, stage="lrth") for r in raw1]  # common.py writer override
        table("nscreen_liveramp_throtle_ex_reason_staged", staged)
        initial = sql(JOB2)
        same(initial, d["initial"], [*keys, "stage"])
        same(
            sql(JOB2, "mapping"),
            [dict(r, exmatchid=r["left"], lrthmatchid=r["right"]) for r in d["job2"]["mapping"]],
            ["exmatchid", "lrthmatchid", "reason"],
        )
        staged.extend(initial)
        table("nscreen_liveramp_throtle_ex_reason_staged", staged)
        connected = sql(CONNECTED)
        same(connected, d["connected"], keys)
        staged.extend(dict(r, stage="connected_ns") for r in connected)
        for i in (1, 2):
            table("nscreen_liveramp_throtle_ex_reason_staged", staged)
            grouped = sql(PROPAGATE, "grouped", current_stage=f"stage{i}")
            same(grouped, d[f"p{i}"]["grouped"], ["uid", "matchid", "householdid", "stable", "weight"])
            rows = sql(PROPAGATE, current_stage=f"stage{i}")
            same(rows, d[f"stage{i}"], keys)
            staged.extend(dict(r, stage=f"stage{i}") for r in rows)
        table("nscreen_liveramp_throtle_ex_reason_staged", staged)
        remainder = sql(REMAINDER)
        same(remainder, d["remainder"], ["uid1", "uid2", "weight", "samedevice", "differentusers", "geo"])
        table(
            "nscreen_ipcollocation_daily_remainder_ex",
            remainder,
            "uid1 string, uid2 string, weight float, samedevice boolean, differentusers boolean, geo string, day string",
        )
        louvain = sql(LOUVAIN)
        assert len(louvain) == 2
        assert {r["uid"] for r in louvain} == {"v19", "v21"}
        matches = {r["matchid"] for r in louvain}
        assert len(matches) == 1
        assert 0 not in matches
        # Canonicalize only the random community ID for comparison/display.
        canonical = [dict(r, matchid=901, stage="louvain") for r in louvain]
        same(canonical, d["louvain"], [*keys, "stage"])
        staged.extend(canonical)
        same(staged, d["staged"], [*keys, "stage"])
        table("nscreen_liveramp_throtle_ex_reason_staged", staged)
        same(sql(RESULT), d["result"], ["uid", "matchid", "householdid", "reason"])
        print(  # noqa: T201 - standalone verification result
            "PASS: seven repository SQL files (propagation twice), actual Java UDAF, 58 staged rows, 29 final rows. Only external hashing is a toy-UID stub."
        )
        spark.stop()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fastutil", type=Path, required=True)
    args = parser.parse_args()
    verify(args.fastutil.resolve())

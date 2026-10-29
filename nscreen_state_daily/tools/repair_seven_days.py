"""Resume verified non-hex UID omissions for October 20–22, 2026.

Source/target hex UID counts and checksums must already match the saved audit.
Reads each day's hash-bucket counts/checksums before writing. Completed buckets
are skipped; partial/mismatched buckets stop execution. The already committed
October 22 TX pilot bucket is excluded. No UID join or broad deletion is used.
"""

import argparse
import concurrent.futures
import json
import threading
import time
from pathlib import Path

from trino.exceptions import TrinoQueryError
from trino_bootstrap import bootstrap

ROOT = Path(__file__).resolve().parents[1] / "evidence"
TARGET = "iceberg.jteixeira_ipa.tmp_nscreen_state_daily_ua"
SOURCE = (
    "iceberg.crossscreen.nscreen_geo_daily_ua FOR VERSION AS OF 3964805227883162890"
)
SLICES = {
    "2026-10-20": ["CA", "FL"],
    "2026-10-21": ["CA", "FL", "TX"],
    "2026-10-22": ["FL", "TX"],
}
SETTINGS = {
    "query_max_execution_time": "5m",
    "query_max_run_time": "7m",
    "query_max_memory": "16GB",
    "query_max_total_memory": "24GB",
    "max_hash_partition_count": "16",
    "max_writer_task_count": "4",
    "task_max_writer_count": "1",
    "task_scale_writers_enabled": "false",
    "task_concurrency": "2",
    "iceberg.target_max_file_size": "64MB",
    "iceberg.parquet_writer_block_size": "16MB",
}
LOCK = threading.Lock()


def log(**data):
    data["time"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    line = json.dumps(data)
    with LOCK:
        print(line, flush=True)
        with (ROOT / "seven_day_repair_events.jsonl").open("a") as out:
            out.write(line + "\n")


def run_day(day, args, db):
    # This audit proves the surviving hex-prefix population is complete.
    audit = json.loads((ROOT / f"verify_7d_{day}.json").read_text())
    source_audit = {(r[0], r[1]): r[2:] for r in audit["source"]["rows"]}
    target_audit = {(r[0], r[1]): r[2:] for r in audit["target"]["rows"]}
    for state in SLICES[day]:
        if source_audit[state, "hex"] != target_audit[state, "hex"]:
            raise RuntimeError(f"Hex population mismatch: {day}/{state}")
    if (
        day == "2026-10-22"
        and source_audit["TX", "pilot"] != target_audit["TX", "pilot"]
    ):
        raise RuntimeError("Pilot population mismatch")
    conn = db.get_trino_connection(session_properties=SETTINGS)
    cur = conn.cursor()
    active_insert = None
    try:
        cur.execute("SELECT zip3,state FROM iceberg.jteixeira_ipa.tmp_zip3_to_state")
        mapping = cur.fetchall()
        if len({r[0] for r in mapping}) != len(mapping):
            raise RuntimeError("Mapping keys are no longer unique")
        lookup = {s: [z for z, state in mapping if state == s] for s in SLICES[day]}
        all_zip3 = [z for zs in lookup.values() for z in zs]
        if any(len(z) != 3 or not z.isascii() or not z.isdigit() for z in all_zip3):
            raise RuntimeError("Invalid ZIP3 mapping")
        literal = lambda vals: ",".join("'" + v + "'" for v in vals)
        case = (
            "CASE "
            + " ".join(
                f"WHEN lpad(geo,3,'0') IN ({literal(zs)}) THEN '{s}'"
                for s, zs in lookup.items()
            )
            + " END"
        )
        # Lexical ranges match the non-hex-prefix set, including empty UIDs.
        # Unlike substring predicates, they let Iceberg prune old hex-only files.
        nonhex = "(uid < '0' OR (uid >= ':' AND uid < 'a') OR uid >= 'g')"
        pilot = (
            "NOT (day='2026-10-22' AND state='TX' AND mod(crc32(to_utf8(uid)),256)=0)"
        )
        source = f"SELECT day,uid,{case} AS state FROM {SOURCE} WHERE day='{day}' AND {nonhex} AND regexp_like(geo,'^[0-9]{{1,3}}$') AND lpad(geo,3,'0') IN ({literal(all_zip3)})"
        inputs = {
            "source": f"SELECT day,uid,state FROM ({source}) WHERE {pilot}",
            "target": f"SELECT day,uid,state FROM {TARGET} WHERE day='{day}' AND state IN ({literal(SLICES[day])}) AND {nonhex} AND {pilot}",
        }

        def counts(kind):
            sql = f"SELECT mod(crc32(to_utf8(uid)),{args.buckets}) AS bucket,count(*),to_hex(checksum(ROW(uid,state))) FROM ({inputs[kind]}) GROUP BY 1 ORDER BY 1"
            cur.execute(sql)
            result = {r[0]: r[1:] for r in cur.fetchall()}
            log(
                day=day,
                event="counts",
                kind=kind,
                query_id=cur.query_id,
                buckets=result,
            )
            return result

        expected = counts("source")
        existing = counts("target")
        for bucket, actual in existing.items():
            if expected.get(bucket) != actual:
                raise RuntimeError(
                    f"Partial/mismatched bucket {day}/{bucket}; refusing append"
                )
        selected = (
            [args.bucket] if args.bucket is not None else list(range(args.buckets))
        )
        pending = []
        for bucket in selected:
            if bucket not in expected or bucket in existing:
                log(day=day, bucket=bucket, event="skip_complete")
                continue
            pending.append(bucket)
        for offset in range(0, len(pending), args.batch_buckets):
            batch = pending[offset : offset + args.batch_buckets]
            bucket_list = ",".join(str(b) for b in batch)
            expected_rows = sum(expected[b][0] for b in batch)
            sql = f"INSERT INTO {TARGET} SELECT day,uid,state FROM ({inputs['source']}) WHERE mod(crc32(to_utf8(uid)),{args.buckets}) IN ({bucket_list})"
            stem = f"nonhex_{day}_{'-'.join(map(str, batch))}_of_{args.buckets}"
            (ROOT / f"{stem}.sql").write_text(sql + "\n")
            if not args.execute:
                cur.execute("EXPLAIN " + sql)
                plan = "\n".join(str(r[0]) for r in cur.fetchall())
                (ROOT / f"{stem}_plan.txt").write_text(plan)
                if "Join[" in plan:
                    raise RuntimeError("Unexpected join in append plan")
                log(
                    day=day,
                    buckets=batch,
                    event="plan_verified",
                    expected_rows=expected_rows,
                )
                continue
            for attempt in range(1, args.attempts + 1):
                active_insert = batch
                log(
                    day=day,
                    buckets=batch,
                    event="insert_start",
                    attempt=attempt,
                    expected_rows=expected_rows,
                )
                start = time.monotonic()
                try:
                    cur.execute(sql)
                    inserted = cur.fetchall()
                    if inserted != [[expected_rows]]:
                        raise RuntimeError(f"Unexpected inserted row count: {inserted}")
                except Exception as error:
                    log(
                        day=day,
                        buckets=batch,
                        event="attempt_failed",
                        attempt=attempt,
                        query_id=getattr(cur, "query_id", None),
                        error=str(error),
                    )
                    if not isinstance(error, TrinoQueryError):
                        # A transport failure does not prove the server stopped.
                        # Leave reconciliation to the operator instead of retrying.
                        raise
                    # A commit error can be ambiguous. Inspect logical contents
                    # before retrying; never append into a partial bucket.
                    observed = counts("target")
                    present = [b for b in batch if b in observed]
                    if present:
                        if len(present) != len(batch) or any(
                            observed[b] != expected[b] for b in batch
                        ):
                            raise RuntimeError(
                                "Ambiguous partial commit; refusing retry"
                            ) from error
                        log(
                            day=day,
                            buckets=batch,
                            event="commit_recovered",
                            result=[[expected_rows]],
                        )
                        active_insert = None
                        break
                    if attempt == args.attempts:
                        raise
                    continue
                log(
                    day=day,
                    buckets=batch,
                    event="insert_committed",
                    query_id=cur.query_id,
                    result=inserted,
                    elapsed_seconds=round(time.monotonic() - start, 1),
                )
                active_insert = None
                break
        if args.execute:
            actual = counts("target")
            for bucket in selected:
                if expected.get(bucket) != actual.get(bucket):
                    raise RuntimeError(f"Post-write checksum mismatch {day}/{bucket}")
            log(
                day=day,
                event="verified",
                completed_buckets=len(actual),
                total_buckets=args.buckets,
                complete=actual == expected,
            )
    except Exception as e:
        log(
            day=day,
            event="failed",
            bucket=active_insert,
            query_id=getattr(cur, "query_id", None),
            error=str(e),
        )
        raise
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--day", choices=list(SLICES))
    p.add_argument("--buckets", type=int, default=16)
    p.add_argument("--bucket", type=int)
    p.add_argument("--batch-buckets", type=int, choices=[1, 2, 4], default=1)
    p.add_argument("--attempts", type=int, choices=[1, 2, 3], default=1)
    p.add_argument("--workers", type=int, choices=[1, 2], default=1)
    p.add_argument("--execute", action="store_true")
    args = p.parse_args()
    if not 1 <= args.buckets <= 256 or (
        args.bucket is not None and not 0 <= args.bucket < args.buckets
    ):
        p.error("Invalid hash bucket")
    db, _ = bootstrap()
    days = [args.day] if args.day else list(SLICES)
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = [pool.submit(run_day, day, args, db) for day in days]
        for f in concurrent.futures.as_completed(futures):
            f.result()

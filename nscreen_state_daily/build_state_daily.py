"""Load daily UID states with count/checksum guards and resumable hash buckets.

Existing nonempty buckets must match their source exactly. Partial buckets stop
execution. Failed writes stop without retries or deletion; rerun only after any
server-side query has stopped. Run one loader at a time against this target.
"""

import argparse
import sys
import time
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "tools"))
from trino_bootstrap import bootstrap

SRC = "iceberg.crossscreen.nscreen_geo_daily_ua"
TARGET = "iceberg.jteixeira_ipa.tmp_nscreen_state_daily_ua"
MAP = "iceberg.jteixeira_ipa.tmp_zip3_to_state"


def run(db, sql):
    """Execute writes directly; never hide errors raised after submission."""
    conn = db.get_trino_connection()
    cur = conn.cursor()
    try:
        cur.execute(sql)
        return cur.fetchall()
    finally:
        cur.close()
        conn.close()


def build_mapping(db):
    """Create a mapping only if absent; existing mappings are never dropped."""
    run(
        db,
        f"""CREATE TABLE {MAP} AS
        WITH c AS (
          SELECT substr(provider_zip,1,3) zip3, upper(provider_state) state, count(*) n
          FROM iceberg.npi.npi_reference
          WHERE regexp_like(provider_zip,'^[0-9]{{5}}')
            AND regexp_like(upper(provider_state),'^[A-Z]{{2}}$')
          GROUP BY 1,2
        ), r AS (
          SELECT zip3, state, n, sum(n) OVER (PARTITION BY zip3) tot,
                 row_number() OVER (PARTITION BY zip3 ORDER BY n DESC, state) rn
          FROM c
        )
        SELECT zip3, state, n AS state_npis, tot AS zip3_npis,
               CAST(n AS double)/tot AS state_share FROM r WHERE rn = 1""",
    )


def mapped_sql(day, source, mapping=MAP):
    return f"""SELECT g.day, g.uid, m.state FROM {source} g
        LEFT JOIN {mapping} m
          ON regexp_like(g.geo,'^[0-9]{{1,3}}$') AND lpad(g.geo,3,'0')=m.zip3
        WHERE g.day = '{day}'"""


def bucket_predicate(bucket, buckets):
    # Hash the entire UID: includes nonhex, empty, and NULL values.
    return f"mod(crc32(to_utf8(coalesce(uid, ''))), {buckets}) = {bucket}"


def signatures(db, inner, buckets):
    sql = f"""SELECT state, mod(crc32(to_utf8(coalesce(uid, ''))), {buckets}) AS bucket,
        count(*) AS rows, to_hex(checksum(ROW(uid,state))) AS fingerprint
        FROM ({inner}) GROUP BY 1,2"""
    frame = db.query2df(sql)
    return {
        (r[0] if isinstance(r[0], str) else None, int(r[1])): (int(r[2]), r[3])
        for r in frame.itertuples(index=False, name=None)
    }


def validate_existing(expected, actual):
    for key, signature in actual.items():
        if expected.get(key) != signature:
            raise RuntimeError(f"Partial/mismatched bucket {key}; refusing append")


def load_day(db, day, source, mapping, buckets):
    inner = mapped_sql(day, source, mapping)
    target = f"SELECT day,uid,state FROM {TARGET} WHERE day = '{day}'"
    expected = signatures(db, inner, buckets)
    actual = signatures(db, target, buckets)
    validate_existing(expected, actual)
    for (state, bucket), signature in expected.items():
        if (state, bucket) in actual:
            continue
        state_filter = (
            "state IS NULL"
            if state is None
            else "state = '" + state.replace("'", "''") + "'"
        )
        sql = f"INSERT INTO {TARGET} SELECT day,uid,state FROM ({inner}) WHERE {state_filter} AND {bucket_predicate(bucket, buckets)}"
        started = time.monotonic()
        # Never retry an ambiguous write or delete a partially loaded slice.
        run(db, sql)
        print(
            f"Inserted {day} {state} bucket={bucket} expected_rows={signature[0]} seconds={time.monotonic() - started:.0f}",
            flush=True,
        )
    if signatures(db, target, buckets) != expected:
        raise RuntimeError(f"Post-write count/checksum mismatch for {day}")
    print(f"Verified {day}", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    dates = parser.add_mutually_exclusive_group()
    dates.add_argument(
        "--days", nargs="+", type=lambda s: date.fromisoformat(s).isoformat()
    )
    dates.add_argument("--last-days", type=int)
    parser.add_argument(
        "--build-mapping",
        action="store_true",
        help="create mapping if absent; refuses replacement",
    )
    parser.add_argument(
        "--buckets",
        type=int,
        default=16,
        help="hash buckets per state, 1–256; keep constant across resumptions",
    )
    parser.add_argument(
        "--split-after",
        action="store_true",
        help="deprecated alias for the default 16 hash buckets; no retry on write failure",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="show requested configuration without connecting or writing",
    )
    args = parser.parse_args()
    if not 1 <= args.buckets <= 256 or (
        args.last_days is not None and args.last_days < 1
    ):
        parser.error("Buckets must be 1–256; --last-days must be positive")
    if args.split_after and args.buckets != 16:
        parser.error("--split-after requires --buckets 16")
    if not (args.days or args.last_days or args.build_mapping):
        parser.error("give --days, --last-days, or --build-mapping")
    if args.dry_run:
        print(
            f"target={TARGET} days={args.days} last_days={args.last_days} buckets={args.buckets} build_mapping={args.build_mapping}"
        )
        return
    db, _ = bootstrap()
    if args.build_mapping:
        build_mapping(db)
    if not (args.days or args.last_days):
        return
    # Pin both inputs so all checks and writes use identical source versions.
    snapshots = {}
    for table in [SRC, MAP]:
        schema, name = table.rsplit(".", 1)
        frame = db.query2df(
            f'SELECT snapshot_id FROM {schema}."{name}$history" ORDER BY made_current_at DESC LIMIT 1'
        )
        snapshots[table] = int(frame.iloc[0, 0])
    source = f"{SRC} FOR VERSION AS OF {snapshots[SRC]}"
    mapping = f"{MAP} FOR VERSION AS OF {snapshots[MAP]}"
    duplicate = db.query2df(
        f"SELECT zip3 FROM {mapping} GROUP BY zip3 HAVING count(*) > 1 LIMIT 1"
    )
    if not duplicate.empty:
        raise RuntimeError("Mapping keys are not unique")
    days = args.days
    if args.last_days:
        days = db.query2df(
            f"SELECT DISTINCT day FROM {source} ORDER BY day DESC LIMIT {args.last_days}"
        )["day"].tolist()
    print(f"Pinned snapshots: {snapshots}; buckets={args.buckets}", flush=True)
    run(
        db,
        f"CREATE TABLE IF NOT EXISTS {TARGET} (day varchar, uid varchar, state varchar) WITH (partitioning = ARRAY['day'])",
    )
    for day in sorted(set(days)):
        load_day(db, day, source, mapping, args.buckets)


if __name__ == "__main__":
    main()

"""Verify logical row counts and UID/state checksums, including deleted files."""

import argparse
import json
import time
from datetime import date, timedelta
from pathlib import Path

from trino_bootstrap import bootstrap

p = argparse.ArgumentParser()
p.add_argument("kind", choices=["source", "target"])
p.add_argument(
    "--start", default="2026-10-20", choices=[f"2026-10-{d}" for d in range(20, 27)]
)
p.add_argument(
    "--end", default="2026-10-26", choices=[f"2026-10-{d}" for d in range(20, 27)]
)
a = p.parse_args()
root = Path(__file__).resolve().parents[1] / "evidence"
if a.kind == "source":
    inner = f"SELECT g.day,g.uid,m.state FROM iceberg.crossscreen.nscreen_geo_daily_ua FOR VERSION AS OF 3964805227883162890 g LEFT JOIN iceberg.jteixeira_ipa.tmp_zip3_to_state m ON regexp_like(g.geo,'^[0-9]{{1,3}}$') AND lpad(g.geo,3,'0')=m.zip3 WHERE g.day BETWEEN '{a.start}' AND '{a.end}'"
else:
    inner = f"SELECT day,uid,state FROM iceberg.jteixeira_ipa.tmp_nscreen_state_daily_ua WHERE day BETWEEN '{a.start}' AND '{a.end}'"
sql = f"SELECT day,count(*) AS rows,count_if(uid IS NULL) AS null_uid,count_if(state IS NULL) AS null_state,to_hex(checksum(ROW(uid,state))) AS uid_state_checksum FROM ({inner}) GROUP BY day ORDER BY day"
(root / f"audit_7d_{a.kind}_{a.start}_{a.end}.sql").write_text(sql + "\n")
db, _ = bootstrap()
conn = db.get_trino_connection(
    session_properties={
        "query_max_execution_time": "8m",
        "query_max_run_time": "10m",
        "query_max_memory": "16GB",
        "query_max_total_memory": "24GB",
        "join_distribution_type": "BROADCAST",
        "task_concurrency": "2",
    }
)
cur = conn.cursor()
try:
    start = time.monotonic()
    rows = []
    queries = []
    day = date.fromisoformat(a.start)
    while day <= date.fromisoformat(a.end):
        daily_sql = sql.replace(f"BETWEEN '{a.start}' AND '{a.end}'", f"= '{day}'")
        cur.execute(daily_sql)
        daily = cur.fetchall()
        rows.extend(daily)
        queries.append(cur.query_id)
        result = {
            "kind": a.kind,
            "start": a.start,
            "end": a.end,
            "query_ids": queries,
            "elapsed_seconds": round(time.monotonic() - start, 1),
            "columns": ["day", "rows", "null_uid", "null_state", "uid_state_checksum"],
            "rows": rows,
        }
        (root / f"audit_7d_{a.kind}_{a.start}_{a.end}.json").write_text(
            json.dumps(result, indent=2) + "\n"
        )
        print(json.dumps({"query_id": cur.query_id, "rows": daily}), flush=True)
        day += timedelta(days=1)
finally:
    cur.close()
    conn.close()

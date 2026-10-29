"""Compare source and stored UID counts/checksums for seven incomplete slices."""

import concurrent.futures
import json
import time
from pathlib import Path

from trino_bootstrap import bootstrap

ROOT = Path(__file__).resolve().parents[1] / "evidence"
SLICES = {
    "2026-10-20": ["CA", "FL"],
    "2026-10-21": ["CA", "FL", "TX"],
    "2026-10-22": ["FL", "TX"],
}
DB, _ = bootstrap()


def check(day):
    conn = DB.get_trino_connection(
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
        states = ",".join("'" + s + "'" for s in SLICES[day])
        group = "CASE WHEN strpos('0123456789abcdef', substr(uid,1,1)) > 0 AND length(uid)>0 THEN 'hex' WHEN day='2026-10-22' AND state='TX' AND mod(crc32(to_utf8(uid)),256)=0 THEN 'pilot' ELSE 'nonhex' END"
        inputs = {
            "source": f"SELECT g.day,g.uid,m.state FROM iceberg.crossscreen.nscreen_geo_daily_ua FOR VERSION AS OF 3964805227883162890 g JOIN iceberg.jteixeira_ipa.tmp_zip3_to_state m ON regexp_like(g.geo,'^[0-9]{{1,3}}$') AND lpad(g.geo,3,'0')=m.zip3 WHERE g.day='{day}' AND m.state IN ({states})",
            "target": f"SELECT day,uid,state FROM iceberg.jteixeira_ipa.tmp_nscreen_state_daily_ua WHERE day='{day}' AND state IN ({states})",
        }
        result = {"day": day}
        for kind, inner in inputs.items():
            sql = f"SELECT state,{group} AS uid_group,count(*) AS rows,to_hex(checksum(uid)) AS uid_checksum FROM ({inner}) GROUP BY 1,2 ORDER BY 1,2"
            (ROOT / f"verify_7d_{day}_{kind}.sql").write_text(sql + "\n")
            start = time.monotonic()
            cur.execute(sql)
            rows = cur.fetchall()
            result[kind] = {
                "query_id": cur.query_id,
                "rows": rows,
                "elapsed_seconds": round(time.monotonic() - start, 1),
            }
            (ROOT / f"verify_7d_{day}.json").write_text(
                json.dumps(result, indent=2) + "\n"
            )
            print(json.dumps({"day": day, "kind": kind, **result[kind]}), flush=True)
        return result
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        futures = {pool.submit(check, day): day for day in SLICES}
        for future in concurrent.futures.as_completed(futures):
            future.result()

"""Publish a verification manifest only when all seven logical datasets match."""

import json
from datetime import datetime, timezone
from pathlib import Path

import sys

# Input shape: {"source": <audit>, "targets": [<audit>, ...]}.
# Supply explicitly from an in-memory caller or pipe, without intermediate files.
payload = json.load(sys.stdin)
source = payload["source"]
expected = {r[0]: r for r in source["rows"]}
actual = {}
for audit in payload["targets"]:
    for row in audit["rows"]:
        if row[0] in actual:
            raise RuntimeError("Overlapping target audits")
        actual[row[0]] = row
if (
    set(expected) != {f"2026-10-{day}" for day in range(20, 27)}
    or len(source["rows"]) != 7
    or actual != expected
):
    raise RuntimeError("Seven-day counts/checksums are incomplete or do not match")
result = {
    "status": "verified_complete",
    "verified_at_utc": datetime.now(timezone.utc).isoformat(),
    "target": "iceberg.jteixeira_ipa.tmp_nscreen_state_daily_ua",
    "source": "iceberg.crossscreen.nscreen_geo_daily_ua",
    "source_snapshot": 3964805227883162890,
    "mapping": "iceberg.jteixeira_ipa.tmp_zip3_to_state",
    "date_start": "2026-10-20",
    "date_end": "2026-10-26",
    "total_rows": sum(r[1] for r in expected.values()),
    "unmapped_state_rows": sum(r[3] for r in expected.values()),
    "verification": "Per-day logical counts, NULL counts, and checksum(ROW(uid,state)) match source",
    "columns": source["columns"],
    "rows": [actual[d] for d in sorted(actual)],
}
print(json.dumps(result, indent=2))

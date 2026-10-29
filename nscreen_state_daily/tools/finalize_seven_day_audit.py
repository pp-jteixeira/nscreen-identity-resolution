"""Publish a verification manifest only when all seven logical datasets match."""

import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "evidence"
source_name = "audit_7d_source_2026-10-20_2026-10-26.json"
target_names = [f"audit_7d_target_2026-10-{d}_2026-10-{d}.json" for d in range(20, 23)]
target_names.append("audit_7d_target_2026-10-23_2026-10-26.json")
source = json.loads((ROOT / source_name).read_text())
expected = {r[0]: r for r in source["rows"]}
actual = {}
for name in target_names:
    audit = json.loads((ROOT / name).read_text())
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
    "source_audit": source_name,
    "target_audits": target_names,
}
(ROOT / "seven_day_validation.json").write_text(json.dumps(result, indent=2) + "\n")
print(json.dumps(result, indent=2))

# Daily UID state lookup

Map the selected ZIP3 in `iceberg.crossscreen.nscreen_geo_daily_ua` to a
provider-derived state. Results have columns `day`, `uid`, and `state`.
Numeric ZIP3 values are left-padded to three digits. A left join retains UIDs
with nonnumeric, NULL, or unmapped geography and gives them NULL state.
The source selects geography using the production 15-day hourly lookback.

## Verified historical coverage

The saved October 27, 2026 audits establish complete persisted coverage in
`iceberg.jteixeira_ipa.tmp_nscreen_state_daily_ua` for October 20–26, 2026.
These are historical checks, not a check of the current warehouse state.
Source snapshot: `3964805227883162890`.

| Date | Verified UID/day rows |
|---|---:|
| 2026-10-20 | 3,812,371,308 |
| 2026-10-21 | 3,840,312,450 |
| 2026-10-22 | 3,865,562,171 |
| 2026-10-23 | 3,877,767,922 |
| 2026-10-24 | 3,885,716,182 |
| 2026-10-25 | 3,905,341,143 |
| 2026-10-26 | 3,910,544,115 |

All seven per-day logical row counts, NULL counts, and
`checksum(ROW(uid,state))` match the source audit. Total: 27,097,615,291 rows,
including 24,433,144 NULL-state rows (0.0902% of all rows).
Physical Iceberg file counts can include position-deleted rows and are not
proof of logical completeness. Other historical dates may be incomplete.

The [verification manifest](evidence/seven_day_validation.json) links to the
versioned source and target audits. Their checksums and aggregate counts
contain no individual UID records. The original repair restored 1,348,883,046
rows, including October 22's remaining 296,803,784 rows.

Read only the verified historical window:

```sql
SELECT day, uid, state
FROM iceberg.jteixeira_ipa.tmp_nscreen_state_daily_ua
WHERE day BETWEEN '2026-10-20' AND '2026-10-26';
```

## Read the newest seven source dates

[select_state_daily_7d.sql](select_state_daily_7d.sql) computes the lookup
without materializing a table. Its dates move with source availability.
Add a date or UID filter for bounded consumption; the full population is
roughly 27 billion rows. The query depends on the existing
`iceberg.jteixeira_ipa.tmp_zip3_to_state` mapping.

[create_state_daily_7d_view.sql](create_state_daily_7d_view.sql) defines an
optional live view with the same lookup. The view was not created in the
October 27 run: HDFS metadata writes failed. Run the SELECT directly instead.

The mapping selects the most common provider state per ZIP3 from
`iceberg.npi.npi_reference`; it is not an official USPS boundary table.
It includes territories and military codes. The historical mapping had 998
unique keys, including 19 explicit NULL-state entries. Existing notes identify
44 keys with `state_share < 0.9`, so boundary assignments may be ambiguous.
Creating a new mapping does not recreate those explicit NULL-state entries;
unmapped keys still yield NULL through the left join.

## Environment and commands

Run commands below from the repository root. Use the shared `.venv` and
root `requirements.txt` (including `trino` and `pandas`). Install/configure the
external PulsePoint Trino skill and credentials separately. Tools search
`~/.codex/skills/pulsepoint-trino/scripts`, then the equivalent `.claude` path.
For another location, set `PP_TRINO_SCRIPTS` to its scripts directory.
No credentials are stored here.

```bash
.venv/bin/python nscreen_state_daily/build_state_daily.py --help
.venv/bin/python nscreen_state_daily/build_state_daily.py \
  --days 2026-10-26 --dry-run
```

Dry-run prints configuration without connecting. To load explicitly chosen
dates or the newest N source dates, omit `--dry-run` or use `--last-days N`.
These commands write to the persisted target. Use only one loader at a time.

## Loader safety and resumption

[build_state_daily.py](build_state_daily.py) pins the source and mapping Iceberg
snapshots for each invocation and refuses duplicate mapping keys. It hashes the
entire UID into 16 buckets per state by default, covering nonhex prefixes,
empty UIDs, and NULL UIDs. `--buckets` accepts 1–256; keep it constant across
resumptions. `--split-after` remains a deprecated alias for the default 16
hash buckets. Splitting occurs before writing, not after a failed insert.

Before writing a date, the loader compares every existing state/bucket's count
and UID/state checksum against the pinned inputs. Exact matches are skipped.
Any partial, extra, or mismatched bucket stops the load before writes for that
date. Empty buckets are inserted, then full-day signatures are checked again.
It preserves source row multiplicity rather than deduplicating UID/day rows.
Checksums detect differences but are not a mathematical proof of equality.

A write error stops execution with a nonzero exit status. There are no automatic
write retries or cleanup deletions. Before rerunning after a connection failure,
confirm the previous server query has stopped. A rerun reconciles committed
buckets; partial buckets require operator investigation. Source or mapping
changes between invocations can cause reconciliation to refuse resumption.
Completed earlier dates are retained if a later date fails.

`--build-mapping` creates the mapping only if absent and refuses replacement.
It can run alone. It never drops an existing mapping. Historical split-prefix
omissions and partial states are deliberately rejected by the new loader;
they are not repaired automatically.

## Historical repair and verification

Maintained scripts live under `tools/`. Compact inputs and aggregate audits
live under `evidence/`. Original local execution history under `logs/` is
ignored and is not required by these tools.

[repair_seven_days.py](tools/repair_seven_days.py) is specific to the October
20–22 omissions and pinned source snapshot. It requires the saved
`verify_7d_*.json` inputs, now versioned in `evidence/`. It verifies existing
buckets and refuses partial buckets. Transport failures stop execution;
server query failures are reconciled before bounded retries. It does not
perform a general backfill. Historical snapshots must still exist to rerun it.

The commands below audit or regenerate saved artifacts; they do not insert
warehouse rows. Regenerating source/target audits overwrites the dated evidence,
so review any resulting diff. Source audits use the pinned source snapshot and
the current mapping; the original mapping must remain unchanged to reproduce
the saved comparison.

```bash
.venv/bin/python nscreen_state_daily/tools/audit_seven_days.py source \
  --start 2026-10-20 --end 2026-10-26
.venv/bin/python nscreen_state_daily/tools/audit_seven_days.py target \
  --start 2026-10-20 --end 2026-10-20
.venv/bin/python nscreen_state_daily/tools/audit_seven_days.py target \
  --start 2026-10-21 --end 2026-10-21
.venv/bin/python nscreen_state_daily/tools/audit_seven_days.py target \
  --start 2026-10-22 --end 2026-10-22
.venv/bin/python nscreen_state_daily/tools/audit_seven_days.py target \
  --start 2026-10-23 --end 2026-10-26
.venv/bin/python nscreen_state_daily/tools/finalize_seven_day_audit.py
```

`verify_seven_day_gaps.py` regenerates the historical repair prerequisite audits
against current target contents; its new outputs will differ after repair.
Do not replace the original prerequisites before reviewing that change.
Finalization publishes the manifest only when all seven dates match.

## Local validation

```bash
.venv/bin/python -m unittest discover -s nscreen_state_daily/tests -v
```

Tests use simulated database responses and saved evidence. They do not connect
to Trino or execute warehouse writes. The revised loader still needs a bounded
integration run before operational use.

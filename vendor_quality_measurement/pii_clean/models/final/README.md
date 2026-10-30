# Final table

The [final model](pii_clean.sql) unions all rows and columns from seven vendor metric models using `SELECT *` with `UNION ALL`. It does not deduplicate, filter, score or recompute metrics.

The October 30, 2026 freshness publication contains **108 columns and 75,564,265 rows** in `iceberg.jteixeira_ipa.pii_clean`. It adds five freshness columns while preserving all 103 fields from the October 29 build, including stored `computed_at`. Reference and cookie evidence were not refreshed. [Freshness publication report](../../results/publication_20261030/report.md) · [October 29 full build](../../results/publication_20261029/report.md).

Rows remain at exact source-record/email-position grain. `record_payload` preserves original email-bearing source fields except `day`, represented through observation history. Typed columns retain names, states, provenance and comparison evidence. The October 29 full build preserved the original 41 columns' substantive values and row counts, excluding query-time `computed_at` from checksum comparisons.

From the project directory:

```bash
../../.venv/bin/python tools/pipeline.py build
../../.venv/bin/python tools/pipeline.py final
```

`build` refreshes all dependencies and publishes the final table. `final` publishes from existing vendor views. Both require identical vendor column names, order and types, then materialize vendor outputs once into a candidate. The runner uses the combined union when its plan fits Trino's stage limit, otherwise separate vendor batches.

Validation reads the stored candidate, without recomputing vendor views for checksums. All seven vendors must be present with nonempty row counts and unique keys. Candidate schema and twelve integrity checks must pass before atomic publication. A supplied `build_final(..., preservation=...)` baseline also checks previous published attributes; this is not required by ordinary CLI refreshes. Published schema, per-vendor counts and substantive-column checksums must match the candidate. Source snapshots are not pinned across batches. The current runner flow has local regression coverage but has not yet been exercised in a full warehouse rebuild.

The October 29 103-column combined vendor plan exceeded Trino's 150-stage limit at 721 stages. The full publication used a uniquely named candidate table and separate vendor batches. The candidate passed all eleven native integrity checks and preserved the previous published attributes before atomic `CREATE OR REPLACE TABLE ... AS` publication. Published schema and checksums were rechecked afterward. The candidate remains available for audit; executed SQL and results are recorded in `../../results/final_build.json` (local-only).

The destination is Joel's `jteixeira_ipa` schema. Source/reference tables are read-only. The [complete email lookup](../../docs/email_lookup.md) reads all 108 published columns unchanged and adds six display/comparison fields for 114 outputs.

[Metric definitions](../../docs/metrics/README.md) · [Name inspection](../../sql/conflicting_names_debug.sql) · [State inspection](../../sql/conflicting_states_debug.sql)

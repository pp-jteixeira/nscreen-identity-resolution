# Link stability publication — October 30, 2026

`iceberg.jteixeira_ipa.pii_clean` contains **114 columns and 75,564,265 rows**. Six link-stability fields were added. All 108 previous fields, including `computed_at`, freshness dates and reference evidence, retained their per-vendor row counts and checksums. Record keys remain unique. No scoring, thresholds or row filters were added.

## Preservation and publication

The upgrade read pinned snapshot `1613450720463268051`. Its existing 108-column baseline checksums came from the completed freshness verification of that exact snapshot. This avoided rescanning an unchanged baseline. Stability used stored `observed_days`, `conflict_days` and undated counts. No raw-source or reference enrichment was rerun.

Candidate `iceberg.jteixeira_ipa.pii_clean_candidate_stability_ce669a11ba6a` passed schema, seven-vendor coverage, nonempty row-count, key uniqueness and all thirteen native integrity checks. One scan compared the existing 108 fields with the baseline and separately checksummed the six new fields together with their source/record keys. Seven vendor definitions were updated for future builds. Native plans use 102–130 fragments, below the 150-stage limit; a full raw-source rebuild was not executed.

After HDFS block-allocation failures, the candidate was written in seven vendor batches with at most eight writer tasks and one writer per task. All batches read the same pinned source snapshot. These were query-scoped settings, not cluster configuration changes.

Atomic `CREATE OR REPLACE TABLE ... AS SELECT * FROM candidate` published snapshot `8096642935433856886`. Published schema, row counts, original-field checksums and keyed stability checksums matched the candidate. The candidate remains available for inspection and recovery.

Four HDFS write failures were retried: two candidate writes and two publication copies. The canonical snapshot was checked before replacement.

## Consumers and interpretation

Existing named-column queries retain their values. Consumers expecting exactly 108 columns from `SELECT *` must accept six appended fields. The complete lookup now returns 120 outputs: all 114 stored fields plus the existing six helpers.

Shares use distinct known days and retain incomplete-date flags. Zero known-day counts are not proof that a link was absent. Undated links have NULL shares. One observed day can yield full presence, and repeated snapshots are not independent confirmation.

The complete local suite passed 70 tests. Native checks covered 29 statistics files, 17 profile templates and the expanded lookup. Full published statistics cover all seven vendors; lookup fixtures preserve all 114 fields and a real-email lookup returned 11 rows with 120 outputs. Individual identifiers and lookup values were not retained.

See [definitions and vendor statistics](../../docs/metrics/21_link_stability.md), [standalone statistics SQL](../../sql/statistics/21_link_stability.sql) and the [lookup reference](../../docs/email_lookup.md). Query results were inspected in memory; individual identifiers and result dumps were not retained.

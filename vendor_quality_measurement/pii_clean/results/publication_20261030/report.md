# Link freshness publication — October 30, 2026

`iceberg.jteixeira_ipa.pii_clean` now contains **108 columns and 75,564,265 rows**. Five link-freshness columns were added. All 103 previous fields, including `computed_at`, retained their per-vendor row counts and full-row checksums. Source-record/email-position keys remain unique. No filtering, scoring or fresh/stale thresholds were added.

## Publication and preservation

Freshness was calculated from pinned Iceberg snapshot `209958900951400330`, using evaluation day `2026-10-30`. The operation read stored vendor observations, without rerunning reference or cookie enrichment. Existing reference evidence and evaluation dates were preserved. This was an additive publication over stored records, not a new raw-source refresh.

Candidate `iceberg.jteixeira_ipa.pii_clean_candidate_freshness_34620bf38e2d` passed schema, seven-vendor coverage, nonempty row-count, unique-key and all twelve native integrity checks. Preservation includes every original column, unlike ordinary rebuild checksums that exclude query-time `computed_at`. Seven vendor definitions were updated for future builds. Their native plans use 97–121 fragments, below the 150-stage limit. A full rebuild of those raw-source views was not executed for this publication.

Two Parquet writer-close errors were retried before publication completed. The final retry reused the validated candidate and preservation results.

Atomic `CREATE OR REPLACE TABLE ... AS SELECT * FROM candidate` published snapshot `1613450720463268051`. The published schema, counts and 108-column checksums matched the validated candidate. The retained candidate supports inspection and recovery; it was not deleted.

## Interpretation and compatibility

The new dates and day counts describe retained vendor evidence. They do not verify current ownership or feed completeness. Undated vendors remain unknown; future source maxima keep both day counts null. The complete lookup reads stored freshness values and does not age them at query time.

Existing named-column queries retain their fields and values. Consumers that assume exactly 103 columns from `SELECT *` must accept the five appended fields. The complete lookup expands from 109 to 114 outputs.

See the [metric definition and vendor measurements](../../docs/metrics/20_link_freshness.md) and [standalone population SQL](../../sql/statistics/20_link_freshness.sql). Detailed executed SQL, query IDs, aggregate counts, checksums and checks are historical output, not retained: `freshness_build.json` in this directory. Synthetic Trino fixtures and vendor plans are historical output, not retained: `../link_freshness_validation_20261030.json`. No individual email or NPI values are included in this report.

## Consumer validation

All 67 local tests passed on October 30. Native validation covered 28 statistics files, 16 profile templates and the complete lookup against the candidate schema. The final exact freshness aggregation ran against both candidate and published table with identical results. The complete lookup passed native preservation fixtures for all 108 stored fields, then executed for an existing email with 114 outputs. Query metadata and aggregate results remain local-only under `../`; individual lookup values were not retained.

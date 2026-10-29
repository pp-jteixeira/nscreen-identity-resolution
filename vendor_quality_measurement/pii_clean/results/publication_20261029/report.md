# PII Clean publication — October 29, 2026

**Published and verified:** `iceberg.jteixeira_ipa.pii_clean` contains **103 columns and 75,564,265 rows**. Publication completed at 19:40:26 CET on October 29, 2026. Snapshot: `209958900951400330`.

All 23 managed views were rebuilt. The seven vendor schemas match the published schema. The candidate and published table matched every vendor’s row count and checksum across all substantive columns. Every source had zero duplicate `(source, metric_row_id)` keys.

The original 41 published columns also matched the saved baseline, excluding query-time `computed_at`. All eleven native integrity checks passed, including the five newly published metric groups. All 13 previously failing missing-column queries passed post-publication validation.

| Vendor | Metric rows |
|---|---:|
| DRDB | 1,115,415 |
| Endato | 5,427,459 |
| Haymarket | 4,223,245 |
| HealthLink | 11,156,016 |
| Medscape | 47,072,262 |
| QuantumMedica | 1,705,723 |
| RocketReach | 4,864,145 |

## Publication path and recovery

The combined 103-column vendor plan needed 721 stages against Trino’s limit of 150. Publication therefore used separate vendor inserts into a candidate table, validated the complete candidate, and atomically replaced the final table from that candidate.

The first candidate creation failed during Iceberg commit because HDFS could not allocate a manifest block. The failed candidate was not registered, and the previous published snapshot remained intact. A fresh empty candidate was created successfully; the build resumed from the saved vendor baselines. The completed candidate is retained as `iceberg.jteixeira_ipa.pii_clean_candidate_d9ae7a9257bd4344`.

Five existing enrichment-statistics queries were changed to project the 41 base record columns explicitly before computing evidence. Their previous `SELECT *` inputs would duplicate newly stored fields. Before/after schema-only checks confirmed the ambiguity errors and the fixes; post-publication checks validated the real schema. The subsequent [statistics cleanup](../../sql/statistics/README.md) replaced repeated enrichment with stored-column aggregations and fully executed all 27 statistics files.

## Scope and remaining limits

The publication verifies this full build, its stored schema, record preservation and metric invariants. It does not prove every future query will finish within the earlier audit’s 120-second limit. The complete email lookup now reads stored evidence directly. Source snapshots are not pinned during pipeline builds, so later source/reference updates can change a future publication. Lookup evidence changes when the published table changes.

## Evidence

- Final build manifest and native validation (local-only: `final_build.json`)
- Previous published attributes and checksums (local-only: `preservation.json`)
- Post-publication query checks (local-only: `post_publication_checks.json`)
- Enrichment-query compatibility checks (local-only: `query_compatibility.json`)
- Initial HDFS commit failure (local-only: `commit_failure.json`)
- Build log (local-only: `build.log`)

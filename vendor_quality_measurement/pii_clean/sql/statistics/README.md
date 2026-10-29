# Metric statistics SQL

Each numbered SQL file corresponds to the same numbered [metric page](../../docs/metrics/README.md). Run each file as one complete statement in Trino. SQL files contain no semicolons or blank lines. All statements are read-only. No result rows or execution logs are included here.

## Query provenance

- **01–07:** equivalent direct aggregations of `iceberg.jteixeira_ipa.pii_clean`. The documented October 29, 2026 tables were calculated from the saved grouped-population extraction in [grouped.sql](../../results/metric_population_20261029/grouped.sql), aggregating row counts within each vendor and outcome. The equivalents have local fixture checks and Trino-dialect syntax checks; they have not been executed against Trino. Observation quantiles use exact weighted nearest-rank median/P95, matching the documented calculation. Percentages use all metric rows in the vendor. Grouped distinct counts are never summed.
- **08–14:** statistics over the current published `iceberg.jteixeira_ipa.pii_clean` population. Queries 08–13 adapt the dated measurement queries to the current table because the historical `pii__evidence` relation is unavailable. Historical metric pages retain their dated counts and original measurement provenance. Running these files measures the current population and does not reproduce those historical baselines.
- **15–19:** original executed read-only enrichment queries over saved published records. Reference lookups and aggregations are embedded, so unpublished warehouse columns are not required. Reference snapshots remain unpinned. Cookie queries retain the October 29, 2026 evaluation date and October 22–28 window. Other queries retain the evaluation-date expressions used at execution; those expressions can evaluate differently on a later day.

Queries derived from local result artifacts contain SQL only. Queries 08–13 target the current published table and have updated provenance comments. Warehouse validation checks table and column resolution without executing the aggregations. It does not verify current counts or execution performance. Other source references remain readable requirements.

## Statement files and output sections

Each original path contains its first statement. Additional statements use the same filename stem followed by `_statement_002.sql`, `_statement_003.sql` and so on. Run the separate files in statement order.

| Metric | Statements and interpretation |
|---|---|
| 01–14 | One statement per file. Select the documented metric's output columns when a query also reports related indicators. Counts are unrounded; display percentages at the precision used in the metric page. |
| 15–16 | Coverage supplies every vendor and its conflict-row denominator. Outcomes supply classifications for vendors with conflicts; no outcome row is emitted for a zero-conflict vendor. Such vendors display zero counts with an undefined percentage. |
| 17 | Reference availability, vendor totals, status outcomes and the independent self-replacement check. Link percentages divide each status count by the vendor's distinct-link total. |
| 18 | Vendor totals, then grouped outcomes by `vendor_state_evidence` and `facility_reference_status`. Sum record counts within the documented outcome. Distinct-link outcomes can overlap across historical record states; they are not exclusive link classifications. |
| 19 | Source-date coverage, vendor totals, then grouped outcome sections. Use the `section` column to distinguish totals, cookie status, vendor-state comparison and facility-state comparison. Do not sum counts across these overlapping grouping sets. Status groups partition vendor links; historical vendor-state comparisons can overlap. |

Local result artifacts remain excluded from Git. The SQL references can be reviewed from a fresh checkout; dated result evidence still requires those local files.

# Metric statistics SQL

Each numbered SQL file corresponds to the same numbered [metric page](../../docs/metrics/README.md). Run each file as one complete statement in Trino. SQL files contain no semicolons or blank lines. All statements are read-only. No result rows or execution logs are included here.

## Query provenance

- **01–07:** equivalent direct aggregations of `iceberg.jteixeira_ipa.pii_clean`. The documented October 29, 2026 tables were calculated from the saved grouped-population extraction in [grouped.sql](../../results/metric_population_20261029/grouped.sql), aggregating row counts within each vendor and outcome. All seven equivalent queries passed live Trino execution on October 29, 2026 in the [SQL audit](../../results/sql_audit_20261029/report.md). Observation quantiles use exact weighted nearest-rank median/P95, matching the documented calculation. Percentages use all metric rows in the vendor. Grouped distinct counts are never summed.
- **08–14:** statistics over the current published `iceberg.jteixeira_ipa.pii_clean` population. Queries 08–13 were re-executed on October 29, 2026 and their metric-page counts, percentages and provenance were refreshed together. Snapshot `6346435822181920647` remained unchanged throughout those six queries. Query 14 also passed the live SQL audit; its page retains its stated extraction time.
- **15–19:** population statistics aggregate published evidence directly from `iceberg.jteixeira_ipa.pii_clean`. Facility/specialty coverage uses the stored arrays. Lifecycle, facility-state and cookie outcomes use stored classifications. Cookie coverage reports each distinct stored window and source-availability combination, including window start/end. Reference joins and cookie-history scans are not repeated. The two raw NPPES diagnostics (`17_npi_registry_status.sql` and `_statement_004.sql`) remain independent checks of the current reference, which may differ from the publication snapshot.
- **20:** link freshness over stored dates and day counts. Each source/email/NPI link contributes once to the distribution. Latest-day percentages use known-lag links; undated percentages use all links. p50 and p95 use exact nearest-rank percentiles over day-count buckets. Stored evaluation dates make source ages reproducible.

Queries contain SQL only. The [initial October 29 SQL audit](../../results/sql_audit_20261029/report.md) checked the earlier query versions. Its cookie-outcome query recomputed reference evidence and exceeded the 120-second limit. The current version aggregates stored cookie evidence. Queries 08–13 additionally ran without an output limit for the metric-page refresh. Documented metric tables remain dated measurements, not automatically refreshed results. Current output can differ after a new publication; raw NPPES diagnostics can change independently.

All **27 statistics files present on October 29** passed native Trino semantic validation and full execution on October 29, 2026, with no output limit. The published snapshot stayed unchanged throughout the checks. All five evidence-group denominators matched seven vendors and 75,564,265 metric rows; the facility-state and cookie invariant aggregations returned zero failures. The stored cookie-outcome aggregation completed in 37.2 seconds. Executed SQL, hashes, query IDs, aggregate results and snapshot checks are retained locally in `../../results/statistics_validation_20261029.json` (excluded from Git).

There are now 28 statistics files. On October 30, native schema validation passed all 28 against the 108-column candidate, and the final exact freshness query ran without a row limit on the published table. Its seven vendor rows matched the candidate exactly, including nearest-rank percentiles. Evidence is local-only: `../../results/freshness_candidate_queries_20261030.json`, `../../results/link_freshness_exact_candidate_20261030.json` and `../../results/link_freshness_published_statistics_20261030.json`.

## Statement files and output sections

Each original path contains its first statement. Additional statements use the same filename stem followed by `_statement_002.sql`, `_statement_003.sql` and so on. Run the separate files in statement order.

| Metric | Statements and interpretation |
|---|---|
| 01–14 | One statement per file. Select the documented metric's output columns when a query also reports related indicators. Counts are unrounded; display percentages at the precision used in the metric page. |
| 15–16 | Coverage supplies every vendor and its conflict-row denominator. Outcomes supply classifications for vendors with conflicts; no outcome row is emitted for a zero-conflict vendor. Such vendors display zero counts with an undefined percentage. |
| 17 | Reference availability, vendor totals, status outcomes and the independent self-replacement check. Link percentages divide each status count by the vendor's distinct-link total. |
| 18 | Vendor totals, then grouped outcomes by `vendor_state_evidence` and `facility_reference_status`. Sum record counts within the documented outcome. Distinct-link outcomes can overlap across historical record states; they are not exclusive link classifications. |
| 19 | Stored window and source-date coverage, vendor totals, then grouped outcome sections. Use the `section` column to distinguish totals, cookie status, vendor-state comparison and facility-state comparison. Do not sum counts across these overlapping grouping sets. Status groups partition vendor links; historical vendor-state comparisons can overlap. |
| 20 | One statement with per-vendor row/link counts, dated and undated links, source age, latest-day links and exact nearest-rank lag percentiles. Unknown lags are excluded from percentile and latest-day denominators. |

Local result artifacts remain excluded from Git. The SQL references can be reviewed from a fresh checkout; dated result evidence still requires those local files.

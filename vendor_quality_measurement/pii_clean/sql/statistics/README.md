# Metric statistics SQL

The current metric pages use **32 read-only population queries**, executed in native Trino on **October 31, 2026**, against `iceberg.jteixeira_ipa.pii_clean FOR VERSION AS OF 8811920360682490090`. This complete publication contains **75,656,369 records across seven sources**. Each query is pinned to the same snapshot. Execution leaves stored metrics and evaluation dates unchanged.

The directory has 35 SQL files: the 32 current publication queries, two independent raw NPPES diagnostics, and one explicitly dated partial-population query. Only SQL source is retained. No result exports or execution logs are stored.

## Counting units

| Metric | Unit and denominator |
|---|---|
| 01 | Exact source-record/email-position counts. Repeated means more than one observation. Median/P95 use exact weighted nearest-rank quantiles. |
| 02–07 | Record outcomes divided by all metric records within each source. Unknown name evidence remains separate from disagreement. |
| 08 | Distinct source/emails for multiplicity percentages; metric records for affected-record percentages. |
| 09–10 | Distinct source/emails for history/conflict prevalence; record counts have their own denominators. |
| 11 | Distinct source/emails for normalized-name counts. Spellings are not people. |
| 12 | Distinct source/email/NPI links for conflicting and unknown link outcomes. |
| 13–16 | Established conflict records for shared/disjoint/unknown percentages. Evidence coverage uses all metric records. Zero-conflict percentages are undefined. |
| 17 | Published lifecycle outcomes by record, link and NPI. The metric page displays record percentages; overlapping distinct counts must not be summed. |
| 18 | Vendor/facility evidence groups partition records. Distinct-link groups can overlap across historical records. |
| 19 | Location-status groups partition source/email/NPI links. Vendor/facility comparison groups are separate and can overlap at link grain. Window checks use stored `cookie_location_window_days`. |
| 20 | Distinct source/email/NPI links. Latest-day percentages and exact lag quantiles exclude unknown lags. |
| 21 | Dated source/email/NPI links for presence/overlap percentages. Unknown and one-day histories stay visible. |
| 22 | Distinct source/NPIs and metric records are separate units. Structure, entity type and entity reason are separate distributions. |
| 23–24 | All records for usable-label coverage; established conflict records for label-agreement outcomes. |
| 25 | Distinct source/emails. Swap and flip-back percentages use emails with dated history. |
| 26 | Distinct Medscape GUID/email/NPI/status combinations, independently of raw record multiplicity. |

## Statement files

Additional statements use `_statement_002.sql`, `_statement_003.sql` and so on. Run each file as one complete statement. SQL files contain no semicolons or blank lines.

- **15–16:** the first query gives all-source coverage. Statement 002 gives conflict outcomes; sources without conflicts have no outcome row and require a zero count with an undefined percentage.
- **17:** statements 002 and 003 query the published population. `17_npi_registry_status.sql` and statement 004 instead inspect the current raw NPPES reference. Those two diagnostic queries were not rerun for this refresh and are not the source of current page statistics.
- **18:** the first query supplies denominators; statement 002 supplies evidence outcomes and invariant failures.
- **19:** the first query supplies the stored window; statement 002 supplies denominators; statement 003 supplies location, vendor-state and facility-state groups. Never sum across overlapping `section` values. Its corrected checks passed with the three-day window and explicit missing-source days.
- **25:** `25_sequential_history.sql` uses the complete publication. `25_sequential_history_partial_20261030.sql` preserves the older six-source snapshot for historical reproduction only.

The current NPPES specialty flag is `conflicting_npis_share_nppes_specialty`. Current statistics and examples use that name. Calculation macros define indicators; these queries measure stored outcomes. See the [metric pages](../../docs/metrics/README.md) for executed examples, tables and interpretation.

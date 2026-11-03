# Metric statistics SQL

The metric pages use **read-only population queries** against the current tables in `iceberg.jteixeira_ipa`: `pii_clean` for published metrics and `pii__int_pii__metrics` for stored name-match classes. Execution leaves stored metrics and evaluation dates unchanged. Only SQL source is retained. No result exports or execution logs are stored.

The directory holds one or more queries per metric page, plus two independent raw NPPES diagnostics for metric 17.

## Counting units

Every row of `pii_clean` is one source/email/NPI link.

| Metric | Unit and denominator |
|---|---|
| 01 | Link counts. Repeated means more than one observation. Median/P95 use exact weighted nearest-rank quantiles. |
| 02–07 | Link outcomes divided by all links within each source. Unknown name evidence remains separate from disagreement. Name-match classes can overlap within a link and must not be summed as disjoint outcomes. |
| 08 | Distinct source/emails for multiplicity percentages; links for affected-link percentages. |
| 09–10 | Distinct source/emails for history/conflict prevalence; link counts have their own denominators. |
| 11 | Distinct source/emails for normalized-name counts. Spellings are not people. |
| 12 | Links for conflicting and unknown link outcomes. |
| 13–16 | Links with an established conflict for shared/disjoint/unknown percentages. Evidence coverage uses all links. Zero-conflict percentages are undefined. |
| 17 | Published lifecycle outcomes by link and NPI. The metric page displays link percentages; overlapping distinct counts must not be summed. |
| 18 | Vendor/facility evidence groups partition links. |
| 19 | Location-status groups partition links. Vendor/facility comparison groups are separate and can overlap. Window checks use stored `cookie_location_window_days`. |
| 20 | Links. Latest-day percentages and exact lag quantiles exclude unknown lags. |
| 21 | Dated links for presence/overlap percentages. Unknown and one-day histories stay visible. |
| 22 | Distinct source/NPIs and links are separate units. Structure, entity type and entity reason are separate distributions. |
| 23–24 | All links for usable-label coverage; links with an established conflict for label-agreement outcomes. |
| 25 | Distinct source/emails. Swap and flip-back percentages use emails with dated history. |
| 26 | Distinct Medscape GUID/email/NPI/status combinations. |
| 27 | Links partitioned by claims-association support. Corroboration compares links with a usable facility state and a known vendor state. |
| 28 | Links within source and domain class. Domain aggregates are recomputed from published links with the stored macro. |

## Statement files

Additional statements use `_statement_002.sql`, `_statement_003.sql` and so on. Run each file as one complete statement. SQL files contain no semicolons or blank lines.

- **01:** statement 002 reports versions merged per link and links without a single latest version.
- **05 and 07 (vendor name):** statement 002 compares the any-version and latest-version indicator.
- **07:** `07_name_match_classes.sql` measures stored name explanations in the core table. Class counts use links as their denominator and can overlap.
- **15–16:** the first query gives all-source coverage. Statement 002 gives conflict outcomes; sources without conflicts have no outcome row and require a zero count with an undefined percentage.
- **17:** statements 002 and 003 query the published population. `17_npi_registry_status.sql` and statement 004 inspect the current raw NPPES reference.
- **18:** the first query supplies denominators; statement 002 supplies evidence outcomes and invariant failures; statement 003 lists links whose any-version and latest-version evidence differ.
- **27:** the first query partitions links by claims support; statement 002 compares corroboration with and without Claims.
- **28:** one statement recomputes the domain aggregates from published links and groups them by source and domain class.
- **29:** one statement counts links by source with another source agreeing or disagreeing on the NPI, from the published email and NPI.
- **19:** the first query supplies the stored window; statement 002 supplies denominators; statement 003 supplies location, vendor-state and facility-state groups. Never sum across overlapping `section` values. Statement 004 lists links whose any-version and latest-version cookie vendor-state evidence differ.

Calculation macros define indicators; these queries measure stored outcomes. See the [metric pages](../../docs/metrics/README.md) for definitions and interpretation.

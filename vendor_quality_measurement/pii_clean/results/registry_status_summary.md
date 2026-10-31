# NPI lifecycle-status measurement

**Historical checkpoint — October 29, 2026.** The population counts and validation results below describe that earlier build. Current publication statistics and executed examples are in [metric 17](../docs/metrics/17_npi_registry_status.md), refreshed October 31 against snapshot `8811920360682490090`. Original result dumps are not retained. See [current build validation](../docs/build_recovery.md).

Input: all 75,564,265 saved source-record/email-position rows and 26,730,605 distinct source/email/NPI links in `iceberg.jteixeira_ipa.pii_clean`. Executed queries and results (historical output, not retained: `registry_status_measure.json`) identify the Iceberg input snapshot and confirm it stayed unchanged during measurement. Current NPPES is not pinned and does not reconstruct historical vendor-day activity. Evaluation uses Europe/Paris current date.

## Findings and reference evidence

Raw `iceberg.npi.nppes_npidata_latest` contains 9,551,447 records for 9,551,447 distinct NPIs. Deactivation dates occur on 361,585 rows (3.79% of reference rows), reactivation dates on 18,267 (0.19%), and replacement values on 82 (0.00086%). Every nonblank lifecycle date parses successfully. Missing date values remain absent; deactivation and reactivation counts overlap.

Independent replacement checks (historical output, not retained: `registry_status_replacement_check.json`) found 82/82 replacement values (100%) equal their own NPI. They remain unknown with reason `self_replacement`, and never redirect a link. The cause of those upstream values has not been established. A further 142 reference NPIs (0.00149% of reference NPIs) have equal deactivation/reactivation dates; their intraday order is unknown.

Reference classifications are current evidence labels. `active_as_reported` means no lifecycle event or replacement is reported; it is not independent confirmation of activity. A later deactivation overrides an earlier reactivation. A later reactivation overrides an earlier deactivation. Equal dates, malformed/future dates, conflicting lifecycle tuples and inconsistent replacement evidence remain unknown. No row is dropped.

## Per-vendor status counts

Counting unit: distinct email–NPI links within each vendor. Percentages use all distinct links in that vendor. Status groups partition these links; source identities are never pooled. Tiny nonzero percentages retain additional precision.

| Vendor | Distinct links | Active as reported, n (%) | Deactivated, n (%) | Reactivated, n (%) | Replaced, n (%) | Not found, n (%) | Unknown, n (%) |
|---|---:|---:|---:|---:|---:|---:|---:|
| HealthLink | 7,688,451 | 7,654,195 (99.55%) | 9,938 (0.13%) | 20,557 (0.27%) | 0 (0.00%) | 3,415 (0.04%) | 346 (0.00450%) |
| QuantumMedica | 1,705,723 | 1,692,741 (99.24%) | 8,083 (0.47%) | 4,805 (0.28%) | 0 (0.00%) | 8 (0.00047%) | 86 (0.00504%) |
| Medscape | 3,659,306 | 3,518,043 (96.14%) | 117,978 (3.22%) | 8,226 (0.22%) | 0 (0.00%) | 14,900 (0.41%) | 159 (0.00435%) |
| Endato | 5,427,459 | 5,227,039 (96.31%) | 189,378 (3.49%) | 10,773 (0.20%) | 0 (0.00%) | 10 (0.00018%) | 259 (0.00477%) |
| RocketReach | 3,199,535 | 3,118,525 (97.47%) | 73,265 (2.29%) | 7,560 (0.24%) | 0 (0.00%) | 14 (0.00044%) | 171 (0.00534%) |
| DRDB | 826,886 | 782,108 (94.58%) | 42,214 (5.11%) | 2,512 (0.30%) | 0 (0.00%) | 5 (0.00060%) | 47 (0.00568%) |
| Haymarket | 4,223,245 | 4,030,766 (95.44%) | 176,950 (4.19%) | 9,062 (0.21%) | 0 (0.00%) | 6,286 (0.15%) | 181 (0.00429%) |

Across all 26,730,605 distinct source/email/NPI links: 26,023,417 (97.35%) active_as_reported, 617,806 (2.31%) deactivated, 63,495 (0.24%) reactivated, 0 (0.00%) replaced, 24,638 (0.09%) not_found, 1,249 (0.00467%) unknown. These totals include repeated email/NPI pairs reported by different vendors, distinguished by source.

## Unknown outcomes and missing references

There are 1,249 unknown source/email/NPI links (0.00467% of all links). All come from same-day event ambiguity or self-replacement evidence. A separate 24,638 links (0.09% of all links) have no NPPES match and are labelled not_found. This is not proof that those provider identifiers are invalid. The existing `registry_npi_present` flag uses the separate registry-name reference and is not overwritten.

## Output columns

These eleven columns are appended to every vendor model and the final UNION ALL output. They were published on October 29, 2026, with all native integrity checks passing.

| Column | Meaning |
|---|---|
| `npi_registry_status` | One of active_as_reported, deactivated, reactivated, replaced, not_found or unknown. |
| `npi_registry_status_reason` | Classification or uncertainty reason; never null. |
| `npi_registry_replacement_npi` | Agreed ten-digit nonzero nonself replacement, if present. Checksum, destination presence and replacement chains are not validated. Retained even when other evidence makes status unknown. |
| `npi_registry_deactivation_date`, `npi_registry_reactivation_date` | Parsed dates from a single agreed lifecycle tuple. Null for absent/invalid dates or conflicting tuples. |
| `npi_registry_reference_row_count` | All readable NPPES rows matched by NPI, including duplicates; zero when unmatched. |
| `npi_registry_variant_count` | Distinct tuples after trimming and blank-to-null normalization. More than one makes status unknown. |
| `npi_registry_lifecycle_evidence` | Distinct original deactivation/reactivation strings, replacement strings and reason codes. Nullable row fields retain unknowns; no-match arrays are empty. |
| `npi_registry_status_as_of_day` | Evaluation date used to reject future events; defaults to Europe/Paris today. The `registry_status_as_of_day` variable fixes comparisons for reproducibility, without restoring historical registry versions. |
| `npi_registry_reference_table` | `iceberg.npi.nppes_npidata_latest`. |
| `npi_registry_definition_version` | `nppes_lifecycle_consensus_v1`. |

## Saved examples

Deterministic truncated sample: up to two metric-row IDs per vendor/status, ordered by metric-row ID. Full source/NPI keys, raw lifecycle values, parsed dates and uncertainty reasons are preserved in executed results. This is diagnostic selection, not a prevalence estimate.

| Vendor | NPI | Status | Reason | Deactivation | Reactivation |
|---|---|---|---|---|---|
| HealthLink | `1114013067` | deactivated | latest_event_deactivation | 2026-02-26 | Missing |
| HealthLink | `1083543078` | not_found | no_nppes_record | Missing | Missing |
| HealthLink | `1659338051` | reactivated | latest_event_reactivation | 2007-07-17 | 2007-08-21 |
| HealthLink | `1013697606` | unknown | ambiguous_event_order | 2024-02-21 | 2024-02-21 |
| Medscape | `1235680307` | deactivated | latest_event_deactivation | 2016-11-17 | Missing |
| Medscape | `12345` | not_found | no_nppes_record | Missing | Missing |
| Medscape | `1952841165` | reactivated | latest_event_reactivation | 2022-02-11 | 2022-08-18 |
| Medscape | `1366687469` | unknown | self_replacement | 2008-11-20 | 2008-12-04 |

## Validation and operational status

- Lifecycle-validation checkpoint: 52 local tests passed, including lifecycle chronology, malformed/future/equal dates, invalid/self replacements, conflicting reference tuples, missing references, duplicate input rows and schema consistency across all vendors.
- Native Trino: 20 synthetic metric rows passed expected statuses and reasons; native invariants returned no failures.
- Population measurement retained all 75,564,265 metric rows with unique source/metric-row keys. Outcome groups also partitioned all 26,730,605 distinct source/email/NPI links. Invariant checks returned no failures. This is not a full source rebuild or before/after original-attribute checksum comparison.
- At the lifecycle-validation checkpoint, all seven vendor query plans (historical output, not retained: `registry_status_plans.json`) passed. Read-only EXPLAIN validation also checked the then-current published-column email lookup without fetching email results. The complete lookup has separate validation linked below.
- Lifecycle evidence is appended after relationship metrics and does not alter their calculations. These historical measurements were read-only. The subsequent full publication (historical report not retained) published all five groups: facility, specialty, lifecycle, vendor/facility state and cookie location. Original published values were preserved, excluding query-time `computed_at`. The [complete email lookup](../docs/email_lookup.md) now reads published evidence directly. The earlier enrichment-based lookup passed the saved 58-test checkpoint plus native synthetic validation.

[Definition](../docs/metrics/17_npi_registry_status.md) · [Calculation SQL](../macros/registry_status.sql) · Native fixtures (historical output, not retained: `registry_status_native.json`) · Local test output (historical output, not retained: `registry_status_local_tests.txt`)

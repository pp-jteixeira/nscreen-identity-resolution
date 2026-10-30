# Facility-overlap measurement

**Status:** the dated measurements below were performed read-only. Their metric columns were subsequently published and validated in the full October 29, 2026 build. [Publication report](publication_20261029/report.md). Original measurement snapshots, counts and extraction times remain the provenance for these statistics.

Measured October 29, 2026 using the saved `iceberg.jteixeira_ipa.pii_clean` snapshot recorded in executed queries and results (historical output, not retained: `conflicting_facilities_measure.json`). Reference: `bq_bi.analytics_prod.npi_facility_association`, all ranks, trimmed `provider_npi` and distinct ten-digit nonzero `facility_npis`. Source snapshots are not pinned; the reference has no activity dates.

The saved table contains 75,564,265 exact-record/email-position rows and 26,730,605 distinct source/email/NPI links. Facility lookup has 1,309,617 provider NPIs; 1,309,617 (100%) have usable facility IDs. This reference coverage does not describe vendor-population coverage.

## Reference coverage

Percentages use all distinct email–NPI links within each vendor. Missing means no usable retained facility IDs, not evidence of no workplace.

| Vendor | Distinct links | Usable facility evidence, n (%) | Missing evidence, n (%) |
|---|---:|---:|---:|
| HealthLink | 7,688,451 | 2,818,777 (36.66%) | 4,869,674 (63.34%) |
| QuantumMedica | 1,705,723 | 784,100 (45.97%) | 921,623 (54.03%) |
| Medscape | 3,659,306 | 1,293,150 (35.34%) | 2,366,156 (64.66%) |
| Endato | 5,427,459 | 1,649,541 (30.39%) | 3,777,918 (69.61%) |
| RocketReach | 3,199,535 | 1,214,950 (37.97%) | 1,984,585 (62.03%) |
| DRDB | 826,886 | 297,758 (36.01%) | 529,128 (63.99%) |
| Haymarket | 4,223,245 | 1,775,580 (42.04%) | 2,447,665 (57.96%) |

## Conflict outcomes at link grain

Percentages use distinct links with an established conflict within each vendor. One link can have different outcomes on different exact records/dates, so these outcome columns can overlap. They are not mutually exclusive link classifications. Record-level outcomes in the [metric definition](../docs/metrics/15_conflicting_npis_share_facility.md) partition conflict rows.

| Vendor | Conflict links | Shared facility, n (%) | Disjoint retained IDs, n (%) | Unknown comparison, n (%) |
|---|---:|---:|---:|---:|
| HealthLink | 0 | 0 (—) | 0 (—) | 0 (—) |
| QuantumMedica | 56 | 0 (0.00%) | 10 (17.86%) | 46 (82.14%) |
| Medscape | 32 | 0 (0.00%) | 12 (37.50%) | 20 (62.50%) |
| Endato | 194,982 | 2,347 (1.20%) | 19,181 (9.84%) | 173,454 (88.96%) |
| RocketReach | 65,846 | 3,925 (5.96%) | 7,688 (11.68%) | 54,233 (82.36%) |
| DRDB | 14,832 | 156 (1.05%) | 1,868 (12.59%) | 12,808 (86.35%) |
| Haymarket | 0 | 0 (—) | 0 (—) | 0 (—) |

Across 313,775 conflict rows, 8,580 (2.73%) share facility IDs, 34,353 (10.95%) have known disjoint retained sets, and 270,842 (86.32%) remain unknown. Counts describe evidence, not ownership accuracy.

## Saved examples

Deterministic, truncated examples: the first two metric-row IDs per vendor/outcome were retained. This is diagnostic selection, not a prevalence sample. Full original email/NPI keys, exact dates, peer IDs and comparison arrays remain in the machine-readable results. The examples below omit email text.

| Vendor | Record NPI | Peer NPI | Shared facility NPIs |
|---|---|---|---|
| DRDB | `1770558413` | `1649275785` | `1427232818` |
| Endato | `1326022708` | `1568494094` | `1821250762` |
| RocketReach | `1417959628` | `1205151032` | `1063441293`, `1467195073`, `1881054997`, `1881619344`, `1982629440`, `1992733513` |

These examples use undated vendor conflict contexts; shared IDs do not establish that both providers attended a facility together. Associations combine Claims, CMS, HealthLink and NPPES support. HealthLink therefore is not an independent reference source. No state matching or geographical proximity is used.

## Validation and publication

- Facility-validation checkpoint: 43 local tests passed, including duplicate-reference handling, missing evidence, exact-day gaps, undated DRDB feeds, all-vendor schemas and publication failure cases.
- Native Trino: 26 synthetic record outcomes checked; the independent relational check returned no failures.
- Full read-only conflict evaluation: all 313,775 conflict rows retained unique metric-row keys. Independent peer/null/intersection checks returned no failures. Published records were inputs only during that measurement. The subsequent full publication verified original-attribute preservation.
- The saved facility-era combined query plan exceeded Trino’s 150-stage limit at 170 stages. This is a historical plan, not a stage count for the current models. The local runner has a candidate-batch fallback with tests for write, integrity, preservation and unrelated-planning failures. The subsequent October 29 publication verified vendor batching in the warehouse.
- The [full publication](publication_20261029/report.md) published all five added metric groups and passed preservation and integrity checks. The current runner materializes vendor outputs once, validates the stored candidate before replacement, and compares published checksums against that candidate. Its optimized flow has local regression coverage; a full warehouse rebuild using that flow has not yet run. The [complete email lookup](../docs/email_lookup.md) reads published evidence directly. The earlier enrichment-based lookup validation checkpoint (historical output, not retained: `email_lookup_full_local_tests.txt`) passed 58 tests.

Native evidence (historical output, not retained: `conflicting_facilities_native.json`) · Local test output (historical output, not retained: `conflicting_facilities_local_tests.txt`) · Per-vendor planning (historical output, not retained: `conflicting_facilities_candidate_plan.json`) · [Publication implementation](../tools/pipeline.py)

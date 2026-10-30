# Specialty-overlap measurement

**Status:** the dated measurements below were performed read-only. Their metric columns were subsequently published and validated in the full October 29, 2026 build. [Publication report](publication_20261029/report.md). Original measurement snapshots, counts and extraction times remain the provenance for these statistics.

Measured October 29, 2026. Executed queries and results (historical output, not retained: `conflicting_specialties_measure.json`) record the final-table snapshot and extraction times. Inputs: `iceberg.jteixeira_ipa.pii_clean`, `iceberg.npi.nppes_npidata_latest`, and `iceberg.npi.npi_taxonomy`. Vendor history is the full saved population; the current taxonomy reference has no vendor-day alignment. Source references are not pinned.

The input contains 75,564,265 source-record/email-position rows and 26,730,605 distinct source/email/NPI links. The recognized-code lookup contains 9,208,126 distinct NPIs, each with at least one dictionary-recognized code, and at most fifteen distinct codes per provider. This is the recognized subset, not all NPPES providers; it does not imply complete registry coverage.

## Reference coverage

Coverage percentages use all distinct email–NPI links within each vendor. Missing means no recognized codes joined for that NPI; missing provider records and unrecognized-only code sets remain unknown.

| Vendor | Distinct links | Recognized codes, n (%) | Missing evidence, n (%) |
|---|---:|---:|---:|
| HealthLink | 7,688,451 | 7,675,098 (99.83%) | 13,353 (0.17%) |
| QuantumMedica | 1,705,723 | 1,697,632 (99.53%) | 8,091 (0.47%) |
| Medscape | 3,659,306 | 3,526,428 (96.37%) | 132,878 (3.63%) |
| Endato | 5,427,459 | 5,238,071 (96.51%) | 189,388 (3.49%) |
| RocketReach | 3,199,535 | 3,126,256 (97.71%) | 73,279 (2.29%) |
| DRDB | 826,886 | 784,667 (94.89%) | 42,219 (5.11%) |
| Haymarket | 4,223,245 | 4,040,009 (95.66%) | 183,236 (4.34%) |

## Conflict outcomes at link grain

Percentages use links with established conflict within each vendor. A link can have different peer contexts on different dates; outcome columns may overlap. Record-level outcomes in the [metric definition](../docs/metrics/16_conflicting_npis_share_specialty.md) partition conflict rows.

| Vendor | Conflict links | Shared code, n (%) | Disjoint codes, n (%) | Unknown, n (%) |
|---|---:|---:|---:|---:|
| HealthLink | 0 | 0 (—) | 0 (—) | 0 (—) |
| QuantumMedica | 56 | 8 (14.29%) | 48 (85.71%) | 0 (0.00%) |
| Medscape | 32 | 6 (18.75%) | 22 (68.75%) | 4 (12.50%) |
| Endato | 194,982 | 21,991 (11.28%) | 157,786 (80.92%) | 15,205 (7.80%) |
| RocketReach | 65,846 | 10,521 (15.98%) | 50,906 (77.31%) | 4,419 (6.71%) |
| DRDB | 14,832 | 1,292 (8.71%) | 11,699 (78.88%) | 1,841 (12.41%) |
| Haymarket | 0 | 0 (—) | 0 (—) | 0 (—) |

Of 313,775 conflict rows, 40,029 (12.76%) share recognized taxonomy codes, 249,457 (79.50%) have known disjoint retained code sets, and 24,289 (7.74%) remain unknown. This measures reference-code overlap, not attribution accuracy.

## Saved examples

Deterministic truncated selection: up to two metric-row IDs per vendor and outcome. This is diagnostic selection, not a prevalence sample. Executed results preserve original email/NPI keys, exact dates, peer code sets and shared codes. The table below omits email text.

| Vendor | Record NPI | Peer NPI | Shared taxonomy codes |
|---|---|---|---|
| DRDB | `1730161308` | `1730179607` | `207P00000X` |
| Endato | `1245423425` | `1073729463` | `208000000X` |
| Medscape | `1083664023` | `1548262900` | `207RH0003X`, `207RX0202X` |
| QuantumMedica | `1164417721` | `1942697610` | `207RC0000X` |
| RocketReach | `1699928200` | `1023212693` | `207L00000X` |

All fifteen NPPES slots contribute equally. Exact code equality does not generalize through taxonomy classification labels. Missing evidence stays unknown; provider names, vendor specialty labels and broad profession are not fallback codes.

## Validation

- Specialty-validation checkpoint: 49 local tests passed. Cases include slot-15 matching, dictionary rejection, duplicate provider/dictionary rows, empty codes, exact dates and gaps, undated DRDB feeds, all-vendor schema consistency, nullable peer aggregation and debug output.
- Native Trino: 26 synthetic record outcomes passed; independent relational checks returned no failures.
- Full conflict evaluation retained all 313,775 unique metric-row keys. Independent peer, null, date-subset and intersection checks returned no failures.
- Enrichment of saved rows is read-only. Existing rows are retained as inputs; a full source rebuild, publication and before/after checksums have not executed.
- Vendor query plans (historical output, not retained: `conflicting_specialties_plans.json`) validate the rendered local models. Existing vendor batching remains the publication approach for queries exceeding the combined stage limit.

[Metric definition](../docs/metrics/16_conflicting_npis_share_specialty.md) · Local test output (historical output, not retained: `conflicting_specialties_local_tests.txt`) · Native evidence (historical output, not retained: `conflicting_specialties_native.json`)

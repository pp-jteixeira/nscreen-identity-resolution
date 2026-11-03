# Facility claims support

**Status:** implemented, stored and measured.

**Principle:** `facility_primary_state` is only as strong as the evidence behind the NPI's preferred facility. This metric publishes the claim count and the data sources behind that rank-1 association, so a state backed by claims can be told apart from one backed by directory listings alone.

**Where to find it:** `facility_claim_count`, `facility_sources`, `facility_claims_backed`, `facility_claims_reference_table` and `facility_claims_definition_version` in `iceberg.jteixeira_ipa.pii__int_<vendor>__metrics`, `pii__int_pii__metrics` and `iceberg.jteixeira_ipa.pii_clean`. One row per source/email/NPI link; key: `source`, `link_id`. The values belong to the link's NPI, so every link of an NPI carries the same values. Input: `bq_bi.analytics_prod.npi_facility_association`, rank-1 rows (`_rank = 1`), columns `provider_npi`, `claim_count` and `sources`.

## How it is computed

Rank-1 rows are grouped by trimmed `provider_npi`. The reference holds one rank-1 row per NPI, and the grouping also guards against duplicates.

```sql
max(claim_count) AS facility_claim_count,
contains(facility_sources, 'Claims') AS facility_claims_backed
```

`facility_sources` is the sorted set of labels in the comma-separated `sources` text: `Claims`, `CMS`, `Healthlink` and `NPPES`. An NPI without a rank-1 row has an empty array, a null count and a null flag. A rank-1 row whose sources exclude `Claims` has a false flag and no claim count. No threshold or score is applied.

The comparison of vendor states with the facility state stays on [page 18](18_vendor_facility_state.md). This page only describes how well supported that facility state is. The implementation is `facility_claims_lookup` in [location_evidence.sql](../../macros/location_evidence.sql).

## Real examples: contrasting outcomes

Executed November 3, 2026 against `iceberg.jteixeira_ipa.pii_clean` (snapshot `985110448175465479`), reading the stored claims columns. These selected cases explain outcomes; they do not measure prevalence.

| source | link_id | npi | facility_claim_count | facility_sources | facility_primary_state | vendor_state_evidence | What it shows |
|---|---|---|---:|---|---|---|---|
| healthlink | 000003E1464D72618D55F78C6D464B854F2B8213906F0546468EE5C189A1376A | 1720286941 | 20 | Claims | TX | corroborated | Claims-only support |
| healthlink | 00000FDBBE490B347739EDAB8535DCBD459D3F7F6A8BC9B12EC70D466FD2978C | 1306880141 | 6 | CMS, Claims | IL | not_corroborated | Few claims, and the vendor state disagrees |
| healthlink | 000038073F44B2FAC31A34449E5F84522BB8D460D10F7C93E93AB23DB5B7E87E | 1457434912 | null | CMS, NPPES | PA | corroborated | A state from directories only |
| healthlink | 000009F089C4DBC8CE55C0EC5FDFAE178C0984C864E9A8B6EE61656DEADEF74F | 1356332324 | null | empty | null | unknown_facility | No rank-1 association at all |

## Statistics by source

Measured **November 3, 2026** from `iceberg.jteixeira_ipa.pii_clean` snapshot `985110448175465479`, reading the stored claims columns. These are exact population counts, not a sample. Source data periods are those of [page 18](18_vendor_facility_state.md). Percentages use all links of the source and the first three outcome columns partition them. The claim buckets (1–9, 10–99, 100 or more) are descriptive labels, not quality thresholds.

[Statistics SQL 1](../../sql/statistics/27_facility_claims_support.sql) · [Statistics SQL 2](../../sql/statistics/27_facility_claims_support_statement_002.sql)

| Source | Links | No rank-1 row, n (%) | Claims-backed, n (%) | Rank-1 row without Claims, n (%) | 1–9 claims, n (%) | 10–99 claims, n (%) | 100+ claims, n (%) | Median claims (approximate) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| HealthLink | 7,688,451 | 4,858,932 (63.20%) | 2,677,755 (34.83%) | 151,764 (1.97%) | 479,243 (6.23%) | 997,050 (12.97%) | 1,201,462 (15.63%) | 71 |
| QuantumMedica | 1,705,723 | 919,475 (53.91%) | 744,300 (43.64%) | 41,948 (2.46%) | 131,766 (7.72%) | 268,222 (15.72%) | 344,312 (20.19%) | 78 |
| Medscape | 3,662,055 | 2,364,492 (64.57%) | 1,226,914 (33.50%) | 70,649 (1.93%) | 217,059 (5.93%) | 453,474 (12.38%) | 556,381 (15.19%) | 73 |
| Endato | 5,427,459 | 3,773,333 (69.52%) | 1,571,184 (28.95%) | 82,942 (1.53%) | 262,352 (4.83%) | 569,590 (10.49%) | 739,242 (13.62%) | 83 |
| RocketReach | 3,199,535 | 1,981,580 (61.93%) | 1,156,531 (36.15%) | 61,424 (1.92%) | 195,076 (6.10%) | 414,644 (12.96%) | 546,811 (17.09%) | 84 |
| DRDB | 826,886 | 528,539 (63.92%) | 283,670 (34.31%) | 14,677 (1.77%) | 46,531 (5.63%) | 104,806 (12.67%) | 132,333 (16.00%) | 81 |
| Haymarket | 4,223,245 | 2,443,956 (57.87%) | 1,680,640 (39.79%) | 98,649 (2.34%) | 298,886 (7.08%) | 618,499 (14.65%) | 763,255 (18.07%) | 74 |

Among links with a usable facility state and a known vendor state (statement 2), the corroborated share by support:

| Source | Links without Claims | Corroborated | Links with Claims | Corroborated |
|---|---:|---:|---:|---:|
| HealthLink | 149,542 | 98.1% | 2,609,421 | 90.3% |
| Medscape | 67,614 | 68.1% | 1,178,065 | 63.6% |
| Endato | 82,918 | 41.1% | 1,570,726 | 42.3% |
| RocketReach | 53,892 | 93.5% | 996,070 | 85.1% |
| DRDB | 14,670 | 91.4% | 283,523 | 87.5% |

QuantumMedica and Haymarket have no recognized vendor states and are absent from the second table.

**Interpretation:** Claims back about 95% of the rank-1 associations that exist, but 54% to 70% of links have no association, so most links still lack a facility state to compare against. Corroboration is not higher when claims stand behind the state. HealthLink, Medscape, RocketReach and DRDB agree more often with the states that come from directory sources (CMS, Healthlink, NPPES) than with claims-based states, and Endato is about equal. A plausible reason is shared lineage: those directory sources can be the origin of the vendor's own state, which [page 18](18_vendor_facility_state.md) already warns about. Claims are the more independent evidence, so a disagreement with a claims-backed state deserves more attention than agreement with a directory-only one. Claim counts say nothing about email ownership.

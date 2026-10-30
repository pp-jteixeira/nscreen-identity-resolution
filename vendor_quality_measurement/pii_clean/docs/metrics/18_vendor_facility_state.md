# Vendor state versus facility state

**Status:** published in all seven vendor metric views and `iceberg.jteixeira_ipa.pii_clean` on October 29, 2026. Full candidate integrity, schema and checksum checks passed. [Publication report](../../results/publication_20261029/report.md).

**Question:** does this exact vendor record’s state agree with its NPI’s preferred historical facility state?

**Target:** `vendor_state_evidence`, nullable `vendor_state_corroborated`, and `facility_primary_state` in `iceberg.jteixeira_ipa.pii__int_<vendor>__metrics` and `iceberg.jteixeira_ipa.pii_clean`. Key: `source`, `metric_row_id`.

## How it is computed

Read rank-1 rows from `bq_bi.analytics_prod.npi_facility_locations_with_ids`; join `npi_facility_provider_npi` to record `npi`. Normalize `state_code` with the existing recognized US state/DC/territory mapping. Group by NPI before joining so duplicate reference rows never multiply records.

A reference is usable only when every rank-1 row has a nonblank location and a recognized state, with exactly one distinct state. Conflicting states, missing states, missing locations and absent associations remain explicit.

Compare the record’s existing `source_state_values`:

```sql
contains(source_state_values, facility_primary_state)
```

| Outcome | Meaning |
|---|---|
| `corroborated` | One vendor state matches; boolean true. |
| `not_corroborated` | Known vendor states exclude the reference; false. |
| `mixed_vendor_states` | Multiple vendor states include the reference; null. |
| `unknown_vendor_state` | Usable reference without recognized vendor states; null. |
| `unknown_facility` | No usable reference; null. |

HealthLink states come from its retained HCP reference; other vendors use the exact email-bearing record. QuantumMedica has no usable states in existing measurements, and Haymarket has no state field. Unknowns stay unknown.

This mixed-source historical facility reference has no vendor-day alignment and can share vendor lineage. Agreement proves neither current attendance nor email ownership. Evaluation day defaults to Europe/Paris today; `location_evidence_day` fixes it.

## Real examples: contrasting outcomes

Selected real records, queried October 30, 2026, from `iceberg.jteixeira_ipa.pii_clean` at snapshot `8096642935433856886`. These examples explain outcomes; they are not prevalence estimates.

[Runnable example SQL](../../sql/examples/18_vendor_facility_state.sql):

```sql
WITH selected AS (
    SELECT *
    FROM iceberg.jteixeira_ipa.pii_clean FOR VERSION AS OF 8096642935433856886
    WHERE (source = 'endato' AND metric_row_id IN (
        '076750B47BF9525013CF247B1F4586BD63C3441A7597799E7FAFC4E08EAA4CA6',
        '7351D2A2087155D1835DBA4399370CD760431B0DE69D8DCC5B498F7D43C83E2F',
        'E03D083EF1264A05321CD9135171184D07BDF075F462D30469C3DC270B61AF29'))
       OR (source = 'healthlink' AND metric_row_id IN (
        'A96287FCC45637781C73F3B0A4B8B7F31EE7E0B7458875252C20087B8D2B6A32'))
       OR (source = 'quantummedica' AND metric_row_id IN (
        '1845B939777C8B052D855CC8A1B24DB40280A23F0DC7FE3AFFB7EA1020DA522A'))
)
SELECT m.source,
       m.source_state_values AS vendor_states,
       m.facility_primary_state AS facility_state,
       m.facility_reference_status,
       m.vendor_state_evidence,
       m.vendor_state_corroborated
FROM selected m
ORDER BY m.source, m.metric_row_id
```

**Result:** 5 rows.

| source | vendor_states | facility_state | facility_reference_status | vendor_state_evidence | vendor_state_corroborated |
|---|---|---|---|---|---|
| endato | [CA] | CA | usable | corroborated | true |
| endato | [RI] | MA | usable | not_corroborated | false |
| endato | [FL] | NULL | no_rank1_association | unknown_facility | NULL |
| healthlink | [NE, TX] | NE | usable | mixed_vendor_states | NULL |
| quantummedica | [] | IL | usable | unknown_vendor_state | NULL |

**What differentiates these cases:** One matching vendor state gives true; known states excluding the usable facility state give false. A mixture including the facility state remains NULL. Missing vendor evidence and unusable facility evidence also remain NULL, with different status labels. None proves current attendance.

Stored indicators are unchanged by display helpers. Reproduction requires the pinned snapshot to remain available.

## Vendor measurements

[Statistics SQL](../../sql/statistics/18_vendor_facility_state.sql). These read-only queries aggregate the published evidence columns in `iceberg.jteixeira_ipa.pii_clean`, without rebuilding reference joins. The tables below retain their stated historical measurement times. A later pipeline publication can change query results. Run vendor totals, then outcome counts; link-level outcomes can overlap across historical records.

Percentages use all distinct links within each vendor. Historical-state changes can put one link in multiple outcome groups.

| Vendor | Links | Agreement, n (%) | Disagreement, n (%) | Mixed, n (%) |
|---|---:|---:|---:|---:|
| HealthLink | 7,688,451 | 2,494,102 (32.44%) | 254,820 (3.31%) | 67,246 (0.87%) |
| QuantumMedica | 1,705,723 | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) |
| Medscape | 3,659,306 | 795,002 (21.73%) | 449,459 (12.28%) | 0 (0.00%) |
| Endato | 5,427,459 | 696,254 (12.83%) | 952,801 (17.56%) | 0 (0.00%) |
| RocketReach | 3,199,535 | 895,708 (27.99%) | 151,318 (4.73%) | 0 (0.00%) |
| DRDB | 826,886 | 261,222 (31.59%) | 36,685 (4.44%) | 0 (0.00%) |
| Haymarket | 4,223,245 | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) |

All 75,564,265 metric rows retained unique record keys. Integrity checks returned no failures. QuantumMedica and Haymarket supply no usable vendor states; missing reference and missing vendor evidence remain distinct. Full unknown-outcome counts are in the linked summary.

[Measurements and validation](../../results/location_evidence_summary.md) · [SQL](../../macros/location_evidence.sql) · [Integrity checks](../../tests/vendor_facility_state.sql) · Local tests (historical output, not retained: `../../results/location_evidence_local_tests.txt`)

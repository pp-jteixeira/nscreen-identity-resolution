# Vendor state versus facility state

**Status:** published in canonical snapshot `8811920360682490090`, verified October 31, 2026.

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

## Real examples

Executed October 31, 2026, against canonical snapshot `8811920360682490090`. These selected cases explain outcomes; they do not measure prevalence.

[Executed example SQL](../../sql/examples/18_vendor_facility_state.sql):

```sql
WITH selected AS (
    SELECT *
    FROM iceberg.jteixeira_ipa.pii_clean FOR VERSION AS OF 8811920360682490090
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
       m.npi,
       m.source_state_values AS vendor_states,
       m.facility_primary_state AS facility_state,
       m.facility_reference_status,
       m.vendor_state_evidence,
       m.vendor_state_corroborated
FROM selected m
ORDER BY m.source, m.metric_row_id
```

| source | npi | vendor_states | facility_state | facility_reference_status | vendor_state_evidence | vendor_state_corroborated |
|---|---|---|---|---|---|---|
| endato | 1750598025 | [CA] | CA | usable | corroborated | true |
| endato | 1154617082 | [RI] | MA | usable | not_corroborated | false |
| endato | 1578677886 | [FL] | NULL | no_rank1_association | unknown_facility | NULL |
| healthlink | 1568840411 | [NE, TX] | NE | usable | mixed_vendor_states | NULL |
| quantummedica | 1063414944 | [] | IL | usable | unknown_vendor_state | NULL |

**What differentiates these cases:** One matching vendor state gives true; known states excluding the usable facility state give false. A mixture including the facility state remains NULL. Missing vendor evidence and unusable facility evidence also remain NULL, with different status labels. None proves current attendance.

## Statistics by source

Measured **October 31, 2026** from `iceberg.jteixeira_ipa.pii_clean` snapshot `8811920360682490090`. These are exact published-population counts across retained eligible history, not a sample. Stored evaluation dates remain unchanged.

[Executed statistics SQL 1](../../sql/statistics/18_vendor_facility_state.sql) · [Executed statistics SQL 2](../../sql/statistics/18_vendor_facility_state_statement_002.sql)

| Source | Metric records | corroborated, n (%) | not corroborated, n (%) | mixed vendor states, n (%) | unknown vendor state, n (%) | unknown facility, n (%) |
|---|---|---|---|---|---|---|
| HealthLink | 11,156,016 | 3,797,466 (34.039625%) | 398,096 (3.568442%) | 105,616 (0.946718%) | 3,849 (0.034502%) | 6,850,989 (61.410713%) |
| QuantumMedica | 1,705,723 | 0 (0.000000%) | 0 (0.000000%) | 0 (0.000000%) | 785,918 (46.075359%) | 919,805 (53.924641%) |
| Medscape | 47,164,366 | 13,713,439 (29.075847%) | 5,789,727 (12.275638%) | 0 (0.000000%) | 320,788 (0.680149%) | 27,340,412 (57.968365%) |
| Endato | 5,427,459 | 697,557 (12.852368%) | 955,595 (17.606674%) | 0 (0.000000%) | 469 (0.008641%) | 3,773,838 (69.532317%) |
| RocketReach | 4,864,145 | 1,370,913 (28.184049%) | 231,579 (4.760939%) | 0 (0.000000%) | 284,682 (5.852663%) | 2,976,971 (61.202349%) |
| DRDB | 1,115,415 | 362,440 (32.493736%) | 52,686 (4.723444%) | 0 (0.000000%) | 0 (0.000000%) | 700,289 (62.782821%) |
| Haymarket | 4,223,245 | 0 (0.000000%) | 0 (0.000000%) | 0 (0.000000%) | 1,778,546 (42.113257%) | 2,444,699 (57.886743%) |

Percentages use all metric records and partition each source population. Mixed evidence and missing evidence remain NULL for the boolean agreement flag. All stored evidence invariant checks returned zero failures. Geographic agreement does not establish attendance or ownership.

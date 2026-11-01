# Cookie-location evidence

**Status:** published in canonical snapshot `4233051104478921549`, verified October 31, 2026.

**Question:** what UID-linked states were observed during the three completed days before evaluation?

**Target:** `cookie_location_status`, UID/day counts, `cookie_state_values`, vendor/facility comparisons and coverage fields in `iceberg.jteixeira_ipa.pii_clean`, populated from source-scoped `int_cookie__metrics` evidence and record-specific comparisons. Key: `source`, `metric_row_id`. [Output reference](../../results/location_evidence_summary.md#output-columns).

## How it is computed

Hash normalized email with SHA-256 and match `iceberg.thirdparty.liveintent_idsync.hashedemail_sha256`. Parse `uids` as pipe-separated `type:uid` tokens, preserving UID strings and namespace labels. Reject malformed tokens; deduplicate hash/day/UID tuples. These identifiers are not verified browser cookies.

Join UID to same-day `iceberg.crossscreen.nscreen_geo_daily_ua.uid`, mapping numeric `geo` ZIP3 through `iceberg.jteixeira_ipa.tmp_zip3_to_state`. Collapse duplicate ZIP3 keys; ambiguous mappings remain unknown. This provider-derived lookup is not an authoritative postal boundary map.

Rank recognized states per UID by distinct observed dates **before** the email join. One deterministic winner is retained; tied winners establish no state agreement. Count mapped, observed, located and eligible UID-days separately. A primary state must appear on the mapping day. Duplicate mappings cannot add observations.

`cookie_state_values` contains only untied same-day primary states. Compare these separately with record vendor states and the usable facility state. Missing observations or references remain explicit unknowns, not mismatches. No scores or fractional votes are calculated.

## Real examples

Executed October 31, 2026, against canonical snapshot `4233051104478921549`. These selected cases explain outcomes; they do not measure prevalence.

[Executed example SQL](../../sql/examples/19_cookie_location_evidence.sql):

```sql
WITH classified AS (
    SELECT metric_row_id,
           CASE WHEN cookie_location_status = 'observed'
                THEN 'observed_' || cookie_vendor_state_evidence
                ELSE cookie_location_status END AS example_case
    FROM iceberg.jteixeira_ipa.pii_clean FOR VERSION AS OF 4233051104478921549
    WHERE source = 'endato'
), chosen AS (
    SELECT example_case, min(metric_row_id) AS metric_row_id
    FROM classified
    WHERE example_case IN ('observed_corroborated', 'observed_not_observed',
        'ambiguous_primary_state', 'no_state_observation', 'no_mapping', 'unknown_state')
    GROUP BY example_case
)
SELECT m.source, m.email, m.npi, m.cookie_location_status,
       m.cookie_count AS mapped_uids,
       m.cookie_eligible_uid_days AS eligible_uid_days,
       m.cookie_primary_state_tied_count AS tied_uids,
       m.cookie_state_values AS states,
       m.source_state_values AS vendor_states,
       m.cookie_vendor_state_evidence AS vendor_evidence
FROM iceberg.jteixeira_ipa.pii_clean FOR VERSION AS OF 4233051104478921549 m
JOIN chosen c ON c.metric_row_id = m.metric_row_id
WHERE m.source = 'endato'
ORDER BY c.example_case
```

| source | email | npi | cookie_location_status | mapped_uids | eligible_uid_days | tied_uids | states | vendor_states | vendor_evidence |
|---|---|---|---|---|---|---|---|---|---|
| endato | rwilson1008@hotmail.com | 1154368264 | ambiguous_primary_state | 58 | 0 | 1 | [] | [OH] | unknown_cookie_location |
| endato | cshuford@epix.net | 1447508080 | no_mapping | 0 | 0 | 0 | [] | [NC] | unknown_cookie_location |
| endato | wbahou1@hotmail.com | 1891720702 | no_state_observation | 12 | 0 | 0 | [] | [NY] | unknown_cookie_location |
| endato | pavaswani@hotmail.com | 1528352440 | observed | 5 | 3 | 0 | [CA] | [CA] | corroborated |
| endato | vboyert@gmail.com | 1295334530 | observed | 15 | 6 | 0 | [MN] | [SC] | not_observed |
| endato | yvettefields@msn.com | 1659612588 | unknown_state | 12 | 0 | 0 | [] | [GA] | unknown_cookie_location |

**What differentiates these cases:** A usable untied primary state can corroborate the vendor state or exclude it, so `observed` does not itself mean agreement. A tied primary state cannot supply agreement. A mapped UID without a qualifying state is different from having no mapping at all. The `unknown_state` example has observations but no recognized state. These counts are UID evidence, not independent confirmations or verified people.

## Statistics by source

Measured **October 31, 2026** from `iceberg.jteixeira_ipa.pii_clean` snapshot `4233051104478921549`. These are exact counts across all stored source/email/NPI links, not a sample. Cookie observations are limited to the stored three-day window. Other metric evaluation dates remain unchanged.

[Executed statistics SQL 1](../../sql/statistics/19_cookie_location_evidence.sql) · [Executed statistics SQL 2](../../sql/statistics/19_cookie_location_evidence_statement_002.sql) · [Executed statistics SQL 3](../../sql/statistics/19_cookie_location_evidence_statement_003.sql)

Stored window: **2026-10-28–2026-10-30**, **3 days**. Mapping and geography each contain **3/3 days**, with no missing dates. Status is `all_source_days_present`. Date presence does not establish complete ingestion.

| Source | Email/NPI links | observed, n (%) | ambiguous primary state, n (%) | no mapping, n (%) | no state observation, n (%) | unknown state, n (%) |
|---|---|---|---|---|---|---|
| HealthLink | 7,688,451 | 783,195 (10.186642%) | 305 (0.003967%) | 6,776,240 (88.135308%) | 128,462 (1.670844%) | 249 (0.003239%) |
| QuantumMedica | 1,705,723 | 124,623 (7.306169%) | 42 (0.002462%) | 1,558,811 (91.387113%) | 22,209 (1.302029%) | 38 (0.002228%) |
| Medscape | 3,659,659 | 594,295 (16.239081%) | 223 (0.006093%) | 2,968,279 (81.108076%) | 96,677 (2.641694%) | 185 (0.005055%) |
| Endato | 5,427,459 | 491,129 (9.048967%) | 221 (0.004072%) | 4,860,971 (89.562556%) | 74,997 (1.381807%) | 141 (0.002598%) |
| RocketReach | 3,199,535 | 130,280 (4.071842%) | 47 (0.001469%) | 3,047,710 (95.254779%) | 21,466 (0.670910%) | 32 (0.001000%) |
| DRDB | 826,886 | 60,164 (7.275973%) | 19 (0.002298%) | 756,285 (91.461822%) | 10,395 (1.257126%) | 23 (0.002782%) |
| Haymarket | 4,223,245 | 385,223 (9.121493%) | 148 (0.003504%) | 3,772,302 (89.322358%) | 65,465 (1.550111%) | 107 (0.002534%) |

Percentages use distinct source/email/NPI links. Location statuses partition those links within each source. Vendor-state agreement is a separate record-level outcome and its distinct-link groups can overlap. Date presence does not prove complete ingestion. Snapshot days can share upstream history and are not independent confirmations. All corrected, window-length-aware statistical invariant checks returned zero failures.

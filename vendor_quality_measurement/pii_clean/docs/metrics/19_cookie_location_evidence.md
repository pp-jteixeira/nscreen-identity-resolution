# Cookie-location evidence

**Status:** published in canonical snapshot `8811920360682490090`, verified October 31, 2026.

**Question:** what UID-linked states were observed during the three completed days before evaluation?

**Target:** `cookie_location_status`, UID/day counts, `cookie_state_values`, vendor/facility comparisons and coverage fields in `iceberg.jteixeira_ipa.pii_clean`, populated from shared `int_cookie__metrics` evidence and record-specific comparisons. Key: `source`, `metric_row_id`. [Output reference](../../results/location_evidence_summary.md#output-columns).

## How it is computed

Hash normalized email with SHA-256 and match `iceberg.thirdparty.liveintent_idsync.hashedemail_sha256`. Parse `uids` as pipe-separated `type:uid` tokens, preserving UID strings and namespace labels. Reject malformed tokens; deduplicate hash/day/UID tuples. These identifiers are not verified browser cookies.

Join UID to same-day `iceberg.crossscreen.nscreen_geo_daily_ua.uid`, mapping numeric `geo` ZIP3 through `iceberg.jteixeira_ipa.tmp_zip3_to_state`. Collapse duplicate ZIP3 keys; ambiguous mappings remain unknown. This provider-derived lookup is not an authoritative postal boundary map.

Rank recognized states per UID by distinct observed dates **before** the email join. One deterministic winner is retained; tied winners establish no state agreement. Count mapped, observed, located and eligible UID-days separately. A primary state must appear on the mapping day. Duplicate mappings cannot add observations.

`cookie_state_values` contains only untied same-day primary states. Compare these separately with record vendor states and the usable facility state. Missing observations or references remain explicit unknowns, not mismatches. No scores or fractional votes are calculated.

## Real examples

Executed October 31, 2026, against canonical snapshot `8811920360682490090`. These selected cases explain outcomes; they do not measure prevalence.

[Executed example SQL](../../sql/examples/19_cookie_location_evidence.sql):

```sql
WITH selected AS (
    SELECT *
    FROM iceberg.jteixeira_ipa.pii_clean FOR VERSION AS OF 8811920360682490090
    WHERE (source = 'endato' AND metric_row_id IN (
        '24D4FC70423A14826D64416BCED92B280D096656622E292DA0EB587CDF30608C',
        '26B3927D287C100691C44DD0E22FBC1B9659860E48E9D6237424A884FF6075F5',
        '0005570358223A037F83CCA0B55CE24FC3DD87B1DDC38C3B784A4AF2ED97C12C',
        '93A2769D124D567DC09A1DF0B73D69824C2111452E45045005E64F3AF0214D25',
        'C1ABB31A0F4C9EA4D613091E85B64872D18FD597460D8AD51138A13ECD0C202E'))
)
SELECT m.source,
       m.email,
       m.npi,
       m.cookie_location_status,
       m.cookie_count AS mapped_uids,
       m.cookie_eligible_uid_days AS eligible_uid_days,
       m.cookie_primary_state_tied_count AS tied_uids,
       m.cookie_state_values AS states,
       m.source_state_values AS vendor_states,
       m.cookie_vendor_state_evidence AS vendor_evidence
FROM selected m
ORDER BY m.source, m.metric_row_id
```

| source | email | npi | cookie_location_status | mapped_uids | eligible_uid_days | tied_uids | states | vendor_states | vendor_evidence |
|---|---|---|---|---|---|---|---|---|---|
| endato | vsdrdanhost@gmail.com | 1508814435 | ambiguous_primary_state | 39 | 0 | 1 | [] | [CA] | unknown_cookie_location |
| endato | themyersplace@msn.com | 1336342260 | observed | 18 | 15 | 1 | [IL] | [IL] | corroborated |
| endato | meesha_h_2000@yahoo.com | 1609492917 | observed | 22 | 4 | 0 | [FL, NJ] | [PA] | not_observed |
| endato | obuttons33@aol.com | 1033879507 | no_state_observation | 22 | 0 | 0 | [] | [OH] | unknown_cookie_location |
| endato | sfoxxi10@latinmail.com | 1013024215 | no_mapping | 0 | 0 | 0 | [] | [NE] | unknown_cookie_location |

**What differentiates these cases:** A usable untied primary state can corroborate the vendor state or exclude it, so `observed` does not itself mean agreement. A tied primary state cannot supply agreement. A mapped UID without a qualifying state is different from having no mapping at all. These counts are UID evidence, not independent confirmations or verified people.

## Statistics by source

Measured **October 31, 2026** from `iceberg.jteixeira_ipa.pii_clean` snapshot `8811920360682490090`. These are exact published-population counts across retained eligible history, not a sample. Stored evaluation dates remain unchanged.

[Executed statistics SQL 1](../../sql/statistics/19_cookie_location_evidence.sql) · [Executed statistics SQL 2](../../sql/statistics/19_cookie_location_evidence_statement_002.sql) · [Executed statistics SQL 3](../../sql/statistics/19_cookie_location_evidence_statement_003.sql)

Stored window: **2026-10-28–2026-10-30**, **3 days**. Mapping and geography each contain **2/3 days**, missing **2026-10-30**. Status is `missing_source_days`. Missing input days remain explicit and must not be interpreted as observed absence.

| Source | Email/NPI links | observed, n (%) | ambiguous primary state, n (%) | no mapping, n (%) | no state observation, n (%) | unknown state, n (%) |
|---|---|---|---|---|---|---|
| HealthLink | 7,688,451 | 763,040 (9.924496%) | 3,166 (0.041179%) | 6,787,601 (88.283075%) | 134,510 (1.749507%) | 134 (0.001743%) |
| QuantumMedica | 1,705,723 | 121,444 (7.119796%) | 461 (0.027027%) | 1,560,649 (91.494868%) | 23,153 (1.357372%) | 16 (0.000938%) |
| Medscape | 3,659,659 | 579,218 (15.827103%) | 2,322 (0.063449%) | 2,976,630 (81.336267%) | 101,386 (2.770367%) | 103 (0.002814%) |
| Endato | 5,427,459 | 479,170 (8.828625%) | 1,915 (0.035284%) | 4,867,804 (89.688453%) | 78,500 (1.446349%) | 70 (0.001290%) |
| RocketReach | 3,199,535 | 126,905 (3.966358%) | 481 (0.015033%) | 3,049,657 (95.315632%) | 22,481 (0.702633%) | 11 (0.000344%) |
| DRDB | 826,886 | 58,596 (7.086346%) | 220 (0.026606%) | 757,217 (91.574534%) | 10,841 (1.311063%) | 12 (0.001451%) |
| Haymarket | 4,223,245 | 375,168 (8.883406%) | 1,524 (0.036086%) | 3,777,990 (89.457041%) | 68,510 (1.622212%) | 53 (0.001255%) |

Percentages use distinct source/email/NPI links. Location statuses partition those links within each source. Vendor-state agreement is a separate record-level outcome and its distinct-link groups can overlap. Date presence does not prove complete ingestion. Snapshot days can share upstream history and are not independent confirmations. All corrected, window-length-aware statistical invariant checks returned zero failures.

# Cookie-location evidence

**Status:** published in all seven vendor metric views and `iceberg.jteixeira_ipa.pii_clean` on October 29, 2026. Full candidate integrity, schema and checksum checks passed. [Publication report](../../results/publication_20261029/report.md).

**Question:** what UID-linked states were observed during the seven completed days before evaluation?

**Target:** `cookie_location_status`, UID/day counts, `cookie_state_values`, vendor/facility comparisons and coverage fields in `iceberg.jteixeira_ipa.pii__int_<vendor>__metrics` and `iceberg.jteixeira_ipa.pii_clean`. Key: `source`, `metric_row_id`. [Output reference](../../results/location_evidence_summary.md#output-columns).

## How it is computed

Hash normalized email with SHA-256 and match `iceberg.thirdparty.liveintent_idsync.hashedemail_sha256`. Parse `uids` as pipe-separated `type:uid` tokens, preserving UID strings and namespace labels. Reject malformed tokens; deduplicate hash/day/UID tuples. These identifiers are not verified browser cookies.

Join UID to same-day `iceberg.crossscreen.nscreen_geo_daily_ua.uid`, mapping numeric `geo` ZIP3 through `iceberg.jteixeira_ipa.tmp_zip3_to_state`. Collapse duplicate ZIP3 keys; ambiguous mappings remain unknown. This provider-derived lookup is not an authoritative postal boundary map.

Rank recognized states per UID by distinct observed dates **before** the email join. One deterministic winner is retained; tied winners establish no state agreement. Count mapped, observed, located and eligible UID-days separately. A primary state must appear on the mapping day. Duplicate mappings cannot add observations.

`cookie_state_values` contains only untied same-day primary states. Compare these separately with record vendor states and the usable facility state. Missing observations or references remain explicit unknowns, not mismatches. No scores or fractional votes are calculated.

## Real examples: contrasting outcomes

Selected real records, queried October 30, 2026, from `iceberg.jteixeira_ipa.pii_clean` at snapshot `8096642935433856886`. These examples explain outcomes; they are not prevalence estimates. Stored evaluation day: `2026-10-29`; observation window: `2026-10-22`–`2026-10-28`, inclusive. The stored evaluation window is used; no live mapping or geography join is recomputed. `eligible_uid_days` counts qualifying UID/day observations, while `mapped_uids` and `tied_uids` count identifiers.

[Runnable example SQL](../../sql/examples/19_cookie_location_evidence.sql):

```sql
WITH selected AS (
    SELECT *
    FROM iceberg.jteixeira_ipa.pii_clean FOR VERSION AS OF 8096642935433856886
    WHERE (source = 'endato' AND metric_row_id IN (
        '24D4FC70423A14826D64416BCED92B280D096656622E292DA0EB587CDF30608C',
        '26B3927D287C100691C44DD0E22FBC1B9659860E48E9D6237424A884FF6075F5',
        '425055A3EB89C18FBC5885A9E12FD5EA08C792EE3E57CDD8EF841FAE19A203C9',
        '93A2769D124D567DC09A1DF0B73D69824C2111452E45045005E64F3AF0214D25',
        'C1ABB31A0F4C9EA4D613091E85B64872D18FD597460D8AD51138A13ECD0C202E'))
)
SELECT m.source,
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

**Result:** 5 rows.

| source | cookie_location_status | mapped_uids | eligible_uid_days | tied_uids | states | vendor_states | vendor_evidence |
|---|---|---|---|---|---|---|---|
| endato | observed | 21 | 48 | 0 | [IL] | [IL] | corroborated |
| endato | ambiguous_primary_state | 22 | 0 | 1 | [] | [PA] | unknown_cookie_location |
| endato | observed | 20 | 12 | 0 | [LA, TX] | [SC] | not_observed |
| endato | no_state_observation | 23 | 0 | 0 | [] | [OH] | unknown_cookie_location |
| endato | no_mapping | 0 | 0 | 0 | [] | [NE] | unknown_cookie_location |

**What differentiates these cases:** A usable untied primary state can corroborate the vendor state or exclude it, so `observed` does not itself mean agreement. A tied primary state cannot supply agreement. A mapped UID without a qualifying state is different from having no mapping at all. These counts are UID evidence, not independent confirmations or verified people.

Stored indicators are unchanged by display helpers. Reproduction requires the pinned snapshot to remain available.

## Window and measurements

[Statistics SQL](../../sql/statistics/19_cookie_location_evidence.sql). These read-only queries aggregate the published evidence columns in `iceberg.jteixeira_ipa.pii_clean`, without rebuilding reference joins. The tables below retain their stated historical measurement times. A later pipeline publication can change query results. Run coverage, vendor totals and grouped outcomes; select the named grouping-set section instead of summing overlapping sections. Coverage reports the stored window start/end and availability. Outcomes use the evaluation window captured by the pipeline, rather than recomputing a fixed-date lookup.

Default evaluation uses Europe/Paris today; `location_evidence_day` fixes it. October 29 evaluation uses October 22–28, excluding evaluation day and future data. Historical vendor records remain intact; this is retrospective window evidence, not historical attendance.

Metadata inspection found mapping dates on 6/7 days (85.71%), missing October 28; geo dates on 7/7 (100%). Date presence does not establish complete data. Geo snapshots can share a 15-day hourly lookback; repeated days are not independent confirmations.

Counts below use distinct links within each vendor. Percentages use all links in that vendor.

| Vendor | Links | Usable location, n (%) |
|---|---:|---:|
| HealthLink | 7,688,451 | 831,792 (10.82%) |
| QuantumMedica | 1,705,723 | 132,843 (7.79%) |
| Medscape | 3,659,306 | 630,778 (17.24%) |
| Endato | 5,427,459 | 520,975 (9.60%) |
| RocketReach | 3,199,535 | 138,527 (4.33%) |
| DRDB | 826,886 | 64,071 (7.75%) |
| Haymarket | 4,223,245 | 409,659 (9.70%) |

All 75,564,265 metric rows and 26,730,605 source/email/NPI links were retained. No invariant failures. Full per-email coverage and comparison outcomes are linked below.

[Evidence and limitations](../../results/location_evidence_summary.md) · [SQL](../../macros/cookie_location.sql) · Source inspection (historical output, not retained: `../../results/location_source_inspection.json`) · Local tests (historical output, not retained: `../../results/location_evidence_local_tests.txt`)

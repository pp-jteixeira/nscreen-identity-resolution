# Cookie-location evidence

**Status:** native fixtures and full-population read-only measurements passed on October 29, 2026. Unpublished.

**Question:** what UID-linked states were observed during the seven completed days before evaluation?

**Target:** `cookie_location_status`, UID/day counts, `cookie_state_values`, vendor/facility comparisons and coverage fields in `iceberg.jteixeira_ipa.pii__int_<vendor>__metrics` and `iceberg.jteixeira_ipa.pii_clean`. Key: `source`, `metric_row_id`. [Output reference](../../results/location_evidence_summary.md#output-columns).

## How it is computed

Hash normalized email with SHA-256 and match `iceberg.thirdparty.liveintent_idsync.hashedemail_sha256`. Parse `uids` as pipe-separated `type:uid` tokens, preserving UID strings and namespace labels. Reject malformed tokens; deduplicate hash/day/UID tuples. These identifiers are not verified browser cookies.

Join UID to same-day `iceberg.crossscreen.nscreen_geo_daily_ua.uid`, mapping numeric `geo` ZIP3 through `iceberg.jteixeira_ipa.tmp_zip3_to_state`. Collapse duplicate ZIP3 keys; ambiguous mappings remain unknown. This provider-derived lookup is not an authoritative postal boundary map.

Rank recognized states per UID by distinct observed dates **before** the email join. One deterministic winner is retained; tied winners establish no state agreement. Count mapped, observed, located and eligible UID-days separately. A primary state must appear on the mapping day. Duplicate mappings cannot add observations.

**Illustrative:** NY observed twice versus CA once selects NY. A NY/CA tie remains ambiguous. An October 23 location cannot fill an October 22 mapping.

`cookie_state_values` contains only untied same-day primary states. Compare these separately with record vendor states and the usable facility state. Missing observations or references remain explicit unknowns, not mismatches. No scores or fractional votes are calculated.

## Window and measurements

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

[Evidence and limitations](../../results/location_evidence_summary.md) · [SQL](../../macros/cookie_location.sql) · Source inspection (local-only: `../../results/location_source_inspection.json`) · Local tests (local-only: `../../results/location_evidence_local_tests.txt`)

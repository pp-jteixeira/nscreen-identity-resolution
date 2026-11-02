# Cookie-location evidence

**Question:** what UID-linked states were observed during the three completed days before evaluation?

**Target:** `cookie_location_status`, UID/day counts, `cookie_state_values`, vendor/facility comparisons (`cookie_vendor_state_evidence`, `cookie_vendor_state_evidence_latest`, `cookie_facility_state_evidence`) and coverage fields in `iceberg.jteixeira_ipa.pii_clean`, populated from source-scoped `int_cookie__metrics` evidence and link-specific comparisons. One row per source/email/NPI link; key: `source`, `link_id`. [Output reference](../../results/location_evidence_summary.md#output-columns).

## How it is computed

Hash normalized email with SHA-256 and match `iceberg.thirdparty.liveintent_idsync.hashedemail_sha256`. Parse `uids` as pipe-separated `type:uid` tokens, preserving UID strings and namespace labels. Reject malformed tokens; deduplicate hash/day/UID tuples. These identifiers are not verified browser cookies.

Join UID to same-day `iceberg.crossscreen.nscreen_geo_daily_ua.uid`, mapping numeric `geo` ZIP3 through `iceberg.jteixeira_ipa.tmp_zip3_to_state`. Collapse duplicate ZIP3 keys; ambiguous mappings remain unknown. This provider-derived lookup is not an authoritative postal boundary map.

Rank recognized states per UID by distinct observed dates **before** the email join. One deterministic winner is retained; tied winners establish no state agreement. Count mapped, observed, located and eligible UID-days separately. A primary state must appear on the mapping day. Duplicate mappings cannot add observations.

`cookie_state_values` contains only untied same-day primary states. Compare these separately with the link's vendor states and the usable facility state. Missing observations or references remain explicit unknowns, not mismatches. No scores or fractional votes are calculated.

`cookie_vendor_state_evidence` compares with `source_state_values`, the union of recognized states across all versions of the link. `cookie_vendor_state_evidence_latest` applies the same comparison to `source_state_values_latest`, the states of the link's latest version only; it is NULL when the link has no single latest version. Cookie evidence itself depends only on the email, so every version of a link shares it.

## Real examples

Executed November 2, 2026, against `iceberg.jteixeira_ipa.pii_clean` snapshot `2837737034249693554`. These selected cases explain outcomes; they do not measure prevalence.

```sql
SELECT source, email, npi, record_count, cookie_location_status, cookie_count,
       cookie_observed_uid_days, cookie_eligible_uid_days, cookie_state_values,
       source_state_values, cookie_vendor_state_evidence,
       source_state_values_latest, cookie_vendor_state_evidence_latest
FROM iceberg.jteixeira_ipa.pii_clean
WHERE ROW(source, link_id) IN (
    ROW('healthlink', '00006002C8B151910CB639620097E29E13905A5F998BA53643739E073599B47F'),
    ROW('healthlink', '00002510C623ED5124A60DDE2861965DFAC1FF19722762D71F3F16141865380A'),
    ROW('healthlink', '00000EC46A5D65063CDB316FD156FA86F0494D5E74FE806E76AAB42898301B2E'),
    ROW('healthlink', '000003E1464D72618D55F78C6D464B854F2B8213906F0546468EE5C189A1376A'),
    ROW('healthlink', '003608E2F77886A64B85974E79E7A9E4A8CCA99DBABD917B1385D49AD3564BF0'),
    ROW('quantummedica', '00000BA286ADECF777EA438FAA70261EEA429A67DBD4E6C1A467307C957CEE9A'),
    ROW('medscape', '039B544EF56627174B58FBBC5BF96B4B9B2621DEB1E0A41D3EF8DFE2A6F0E5E4'),
    ROW('medscape', '04B9E39F1A6D7BDA26F224B6B7B540DC46F91FC034EDAD8593C542FA7766167E'))
ORDER BY source, link_id
```

| source | email | npi | record_count | cookie_location_status | cookie_count | cookie_observed_uid_days | cookie_eligible_uid_days | cookie_state_values | source_state_values | cookie_vendor_state_evidence | source_state_values_latest | cookie_vendor_state_evidence_latest |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| healthlink | csteele@hotmail.com | 1720286941 | 3 | no_mapping | 0 | 0 | 0 | [] | [TX] | unknown_cookie_location | [TX] | unknown_cookie_location |
| healthlink | susancbloom@gmail.com | 1306272737 | 1 | observed | 21 | 7 | 7 | [MI, PA] | [PA] | mixed_state_evidence | [PA] | mixed_state_evidence |
| healthlink | guillermopadilla@gmail.com | 1124229265 | 1 | observed | 12 | 3 | 3 | [NJ] | [LA] | not_observed | [LA] | not_observed |
| healthlink | tara.perkins@earthlink.net | 1306093034 | 2 | observed | 17 | 3 | 3 | [OH] | [OH] | corroborated | [OH] | corroborated |
| healthlink | christinalebedis@gmail.com | 1073703112 | 1 | ambiguous_primary_state | 12 | 2 | 0 | [] | [MA] | unknown_cookie_location | [MA] | unknown_cookie_location |
| medscape | awoods3102@aol.com | 1043201486 | 2 | observed | 18 | 5 | 5 | [AZ] | [AZ, TX] | mixed_state_evidence | [AZ] | corroborated |
| medscape | saraharamirez@gmail.com | 1215356118 | 2 | observed | 37 | 13 | 13 | [NC, NY, TN] | [NJ, NY] | mixed_state_evidence | [NJ] | not_observed |
| quantummedica | angiescanales@yahoo.com | 1942511381 | 1 | observed | 22 | 9 | 8 | [IN, TX] | [] | unknown_reference_state | [] | unknown_reference_state |

**What differentiates these cases:** `csteele@hotmail.com` has no mapped UID at all (`no_mapping`, `cookie_count` 0), so every comparison is `unknown_cookie_location`. `christinalebedis@gmail.com` has mapped UIDs and two observed UID-days, but the primary state is tied, so no UID-day is eligible (`ambiguous_primary_state`, empty `cookie_state_values`). `tara.perkins@earthlink.net` has one untied cookie state, OH, equal to the vendor state (`corroborated`). `guillermopadilla@gmail.com` is observed in NJ against a vendor state of LA (`not_observed`), so `observed` itself does not mean agreement. `susancbloom@gmail.com` is observed in MI and PA against a vendor state of PA, which is `mixed_state_evidence`. QuantumMedica `angiescanales@yahoo.com` is observed in IN and TX but has no vendor state (`unknown_reference_state`). The Medscape links have two versions and share the same cookie evidence, but the version comparison differs: `awoods3102@aol.com` reports AZ and TX across versions (`mixed_state_evidence`), and its latest version reports only AZ (`corroborated`); `saraharamirez@gmail.com` reports NJ and NY across versions, and its latest version reports only NJ, which the cookie states NC, NY and TN exclude (`not_observed`). These counts are UID evidence, not independent confirmations or verified people.

## Statistics by source

Measured **November 2, 2026** from `iceberg.jteixeira_ipa.pii_clean` snapshot `2837737034249693554`. These are exact published-population counts across retained eligible history, not a sample. Cookie observations are limited to the stored three-day window, 2026-10-30 to 2026-11-01 (`cookie_location_window_days` 3). The base statement returns one row for the whole table: the mapping and location sources have all three days present (`cookie_mapping_available_days` 3, `cookie_location_available_days` 3, no missing days, status `all_source_days_present`), so every link has the same window and full source coverage. Vendor periods are unrelated to this window. Source data period (first and last observed day): HealthLink 2026-01-07 to 2026-10-03, QuantumMedica 2025-09-14 to 2026-10-15, Medscape 2024-01-10 to 2026-11-01 and Haymarket 2021-07-06 (one snapshot day). Endato, RocketReach and DRDB are undated.

[Statistics SQL 1](../../sql/statistics/19_cookie_location_evidence.sql) · [Statistics SQL 2](../../sql/statistics/19_cookie_location_evidence_statement_002.sql) · [Statistics SQL 3](../../sql/statistics/19_cookie_location_evidence_statement_003.sql) · [Statistics SQL 4](../../sql/statistics/19_cookie_location_evidence_statement_004.sql)

Statement 3 reports three overlapping sections. Each section partitions the links of a source on its own, so counts and percentages must never be summed across sections. Percentages use all links of the source.

Cookie location status:

| Source | Links | observed, n (%) | no mapping, n (%) | no state observation, n (%) | ambiguous primary state, n (%) | unknown state, n (%) |
|---|---|---|---|---|---|---|
| HealthLink | 7,688,451 | 786,359 (10.227795%) | 6,773,300 (88.097069%) | 128,204 (1.667488%) | 325 (0.004227%) | 263 (0.003421%) |
| QuantumMedica | 1,705,723 | 125,197 (7.339820%) | 1,558,272 (91.355513%) | 22,166 (1.299508%) | 38 (0.002228%) | 50 (0.002931%) |
| Medscape | 3,661,537 | 597,070 (16.306540%) | 2,967,438 (81.043507%) | 96,585 (2.637827%) | 227 (0.006200%) | 217 (0.005926%) |
| Endato | 5,427,459 | 493,413 (9.091050%) | 4,859,068 (89.527493%) | 74,630 (1.375045%) | 181 (0.003335%) | 167 (0.003077%) |
| RocketReach | 3,199,535 | 130,763 (4.086938%) | 3,047,168 (95.237839%) | 21,504 (0.672098%) | 56 (0.001750%) | 44 (0.001375%) |
| DRDB | 826,886 | 60,467 (7.312616%) | 756,027 (91.430620%) | 10,351 (1.251805%) | 17 (0.002056%) | 24 (0.002902%) |
| Haymarket | 4,223,245 | 387,003 (9.163641%) | 3,770,764 (89.285940%) | 65,170 (1.543126%) | 165 (0.003907%) | 143 (0.003386%) |

Cookie evidence compared with the vendor states (`cookie_vendor_state_evidence`):

| Source | Links | corroborated, n (%) | not observed, n (%) | mixed state evidence, n (%) | unknown reference state, n (%) | unknown cookie location, n (%) |
|---|---|---|---|---|---|---|
| HealthLink | 7,688,451 | 184,725 (2.402630%) | 354,732 (4.613829%) | 230,700 (3.000604%) | 16,202 (0.210732%) | 6,902,092 (89.772205%) |
| QuantumMedica | 1,705,723 | 0 (0.000000%) | 0 (0.000000%) | 0 (0.000000%) | 125,197 (7.339820%) | 1,580,526 (92.660180%) |
| Medscape | 3,661,537 | 157,644 (4.305405%) | 206,750 (5.646536%) | 201,607 (5.506076%) | 31,069 (0.848523%) | 3,064,467 (83.693460%) |
| Endato | 5,427,459 | 110,363 (2.033419%) | 243,586 (4.488030%) | 139,350 (2.567500%) | 114 (0.002100%) | 4,934,046 (90.908950%) |
| RocketReach | 3,199,535 | 30,726 (0.960327%) | 39,374 (1.230616%) | 35,746 (1.117225%) | 24,917 (0.778769%) | 3,068,772 (95.913062%) |
| DRDB | 826,886 | 16,416 (1.985280%) | 23,291 (2.816712%) | 20,760 (2.510624%) | 0 (0.000000%) | 766,419 (92.687384%) |
| Haymarket | 4,223,245 | 0 (0.000000%) | 0 (0.000000%) | 0 (0.000000%) | 387,003 (9.163641%) | 3,836,242 (90.836359%) |

Cookie evidence compared with the usable facility state (`cookie_facility_state_evidence`):

| Source | Links | corroborated, n (%) | not observed, n (%) | mixed state evidence, n (%) | unknown reference state, n (%) | unknown cookie location, n (%) |
|---|---|---|---|---|---|---|
| HealthLink | 7,688,451 | 63,748 (0.829140%) | 115,658 (1.504308%) | 71,867 (0.934740%) | 535,086 (6.959607%) | 6,902,092 (89.772205%) |
| QuantumMedica | 1,705,723 | 13,227 (0.775448%) | 29,397 (1.723433%) | 15,588 (0.913865%) | 66,985 (3.927074%) | 1,580,526 (92.660180%) |
| Medscape | 3,661,537 | 63,062 (1.722282%) | 69,605 (1.900978%) | 71,194 (1.944375%) | 393,209 (10.738906%) | 3,064,467 (83.693460%) |
| Endato | 5,427,459 | 24,903 (0.458833%) | 106,694 (1.965819%) | 32,259 (0.594367%) | 329,557 (6.072031%) | 4,934,046 (90.908950%) |
| RocketReach | 3,199,535 | 17,349 (0.542235%) | 20,480 (0.640093%) | 18,987 (0.593430%) | 73,947 (2.311180%) | 3,068,772 (95.913062%) |
| DRDB | 826,886 | 7,191 (0.869648%) | 8,005 (0.968090%) | 8,632 (1.043917%) | 36,639 (4.430961%) | 766,419 (92.687384%) |
| Haymarket | 4,223,245 | 48,801 (1.155533%) | 54,457 (1.289459%) | 55,569 (1.315789%) | 228,176 (5.402860%) | 3,836,242 (90.836359%) |

Emails whose UIDs have tied or multi-state primary evidence (distinct emails; links of one email share this evidence):

| Source | Links | Distinct emails | Emails with tied-primary-state UIDs | Emails with multi-state UIDs |
|---|---|---|---|---|
| HealthLink | 7,688,451 | 7,688,331 | 6,542 | 83,588 |
| QuantumMedica | 1,705,723 | 1,705,695 | 1,008 | 13,097 |
| Medscape | 3,661,537 | 3,551,989 | 4,794 | 62,587 |
| Endato | 5,427,459 | 5,324,318 | 4,250 | 52,336 |
| RocketReach | 3,199,535 | 3,163,679 | 1,011 | 13,103 |
| DRDB | 826,886 | 819,454 | 478 | 6,335 |
| Haymarket | 4,223,245 | 4,223,245 | 3,226 | 41,614 |

Links whose any-version and latest-version cookie vendor-state evidence differ (statement 4, links with a single latest version only):

| Source | Any-version evidence | Latest-version evidence | Links |
|---|---|---|---|
| Medscape | mixed_state_evidence | corroborated | 241 |
| Medscape | mixed_state_evidence | not_observed | 76 |
| Medscape | mixed_state_evidence | unknown_reference_state | 1 |
| Medscape | not_observed | unknown_reference_state | 6 |

The stored evidence invariant checks returned zero failures in every group. Location statuses partition the links within each source. Vendor-state and facility-state agreement are separate link-level outcomes. Date presence does not prove complete ingestion. Snapshot days can share upstream history and are not independent confirmations.

Between 4.1% (RocketReach) and 16.3% (Medscape) of links have an observed untied cookie state in the window, and 81.0% to 95.2% have no mapping at all. Where a vendor state is known, `not_observed` is the most frequent outcome in every source, ahead of `mixed_state_evidence` and `corroborated`. QuantumMedica and Haymarket have no vendor states, so all their observed links are `unknown_reference_state`; Haymarket's vendor snapshot (2021-07-06) is also far older than the cookie window. Only Medscape has links whose any-version and latest-version comparisons differ (324 links).

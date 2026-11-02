# Vendor state versus facility state

**Question:** do the vendor states reported for this link agree with its NPI’s preferred historical facility state?

**Target:** `vendor_state_evidence`, nullable `vendor_state_corroborated`, `facility_primary_state` and the latest-version companions `vendor_state_evidence_latest`, `vendor_state_corroborated_latest` and `source_state_values_latest` in `iceberg.jteixeira_ipa.pii__int_<vendor>__metrics` and `iceberg.jteixeira_ipa.pii_clean`. One row per source/email/NPI link; key: `source`, `link_id`. `location_evidence_version` is `link_vendor_facility_state_v1`.

## How it is computed

Read rank-1 rows from `bq_bi.analytics_prod.npi_facility_locations_with_ids`; join `npi_facility_provider_npi` to the link's `npi`. Normalize `state_code` with the existing recognized US state/DC/territory mapping. Group by NPI before joining so duplicate reference rows never multiply links.

A reference is usable only when every rank-1 row has a nonblank location and a recognized state, with exactly one distinct state. Conflicting states, missing states, missing locations and absent associations remain explicit.

Compare the link's `source_state_values`, the union of recognized states across all versions of the link:

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

Because the unsuffixed columns use the union, a link whose versions report different states that include the reference is `mixed_vendor_states`. The `_latest` columns apply the same comparison to `source_state_values_latest`, the recognized states of the link's latest version (`latest_record_id`) only. All three `_latest` columns are NULL when the link has no single latest version.

HealthLink states come from its retained HCP reference by NPI, so its `_latest` columns equal the all-version columns. Other vendors use the states of the link's email-bearing versions. QuantumMedica has no usable states, and Haymarket has no state field. Unknowns stay unknown.

This mixed-source historical facility reference has no vendor-day alignment and can share vendor lineage. Agreement proves neither current attendance nor email ownership. Evaluation day defaults to Europe/Paris today; `location_evidence_day` fixes it.

## Real examples

Executed November 2, 2026, against `iceberg.jteixeira_ipa.pii_clean` snapshot `2837737034249693554`. These selected cases explain outcomes; they do not measure prevalence.

```sql
SELECT source, email, npi, record_count,
       source_state_values, facility_primary_state, facility_reference_status,
       vendor_state_evidence, vendor_state_corroborated,
       source_state_values_latest, vendor_state_evidence_latest
FROM iceberg.jteixeira_ipa.pii_clean
WHERE ROW(source, link_id) IN (
    ROW('healthlink', '000003E1464D72618D55F78C6D464B854F2B8213906F0546468EE5C189A1376A'),
    ROW('healthlink', '000003EF65550016D15786DAA9351C829F608354411ECD4C845B5E20C1276CC8'),
    ROW('healthlink', '000276940C02CE657B3BB55C27EDDEDC7F5826B6B1895076A8AC78F5B0712168'),
    ROW('medscape', '004871A9253F92B698DB560F8B63E34B5CF596BE7B820F4CC1EA9326AB7253E4'),
    ROW('medscape', '005E7C57737A0CD7FF8C4CA6A55BA7050BCCD2E9509B6377E7B2CB8566D0BB0B'),
    ROW('medscape', '243824654BF7631DFFC66DD52343ADCD1EC9EFD89C8914990D977F2CBE456038'),
    ROW('endato', '00000359411756A423CF6FA62F7ADEA5FAF7F0213AB36334DF4DE1CD16782DF9'),
    ROW('quantummedica', '00000DDB36714AA722CCD60CF05FFB422CA04FFF54E4FD4B9F69FE63FA168F87'))
ORDER BY source, link_id
```

| source | email | npi | record_count | source_state_values | facility_primary_state | facility_reference_status | vendor_state_evidence | vendor_state_corroborated | source_state_values_latest | vendor_state_evidence_latest |
|---|---|---|---|---|---|---|---|---|---|---|
| endato | hhutch2@gmail.com | 1922407774 | 1 | [TX] | NULL | no_rank1_association | unknown_facility | NULL | [TX] | unknown_facility |
| healthlink | csteele@hotmail.com | 1720286941 | 3 | [TX] | TX | usable | corroborated | true | [TX] | corroborated |
| healthlink | jnance219676@cookchildrens.direct-ci.com | 1770745390 | 1 | [CO] | TX | usable | not_corroborated | false | [CO] | not_corroborated |
| healthlink | shandymcdonald@yahoo.com | 1932546124 | 3 | [LA, TN] | TN | usable | mixed_vendor_states | NULL | [LA, TN] | mixed_vendor_states |
| medscape | iamwxx@gmail.com | 1114416583 | 2 | [IL, NC] | NC | usable | mixed_vendor_states | NULL | [NC] | corroborated |
| medscape | cprokos2@pol.net | 1205838166 | 3 | [FL, NC, VA] | VA | usable | mixed_vendor_states | NULL | [NC] | not_corroborated |
| medscape | louisandjanet@gmail.com | 1003362633 | 2 | [TN] | TN | usable | corroborated | true | NULL | NULL |
| quantummedica | lois.kramer@yahoo.com | 1952381295 | 1 | [] | AZ | usable | unknown_vendor_state | NULL | [] | unknown_vendor_state |

**What differentiates these cases:** `csteele@hotmail.com` has one vendor state, TX, equal to the usable facility state, so the evidence is `corroborated` and the flag is true. `jnance219676@cookchildrens.direct-ci.com` reports CO against a TX facility state, so it is `not_corroborated` and false. `shandymcdonald@yahoo.com` reports LA and TN across its versions; the union includes the facility state TN but is not a single state, so the evidence is `mixed_vendor_states` and the flag stays NULL. The two Medscape multi-version links show how the latest version resolves a mixture: `iamwxx@gmail.com` reports IL and NC over time and its latest version reports only NC (`corroborated`), while `cprokos2@pol.net` reports FL, NC and VA and its latest version reports only NC, which excludes the facility state VA (`not_corroborated`). `louisandjanet@gmail.com` has two versions and no single latest version, so every `_latest` column is NULL. Endato `hhutch2@gmail.com` has a vendor state but no rank-1 facility association (`unknown_facility`), and QuantumMedica `lois.kramer@yahoo.com` has a usable facility state but no vendor state (`unknown_vendor_state`). None proves current attendance.

## Statistics by source

Measured **November 2, 2026** from `iceberg.jteixeira_ipa.pii_clean` snapshot `2837737034249693554`. These are exact published-population counts across retained eligible history, not a sample.

Source data period (first and last observed day): HealthLink 2026-01-07 to 2026-10-03, QuantumMedica 2025-09-14 to 2026-10-15, Medscape 2024-01-10 to 2026-11-01 and Haymarket 2021-07-06 (one snapshot day). Endato, RocketReach and DRDB are undated.

[Statistics SQL 1](../../sql/statistics/18_vendor_facility_state.sql) · [Statistics SQL 2](../../sql/statistics/18_vendor_facility_state_statement_002.sql) · [Statistics SQL 3](../../sql/statistics/18_vendor_facility_state_statement_003.sql)

| Source | Links | corroborated, n (%) | not corroborated, n (%) | mixed vendor states, n (%) | unknown vendor state, n (%) | unknown facility, n (%) |
|---|---|---|---|---|---|---|
| HealthLink | 7,688,451 | 2,503,228 (32.558288%) | 255,735 (3.326223%) | 67,899 (0.883130%) | 2,652 (0.034493%) | 4,858,937 (63.197867%) |
| QuantumMedica | 1,705,723 | 0 (0.000000%) | 0 (0.000000%) | 0 (0.000000%) | 786,246 (46.094589%) | 919,477 (53.905411%) |
| Medscape | 3,661,537 | 795,819 (21.734561%) | 449,741 (12.282847%) | 1,515 (0.041376%) | 50,354 (1.375215%) | 2,364,108 (64.566001%) |
| Endato | 5,427,459 | 698,206 (12.864326%) | 955,438 (17.603781%) | 0 (0.000000%) | 472 (0.008697%) | 3,773,343 (69.523197%) |
| RocketReach | 3,199,535 | 898,375 (28.078299%) | 151,587 (4.737782%) | 0 (0.000000%) | 167,985 (5.250294%) | 1,981,588 (61.933625%) |
| DRDB | 826,886 | 261,532 (31.628544%) | 36,661 (4.433622%) | 153 (0.018503%) | 0 (0.000000%) | 528,540 (63.919331%) |
| Haymarket | 4,223,245 | 0 (0.000000%) | 0 (0.000000%) | 0 (0.000000%) | 1,779,285 (42.130755%) | 2,443,960 (57.869245%) |

Percentages use all links and partition each source population. Mixed evidence and missing evidence remain NULL for the boolean agreement flag. The stored evidence invariant checks returned zero failures in every source and outcome group. Of the unknown-facility links, only 34 across all sources have a `missing_state` reference; the rest have no rank-1 association for the NPI.

Links whose any-version and latest-version evidence differ (statement 3, links with a single latest version only):

| Source | Any-version evidence | Latest-version evidence | Links |
|---|---|---|---|
| Medscape | corroborated | unknown_vendor_state | 4 |
| Medscape | mixed_vendor_states | corroborated | 1,359 |
| Medscape | mixed_vendor_states | not_corroborated | 156 |
| Medscape | not_corroborated | unknown_vendor_state | 3 |

HealthLink latest columns equal its all-version columns. No other source has a differing link among links with a single latest version.

Unknown facility is the largest outcome in every source, from 53.9% (QuantumMedica) to 69.5% (Endato). QuantumMedica and Haymarket have no recognized vendor states, so none of their links is corroborated or not corroborated. Among links with both a usable facility state and a known vendor state, the share corroborated is 90.7% for HealthLink, 87.7% for DRDB, 85.6% for RocketReach, 63.9% for Medscape and 42.2% for Endato. All 1,515 Medscape links with mixed any-version evidence have a single latest version, and it resolves 1,359 of them to `corroborated` and 156 to `not_corroborated`. Geographic agreement does not establish attendance or ownership.

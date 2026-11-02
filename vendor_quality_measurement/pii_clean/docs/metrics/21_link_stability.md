# 21. Link stability

Stability describes a reported link's presence and overlap across a vendor's dated email history. It does not establish ownership, switching frequency or independent confirmation.

## How it is computed

The [macro](../../macros/link_stability.sql) counts distinct `observed_days` of each `source/email/npi` link, which already unions the days of all its versions. The email denominator unions days across every NPI for that `source/email`. Distinct `conflict_days` count days when this link accompanied another NPI. Repeated versions and email positions do not increase these counts. The columns are appended to each link in `iceberg.jteixeira_ipa.pii_clean`.

| Stored column | Meaning |
|---|---|
| `email_observed_day_count` | Distinct known days for the vendor/email across all NPIs. |
| `link_observed_day_count` | Distinct known days for this vendor/email/NPI. |
| `link_conflict_day_count` | Distinct known days this link overlapped another NPI. |
| `link_presence_share` | Link days divided by email days. |
| `link_overlap_share` | Conflict days divided by link days. |
| `link_stability_has_undated_observations` | Any link for this vendor/email, including peer NPIs, has undated or invalid-day observations. |

Shares are fractions from 0 to 1; multiply by 100 for percentages. Presence shares across NPIs can sum above 100% because days overlap. Several competing NPIs on one day still contribute only one conflict day. A link with no dated observations has zero link/conflict day counts and NULL shares. Its email-day denominator can still be positive when another NPI supplies dated email history. Mixed histories retain shares over known days and flag incomplete coverage. Missing calendar days are not inferred. All stored parsed dates participate; stability applies no evaluation-day filter.

## Real examples

Executed November 2, 2026, against `iceberg.jteixeira_ipa.pii_clean` snapshot `2837737034249693554`. These selected cases explain outcomes; they do not measure prevalence.

```sql
SELECT source, email, npi, email_observed_day_count, link_observed_day_count,
       link_conflict_day_count, link_presence_share, link_overlap_share,
       link_stability_has_undated_observations
FROM iceberg.jteixeira_ipa.pii_clean
WHERE ROW(source, link_id) IN (
    ROW('haymarket', '000001F7A2912A5F067399B37D6E035976692BB806F3C0D9BFEE46B2319F5867'),
    ROW('healthlink', '011A4E3469D63171B176507DBDB51E1A4A7FE27976A32920F81AB683684A4A21'),
    ROW('medscape', '0AF4CA4655666D06E21F300BD4D296CFBE6BF922886EB5E5A06691C543743B03'),
    ROW('medscape', '07F90157AC8FA07254DD4BF552EB4E4AEF27B83FDB65D97827B7FCDB7E7324A7'),
    ROW('medscape', '4AC7E03D58C982D74C164A9AB653C77BA18CCA102D3AA4D7565653E26E421889'),
    ROW('quantummedica', '0411C6CA8D68C5ABE8FECFA3D00029BF7C461C8356B3A7AEB7A336877F30F528'),
    ROW('endato', '00000359411756A423CF6FA62F7ADEA5FAF7F0213AB36334DF4DE1CD16782DF9'))
ORDER BY source, link_id
```

| source | email | npi | email_observed_day_count | link_observed_day_count | link_conflict_day_count | link_presence_share | link_overlap_share | link_stability_has_undated_observations |
|---|---|---|---|---|---|---|---|---|
| endato | hhutch2@gmail.com | 1922407774 | 0 | 0 | 0 | NULL | NULL | true |
| haymarket | ejshim41@yahoo.com | 1104930056 | 1 | 1 | 0 | 1.0000 | 0.0000 | false |
| healthlink | kchuang@memorialcare.org | 1205998929 | 30 | 29 | 0 | 0.9667 | 0.0000 | false |
| medscape | usmanayubkhan@gmail.com | 1346658416 | 4 | 3 | 2 | 0.7500 | 0.6667 | false |
| medscape | srd1448@aol.com | 1790703072 | 362 | 3 | 3 | 0.0083 | 1.0000 | false |
| medscape | andrewsj2@gmail.com | 1548321714 | 3 | 3 | 3 | 1.0000 | 1.0000 | false |
| quantummedica | kshahzad@wwbh.org | 1407056278 | 11 | 11 | 11 | 1.0000 | 1.0000 | false |

**What differentiates these cases:** Haymarket `ejshim41@yahoo.com` is present on its only day, so presence is 1 with no overlap, which supplies little history. HealthLink `kchuang@memorialcare.org` was present on 29 of the email's 30 days (presence 0.9667) with no overlap. Medscape `usmanayubkhan@gmail.com` shows partial presence (3 of 4 email days) and partial overlap (2 of its 3 days alongside another NPI). Medscape `srd1448@aol.com` was present on 3 of the email's 362 days (presence 0.0083), and every one of those days had another NPI (overlap 1). Medscape `andrewsj2@gmail.com` and QuantumMedica `kshahzad@wwbh.org` appear on every email day and overlap on every link day. Endato `hhutch2@gmail.com` is undated: its counts are zero, its shares are NULL and `link_stability_has_undated_observations` is true, rather than a measured zero stability.

## Statistics by source

Measured **November 2, 2026** from `iceberg.jteixeira_ipa.pii_clean` snapshot `2837737034249693554`. These are exact published-population counts across retained eligible history, not a sample.

Source data period (first and last observed day): HealthLink 2026-01-07 to 2026-10-03, QuantumMedica 2025-09-14 to 2026-10-15, Medscape 2024-01-10 to 2026-11-01 and Haymarket 2021-07-06 (one snapshot day). Endato, RocketReach and DRDB are undated.

[Statistics SQL](../../sql/statistics/21_link_stability.sql)

| Source | Links | dated links, n (%) | single-day links, n (% of links) | full presence, n (% of dated) | mean presence (% of dated) | with overlap, n (% of dated) | overlap on every day, n (% of dated) | mean overlap (% of dated) | max link days |
|---|---|---|---|---|---|---|---|---|---|
| HealthLink | 7,688,451 | 7,688,451 (100.000000%) | 1,223,374 (15.911840%) | 7,688,211 (99.996878%) | 99.998439% | 0 (0.000000%) | 0 (0.000000%) | 0.000000% | 245 |
| QuantumMedica | 1,705,723 | 1,705,723 (100.000000%) | 1,087 (0.063727%) | 1,705,722 (99.999941%) | 99.999989% | 56 (0.003283%) | 55 (0.003224%) | 0.003272% | 11 |
| Medscape | 3,661,537 | 3,661,537 (100.000000%) | 39,329 (1.074112%) | 3,442,461 (94.016830%) | 97.008252% | 32 (0.000874%) | 11 (0.000300%) | 0.000504% | 394 |
| Endato | 5,427,459 | 0 (0.000000%) | 0 (0.000000%) | — | — | — | — | — | 0 |
| RocketReach | 3,199,535 | 0 (0.000000%) | 0 (0.000000%) | — | — | — | — | — | 0 |
| DRDB | 826,886 | 0 (0.000000%) | 0 (0.000000%) | — | — | — | — | — | 0 |
| Haymarket | 4,223,245 | 4,223,245 (100.000000%) | 4,223,245 (100.000000%) | 4,223,245 (100.000000%) | 100.000000% | 0 (0.000000%) | 0 (0.000000%) | 0.000000% | 1 |

Presence and overlap percentages use dated links. A zero dated denominator is undefined (—), not zero stability. Means weight each dated link equally. One-day histories can show full presence without sufficient sequential history. Distinct links within each source remain separate from globally unique people.

For Endato, RocketReach and DRDB every link is undated and every link has `link_stability_has_undated_observations` true. The dated sources have no incomplete email dates. Haymarket links are all single-day, so its 100% presence carries no history, and 15.9% of HealthLink links are also single-day. Overlap with a competing NPI is rare among dated sources: none of HealthLink's links, 32 of Medscape's (11 on every observed day) and 56 of QuantumMedica's (55 on every observed day). Medscape has the lowest full-presence share among dated sources, 94.0% of links, against 99.997% for HealthLink.

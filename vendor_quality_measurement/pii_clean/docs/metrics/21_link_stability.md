# 21. Link stability

Stability describes a reported link's presence and overlap across a vendor's dated email history. It does not establish ownership, switching frequency or independent confirmation.

## How it is computed

The [macro](../../macros/link_stability.sql) unions distinct `observed_days` across records within each `source/email/npi`. The email denominator unions days across every NPI for that `source/email`. Distinct `conflict_days` count days when this link accompanied another NPI. Repeated records and email positions do not increase these counts. Original rows remain intact in `iceberg.jteixeira_ipa.pii_clean`.

| Stored column | Meaning |
|---|---|
| `email_observed_day_count` | Distinct known days for the vendor/email across all NPIs. |
| `link_observed_day_count` | Distinct known days for this vendor/email/NPI. |
| `link_conflict_day_count` | Distinct known days this link overlapped another NPI. |
| `link_presence_share` | Link days divided by email days. |
| `link_overlap_share` | Conflict days divided by link days. |
| `link_stability_has_undated_observations` | Any record for this vendor/email, including peer NPIs, has undated or invalid-day observations. |

Shares are fractions from 0 to 1; multiply by 100 for percentages. Presence shares across NPIs can sum above 100% because days overlap. Several competing NPIs on one day still contribute only one conflict day. A link with no dated observations has zero link/conflict day counts and NULL shares. Its email-day denominator can still be positive when another NPI supplies dated email history. Mixed histories retain shares over known days and flag incomplete coverage. Missing calendar days are not inferred. All stored parsed dates participate; stability applies no evaluation-day filter.

## Real examples

Executed October 31, 2026, against canonical snapshot `8811920360682490090`. These selected cases explain outcomes; they do not measure prevalence.

[Executed example SQL](../../sql/examples/21_link_stability.sql):

```sql
WITH selected AS (
    SELECT *
    FROM iceberg.jteixeira_ipa.pii_clean FOR VERSION AS OF 8811920360682490090
    WHERE (source = 'endato' AND metric_row_id IN (
        'DC0EE0243F487695065E208BC5A960451759587FB3772AA025AAB99774C9E822'))
       OR (source = 'haymarket' AND metric_row_id IN (
        '9DF2E9F9E7A4ECB5EE6C33558A69F6F91B5222D322F1CDB70BE08D0EE1FB82DC'))
       OR (source = 'healthlink' AND metric_row_id IN (
        'FFBCB6093266218722EB50FD8749ED16173B42DAB91D463CDF515A029E43C3FD'))
       OR (source = 'medscape' AND metric_row_id IN (
        '823B6E80C0F4F8F215E7B4CD725A91595A9EE54607E1B167FBCDC8FC54C43AC2'))
       OR (source = 'quantummedica' AND metric_row_id IN (
        '3E55BDBA7BCA37D1F8B9FEE233B0C71869874E3238FC9A78785DBE2DB8224C30'))
)
SELECT m.source,
       m.email,
       m.npi,
       m.email_observed_day_count AS email_days,
       m.link_observed_day_count AS link_days,
       m.link_conflict_day_count AS conflict_days,
       round(100e0 * m.link_presence_share, 2) AS presence_pct,
       round(100e0 * m.link_overlap_share, 2) AS overlap_pct,
       m.link_stability_has_undated_observations AS incomplete_dates
FROM selected m
ORDER BY m.source, m.metric_row_id
```

| source | email | npi | email_days | link_days | conflict_days | presence_pct | overlap_pct | incomplete_dates |
|---|---|---|---|---|---|---|---|---|
| endato | charlene513@yahoo.com | 1568013472 | 0 | 0 | 0 | NULL | NULL | true |
| haymarket | amaslo@yahoo.com | 1962472621 | 1 | 1 | 0 | 100 | 0 | false |
| healthlink | jyee@kaiserpermanente.org | 1033597679 | 30 | 29 | 0 | 96.67 | 0 | false |
| medscape | fangchenmd@gmail.com | 1407193790 | 6 | 4 | 3 | 66.67 | 75 | false |
| quantummedica | gregory@giconsultants.com | 1619953403 | 11 | 11 | 11 | 100 | 100 | false |

**What differentiates these cases:** Full presence over one day supplies little history. Partial presence without overlap differs from appearing on every day alongside a competing NPI. A link can also have both partial presence and overlap. Undated links have zero known-day counts and NULL shares, rather than measured zero stability.

## Statistics by source

Measured **October 31, 2026** from `iceberg.jteixeira_ipa.pii_clean` snapshot `8811920360682490090`. These are exact published-population counts across retained eligible history, not a sample. Stored evaluation dates remain unchanged.

[Executed statistics SQL](../../sql/statistics/21_link_stability.sql)

| Source | Email/NPI links | Dated links | One email-day links | Full presence / dated, n (%) | Any overlap / dated, n (%) | Mean presence / overlap % |
|---|---|---|---|---|---|---|
| HealthLink | 7,688,451 | 7,688,451 | 1,223,251 | 7,688,211 (99.996878%) | 0 (0.000000%) | 99.998439 / 0 |
| QuantumMedica | 1,705,723 | 1,705,723 | 1,087 | 1,705,722 (99.999941%) | 56 (0.003283%) | 99.999989 / 0.003272 |
| Medscape | 3,659,659 | 3,659,659 | 30,734 | 3,441,079 (94.027312%) | 32 (0.000874%) | 97.013493 / 0.000504 |
| Endato | 5,427,459 | 0 | 0 | 0 (—) | 0 (—) | NULL / NULL |
| RocketReach | 3,199,535 | 0 | 0 | 0 (—) | 0 (—) | NULL / NULL |
| DRDB | 826,886 | 0 | 0 | 0 (—) | 0 (—) | NULL / NULL |
| Haymarket | 4,223,245 | 4,223,245 | 4,223,245 | 4,223,245 (100.000000%) | 0 (0.000000%) | 100 / 0 |

Presence and overlap percentages use dated links. A zero dated denominator is undefined (—), not zero stability. Means weight each dated link equally. One-day histories can show full presence without sufficient sequential history. Distinct links within each source remain separate from globally unique people.

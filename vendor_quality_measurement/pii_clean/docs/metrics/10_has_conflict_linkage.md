# Has conflict linkage

**Principle:** flag competing reported NPIs at the same observation time, within one vendor/email. Output: nullable boolean `has_conflict_linkage`, one value per link, in `iceberg.jteixeira_ipa.pii__int_<vendor>__metrics` and `iceberg.jteixeira_ipa.pii_clean`.

## How it is computed

For dated vendors, count distinct NPIs within `source`, `email`, actual delivery day, using each link's `observed_days` across all its versions. Collect days with more than one NPI into `email_conflict_days`, then keep only days observed for this link:

```sql
count(DISTINCT npi) AS daily_npi_count
```

```sql
array_sort(array_intersect(observed_days, email_conflict_days)) AS conflict_days
```

Endato, RocketReach and DRDB compare all current links within each vendor, including both DRDB inputs. This assumes comparability, not a common collection date.

```sql
CASE WHEN source IN ('endato', 'rocketreach', 'drdb') THEN email_npi_count > 1
     WHEN cardinality(conflict_days) > 0 THEN true
     WHEN email_npi_count = 1 THEN false
     WHEN undated_observation_count > 0 THEN NULL
     ELSE false
END AS has_conflict_linkage
```

Repeated deliveries of one NPI do not create conflict. Unknown days in dated vendors remain unknown; date ranges are never expanded.

A link can span many days and several versions. `conflict_days` lists exactly which of the link's `observed_days` conflict; any such day makes its flag true. Undated-vendor conflicts have an empty `conflict_days` array. A conflict may reflect a shared mailbox or reporting error; it does not identify the correct NPI. All links remain in the table.

## Real examples

Executed November 2, 2026, against `iceberg.jteixeira_ipa.pii_clean` snapshot `2837737034249693554`. These selected cases explain outcomes; they do not measure prevalence.

```sql
SELECT source, email, npi, record_count, email_npi_count,
       cardinality(observed_days) AS observed_day_count,
       cardinality(conflict_days) AS conflict_day_count,
       has_been_reassigned, has_conflict_linkage
FROM iceberg.jteixeira_ipa.pii_clean
WHERE (source = 'healthlink' AND link_id IN ('011A4E3469D63171B176507DBDB51E1A4A7FE27976A32920F81AB683684A4A21'))
   OR (source = 'quantummedica' AND link_id IN ('0411C6CA8D68C5ABE8FECFA3D00029BF7C461C8356B3A7AEB7A336877F30F528'))
   OR (source = 'medscape' AND link_id IN ('07F90157AC8FA07254DD4BF552EB4E4AEF27B83FDB65D97827B7FCDB7E7324A7', '4C7468EBC1D99D7914693F0F05ED57FF0F55BDBF5DC6277B2801FC795FED5D19'))
   OR (source = 'endato' AND link_id IN ('0000D99684BF16BE7602BA1F9A425F5BAC8E6AC57A0EA41D47F76C41805EA27A'))
   OR (source = 'haymarket' AND link_id IN ('000001F7A2912A5F067399B37D6E035976692BB806F3C0D9BFEE46B2319F5867'))
ORDER BY source, link_id
```

| source | email | npi | record_count | email_npi_count | observed_day_count | conflict_day_count | has_been_reassigned | has_conflict_linkage |
|---|---|---|---|---|---|---|---|---|
| endato | ppaulaj7i20@verizon.net | 1871569921 | 1 | 2 | 0 | 0 | NULL | true |
| haymarket | ejshim41@yahoo.com | 1104930056 | 1 | 1 | 1 | 0 | false | false |
| healthlink | kchuang@memorialcare.org | 1205998929 | 1 | 2 | 29 | 0 | true | false |
| medscape | usmanayubkhan@gmail.com | 1346658416 | 1 | 2 | 3 | 2 | true | true |
| medscape | pawnking4@netscape.net | 1033420419 | 2 | 2 | 55 | 3 | true | true |
| quantummedica | kshahzad@wwbh.org | 1407056278 | 1 | 2 | 11 | 11 | false | true |

**What differentiates these cases:**

- **Reassignment without overlap:** the HealthLink email `kchuang@memorialcare.org` has two NPIs (`email_npi_count` 2) observed on different days, so it is reassigned. No day reports both NPIs, so `conflict_day_count` is 0 and the link is not in conflict.
- **Overlap on every observed day:** the QuantumMedica link for `kshahzad@wwbh.org` shares all 11 of its observed days with the other NPI. It is in conflict and the email is not reassigned.
- **Overlap on some days:** the Medscape link for `usmanayubkhan@gmail.com` conflicts on 2 of its 3 observed days. Any conflict day makes the flag true, and this email is also reassigned.
- **Several versions in one link:** the Medscape link for `pawnking4@netscape.net` and NPI `1033420419` merges 2 versions (`record_count` 2). Of its 55 observed days, 3 are conflict days.
- **Undated vendor:** the Endato link for `ppaulaj7i20@verizon.net` has no observed days and no conflict days, yet the flag is true because the other NPI of the email is a peer in the vendor snapshot. Reassignment is NULL for undated vendors.
- **Single NPI:** the Haymarket link has one NPI on one day, so it is false for both flags.

## Statistics by source

Measured **November 2, 2026** from `iceberg.jteixeira_ipa.pii_clean` snapshot `2837737034249693554`. These are exact published-population counts across retained eligible history, not a sample. Source data period (first to last observed day): HealthLink 2026-01-07 to 2026-10-03, QuantumMedica 2025-09-14 to 2026-10-15, Medscape 2024-01-10 to 2026-11-01 and Haymarket 2021-07-06 (a single day). Endato, RocketReach and DRDB are undated.

[Statistics SQL](../../sql/statistics/10_has_conflict_linkage.sql)

| Source | Distinct emails | True: emails, n (%) | Unknown: emails, n (%) | Links | True: links, n (%) | Unknown: links, n (%) |
|---|---|---|---|---|---|---|
| HealthLink | 7,688,331 | 0 (0.000000%) | 0 (0.000000%) | 7,688,451 | 0 (0.000000%) | 0 (0.000000%) |
| QuantumMedica | 1,705,695 | 28 (0.001642%) | 0 (0.000000%) | 1,705,723 | 56 (0.003283%) | 0 (0.000000%) |
| Medscape | 3,551,989 | 16 (0.000450%) | 0 (0.000000%) | 3,661,537 | 32 (0.000874%) | 0 (0.000000%) |
| Endato | 5,324,318 | 91,841 (1.724935%) | 0 (0.000000%) | 5,427,459 | 194,982 (3.592510%) | 0 (0.000000%) |
| RocketReach | 3,163,679 | 29,990 (0.947947%) | 0 (0.000000%) | 3,199,535 | 65,846 (2.057987%) | 0 (0.000000%) |
| DRDB | 819,454 | 7,400 (0.903040%) | 0 (0.000000%) | 826,886 | 14,832 (1.793718%) | 0 (0.000000%) |
| Haymarket | 4,223,245 | 0 (0.000000%) | 0 (0.000000%) | 4,223,245 | 0 (0.000000%) | 0 (0.000000%) |

Email percentages use distinct source/emails; link percentages use the source's links. Email-level conflict means at least one conflicting link. No source has links with unknown conflict status. Unknown chronology remains separate from false.

Conflicts are rare in the dated vendors (QuantumMedica 0.001642% of emails, Medscape 0.000450%) and absent in HealthLink and Haymarket. The undated vendors, where every other NPI of an email is a peer, have far higher rates: Endato 1.724935%, RocketReach 0.947947% and DRDB 0.903040% of emails. Haymarket has one NPI per email, so no conflict is possible.

Reassignment and conflict overlap only rarely. Reassignment (`has_been_reassigned`) is NULL for undated vendors:

| Source | Distinct emails | Reassigned emails, n (%) | Reassigned and conflicting emails |
|---|---|---|---|
| HealthLink | 7,688,331 | 120 (0.001561%) | 0 |
| QuantumMedica | 1,705,695 | 1 (0.000059%) | 1 |
| Medscape | 3,551,989 | 109,537 (3.083821%) | 15 |
| Endato | 5,324,318 | unknown for every email (undated) | 0 |
| RocketReach | 3,163,679 | unknown for every email (undated) | 0 |
| DRDB | 819,454 | unknown for every email (undated) | 0 |
| Haymarket | 4,223,245 | 0 (0.000000%) | 0 |

Medscape has 109,537 reassigned emails, of which 15 also have conflicting links; 16 Medscape emails have conflicts in total.

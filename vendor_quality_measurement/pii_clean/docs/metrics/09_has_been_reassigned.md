# Has been reassigned

**Principle:** detect changes in the reported NPI set between observed days, within one vendor/email. This is an email-history flag: every link of the email receives the same value, including links preceding the change.

**Where:** `iceberg.jteixeira_ipa.pii__int_<vendor>__metrics` and `iceberg.jteixeira_ipa.pii_clean`. Inputs: `source`, `email`, `npi`, each link's exact `observed_days` (all versions combined) and `undated_observation_count`. Output: nullable boolean `has_been_reassigned`.

## How it is computed

For each vendor/email/day, collect the distinct NPIs of the email's links observed that day into a sorted set. Compare those sets across the email's observed days:

```sql
array_sort(array_agg(DISTINCT npi)) AS daily_npis
```

```sql
count(DISTINCT daily_npis) > 1 AS observed_reassignment
```

`undated_link_count` counts this vendor/email's links with any unknown observation day. Apply the following rule to every link of the email:

```sql
CASE WHEN observed_reassignment THEN true
     WHEN email_npi_count = 1 THEN false
     WHEN undated_link_count > 0 THEN NULL
     ELSE false
END AS has_been_reassigned
```

Endato, RocketReach and DRDB have no delivery days: multiple NPIs give unknown reassignment; one NPI gives false.

Set additions, removals and replacements qualify; this is evidence of changing attribution, not proof of mailbox ownership transfer. Changes in a link's other attributes, visible in `attribute_versions`, do not count. Calendar gaps are not filled. No cross-vendor comparisons apply.

## Real examples

Executed November 2, 2026, against `iceberg.jteixeira_ipa.pii_clean` snapshot `2837737034249693554`. These selected cases explain outcomes; they do not measure prevalence.

```sql
SELECT source,
       email,
       npi,
       first_seen_day,
       last_seen_day,
       observed_day_count,
       email_npi_count,
       has_been_reassigned,
       has_conflict_linkage
FROM iceberg.jteixeira_ipa.pii_clean FOR VERSION AS OF 2837737034249693554
WHERE (source = 'healthlink' AND link_id IN (
        'C5F34031C769F50280D7584026359729A8A746E31FA56A2C94BC8756BCF61F1F',
        '033BE528CA96A246F6251114B35F64A068E0854D04DE30448F93CC41A1D46164'))
   OR (source = 'medscape' AND link_id IN (
        'F5C0A5D1592D591447787CB36A5262FD287FC9301625E5CEB94581C50E1DBB61',
        '4AC7E03D58C982D74C164A9AB653C77BA18CCA102D3AA4D7565653E26E421889',
        '1751963BAF7F8719CCA77175665E582725B05C7D006D4915E13AA17C79DEFAF9',
        '8E7CCB45B25A14598EA076D2FEC6D4B5B8040E4D252BA5C874882F4DFC98273A'))
   OR (source = 'endato' AND link_id IN (
        'AE47F819A5A9000EAC3F944C0984B82D3960791FBEBEC7A5157F907159A96A74',
        'B2EE7EB17BD10D42AD661D1F6895980502E3B4BEFE5317F66492E8A38983BE27'))
ORDER BY source, email, npi
```

| source | email | npi | first_seen_day | last_seen_day | observed_day_count | email_npi_count | has_been_reassigned | has_conflict_linkage |
|---|---|---|---|---|---|---|---|---|
| endato | 01pbaker@gmail.com | 1639231517 | NULL | NULL | NULL | 2 | NULL | true |
| endato | 01pbaker@gmail.com | 1811340664 | NULL | NULL | NULL | 2 | NULL | true |
| healthlink | aahmed@adena.org | 1306541529 | 2026-01-07 | 2026-01-07 | 1 | 2 | true | false |
| healthlink | aahmed@adena.org | 1376258277 | 2026-02-02 | 2026-10-03 | 244 | 2 | true | false |
| medscape | andrewsj2@gmail.com | 1134484942 | 2024-01-10 | 2024-03-07 | 3 | 2 | false | true |
| medscape | andrewsj2@gmail.com | 1548321714 | 2024-01-10 | 2024-03-07 | 3 | 2 | false | true |
| medscape | cdknoblauch@comcast.net | 1194772020 | 2024-01-10 | 2024-05-10 | 5 | 2 | true | true |
| medscape | cdknoblauch@comcast.net | 1851492250 | 2024-01-10 | 2026-08-06 | 73 | 2 | true | true |

**What differentiates these cases:** `aahmed@adena.org` changes its NPI set between days (the first NPI appears on 2026-01-07, the second from 2026-02-02), so it is reassigned without a same-day conflict. `cdknoblauch@comcast.net` is reassigned and also has days on which both NPIs were reported (both flags true). `andrewsj2@gmail.com` reports the same two NPIs on every observed day, so reassignment is false although the conflict flag is true. `01pbaker@gmail.com` is undated with two competing NPIs, so reassignment is unknown (NULL), not false. Every link of an email carries the email's value, including the link whose days precede the change. Day counts describe coverage, not calendar continuity.

## Statistics by source

Measured **November 2, 2026** from `iceberg.jteixeira_ipa.pii_clean` snapshot `2837737034249693554`. These are exact published-population counts across retained eligible history, not a sample.

Source data period (first to last observed day): HealthLink 2026-01-07 to 2026-10-03; QuantumMedica 2025-09-14 to 2026-10-15; Medscape 2024-01-10 to 2026-11-01; Haymarket 2021-07-06 (a single day). Endato, RocketReach and DRDB are undated.

[Statistics SQL](../../sql/statistics/09_has_been_reassigned.sql) reports, per source, distinct emails, reassigned, not reassigned and unknown emails, and the links of reassigned and unknown emails.

| Source | Distinct emails | Reassigned emails, n (%) | Not reassigned emails, n (%) | Unknown emails, n (%) | Links of reassigned emails, n (%) | Links of unknown emails, n (%) |
|---|---:|---:|---:|---:|---:|---:|
| HealthLink | 7,688,331 | 120 (0.001561%) | 7,688,211 (99.998439%) | 0 (0.000000%) | 240 (0.003122%) | 0 (0.000000%) |
| QuantumMedica | 1,705,695 | 1 (0.000059%) | 1,705,694 (99.999941%) | 0 (0.000000%) | 2 (0.000117%) | 0 (0.000000%) |
| Medscape | 3,551,989 | 109,537 (3.083821%) | 3,442,452 (96.916179%) | 0 (0.000000%) | 219,084 (5.983389%) | 0 (0.000000%) |
| Endato | 5,324,318 | 0 (0.000000%) | 5,232,477 (98.275065%) | 91,841 (1.724935%) | 0 (0.000000%) | 194,982 (3.592510%) |
| RocketReach | 3,163,679 | 0 (0.000000%) | 3,133,689 (99.052053%) | 29,990 (0.947947%) | 0 (0.000000%) | 65,846 (2.057987%) |
| DRDB | 819,454 | 0 (0.000000%) | 812,054 (99.096960%) | 7,400 (0.903040%) | 0 (0.000000%) | 14,832 (1.793718%) |
| Haymarket | 4,223,245 | 0 (0.000000%) | 4,223,245 (100.000000%) | 0 (0.000000%) | 0 (0.000000%) | 0 (0.000000%) |

Email percentages use distinct source/emails; link percentages use the source's links. Unknown chronology remains separate from false.

Medscape has the most reassigned emails (109,537, 3.08%). HealthLink has 120 and QuantumMedica 1. Haymarket has none; every Haymarket email has one NPI. Endato, RocketReach and DRDB have no delivery days, so reassignment is false for single-NPI emails and unknown for every multi-NPI email: 91,841, 29,990 and 7,400 emails, matching their multi-NPI email counts in [multiplicity](08_email_npi_multiplicity.md).

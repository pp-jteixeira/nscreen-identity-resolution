# Email–NPI multiplicity

**Principle:** count how many distinct reported NPIs one vendor associates with an email across its retained history.

**Where:** `iceberg.jteixeira_ipa.pii__int_<vendor>__metrics` and `iceberg.jteixeira_ipa.pii_clean`. Inputs: `source`, cleaned `email`, trimmed `npi`. Outputs: `email_npi_count` and `email_has_multiple_npis`.

## How it is computed

Group retained links by `source`, `email` and count different nonempty, trimmed NPIs. Then flag counts above one:

```sql
count(DISTINCT npi) AS email_npi_count
```

```sql
email_npi_count > 1 AS email_has_multiple_npis
```

Every link for the same vendor/email receives the same count. Each link is one email–NPI pair, so the count equals the email's number of links within the vendor. Vendors are never pooled. DRDB's two inputs belong to one vendor. Versions, duplicate email slots and repeated dates cannot increase the distinct-NPI count. Missing email/NPI keys remain in staging; malformed nonempty NPIs still count because validity is a separate question.

Multiplicity does not distinguish historical changes from same-day conflicts or establish ownership. See [reassignment](09_has_been_reassigned.md) and [conflict](10_has_conflict_linkage.md).

## Real examples

Executed November 2, 2026, against `iceberg.jteixeira_ipa.pii_clean` snapshot `2837737034249693554`. These selected cases explain outcomes; they do not measure prevalence.

```sql
SELECT source,
       email,
       npi,
       email_npi_count,
       email_has_multiple_npis,
       first_seen_day,
       last_seen_day,
       observed_day_count,
       has_been_reassigned,
       has_conflict_linkage
FROM iceberg.jteixeira_ipa.pii_clean FOR VERSION AS OF 2837737034249693554
WHERE (source = 'healthlink' AND link_id IN (
        'C5F34031C769F50280D7584026359729A8A746E31FA56A2C94BC8756BCF61F1F',
        '033BE528CA96A246F6251114B35F64A068E0854D04DE30448F93CC41A1D46164',
        'FCFA5776B048950CD034ADAC4584157E4FE486AA4BDA96091AA56D34A4FD882C'))
   OR (source = 'medscape' AND link_id IN (
        'F5C0A5D1592D591447787CB36A5262FD287FC9301625E5CEB94581C50E1DBB61',
        '4AC7E03D58C982D74C164A9AB653C77BA18CCA102D3AA4D7565653E26E421889'))
   OR (source = 'endato' AND link_id IN (
        'AE47F819A5A9000EAC3F944C0984B82D3960791FBEBEC7A5157F907159A96A74',
        'B2EE7EB17BD10D42AD661D1F6895980502E3B4BEFE5317F66492E8A38983BE27'))
ORDER BY source, email, npi
```

| source | email | npi | email_npi_count | email_has_multiple_npis | first_seen_day | last_seen_day | observed_day_count | has_been_reassigned | has_conflict_linkage |
|---|---|---|---|---|---|---|---|---|---|
| endato | 01pbaker@gmail.com | 1639231517 | 2 | true | NULL | NULL | NULL | NULL | true |
| endato | 01pbaker@gmail.com | 1811340664 | 2 | true | NULL | NULL | NULL | NULL | true |
| healthlink | 0.crickett@att.net | 1023302569 | 1 | false | 2026-01-07 | 2026-10-03 | 245 | false | false |
| healthlink | aahmed@adena.org | 1306541529 | 2 | true | 2026-01-07 | 2026-01-07 | 1 | true | false |
| healthlink | aahmed@adena.org | 1376258277 | 2 | true | 2026-02-02 | 2026-10-03 | 244 | true | false |
| medscape | andrewsj2@gmail.com | 1134484942 | 2 | true | 2024-01-10 | 2024-03-07 | 3 | false | true |
| medscape | andrewsj2@gmail.com | 1548321714 | 2 | true | 2024-01-10 | 2024-03-07 | 3 | false | true |

**What differentiates these cases:** `aahmed@adena.org` has two NPIs in HealthLink: the first was delivered only on 2026-01-07 and the second from 2026-02-02 onward, without overlap, so the email is reassigned and has no conflict. `andrewsj2@gmail.com` has two NPIs in Medscape delivered on the same three days (2024-01-10 to 2024-03-07), so it is a conflict and not a reassignment. `01pbaker@gmail.com` has two NPIs in Endato, which has no delivery days: reassignment is unknown and the NPIs conflict. `0.crickett@att.net` has one NPI, so all three flags are false. Multiplicity alone (`email_has_multiple_npis`) is true for the first three emails and cannot tell these situations apart.

## Statistics by source

Measured **November 2, 2026** from `iceberg.jteixeira_ipa.pii_clean` snapshot `2837737034249693554`. These are exact published-population counts across retained eligible history, not a sample.

Source data period (first to last observed day): HealthLink 2026-01-07 to 2026-10-03; QuantumMedica 2025-09-14 to 2026-10-15; Medscape 2024-01-10 to 2026-11-01; Haymarket 2021-07-06 (a single day). Endato, RocketReach and DRDB are undated.

[Statistics SQL](../../sql/statistics/08_email_npi_multiplicity.sql) reports, per source, distinct emails, emails with multiple NPIs, affected links, the maximum NPIs per email and the distribution of NPIs per email.

| Source | Distinct emails | Links | Emails with multiple NPIs, n (%) | Links of those emails, n (%) | Maximum NPIs per email |
|---|---:|---:|---:|---:|---:|
| HealthLink | 7,688,331 | 7,688,451 | 120 (0.001561%) | 240 (0.003122%) | 2 |
| QuantumMedica | 1,705,695 | 1,705,723 | 28 (0.001642%) | 56 (0.003283%) | 2 |
| Medscape | 3,551,989 | 3,661,537 | 109,538 (3.083850%) | 219,086 (5.983444%) | 3 |
| Endato | 5,324,318 | 5,427,459 | 91,841 (1.724935%) | 194,982 (3.592510%) | 2,172 |
| RocketReach | 3,163,679 | 3,199,535 | 29,990 (0.947947%) | 65,846 (2.057987%) | 24 |
| DRDB | 819,454 | 826,886 | 7,400 (0.903040%) | 14,832 (1.793718%) | 5 |
| Haymarket | 4,223,245 | 4,223,245 | 0 (0.000000%) | 0 (0.000000%) | 1 |

**Distribution of NPIs per email (share of distinct emails)**

| Source | One NPI | Two NPIs | Three NPIs | Four NPIs | Five or more NPIs |
|---|---:|---:|---:|---:|---:|
| HealthLink | 7,688,211 (99.998439%) | 120 (0.001561%) | 0 (0.000000%) | 0 (0.000000%) | 0 (0.000000%) |
| QuantumMedica | 1,705,667 (99.998358%) | 28 (0.001642%) | 0 (0.000000%) | 0 (0.000000%) | 0 (0.000000%) |
| Medscape | 3,442,451 (96.916150%) | 109,528 (3.083568%) | 10 (0.000282%) | 0 (0.000000%) | 0 (0.000000%) |
| Endato | 5,232,477 (98.275065%) | 89,015 (1.671857%) | 2,423 (0.045508%) | 160 (0.003005%) | 243 (0.004564%) |
| RocketReach | 3,133,689 (99.052053%) | 26,762 (0.845914%) | 2,040 (0.064482%) | 586 (0.018523%) | 602 (0.019028%) |
| DRDB | 812,054 (99.096960%) | 7,371 (0.899501%) | 27 (0.003295%) | 1 (0.000122%) | 1 (0.000122%) |
| Haymarket | 4,223,245 (100.000000%) | 0 (0.000000%) | 0 (0.000000%) | 0 (0.000000%) | 0 (0.000000%) |

Email percentages use distinct emails within each source. Affected-link percentages use that source's links. Multiplicity does not identify overlap timing or ownership.

Haymarket has exactly one NPI for every email. Medscape has the largest share of multi-NPI emails (3.08%), almost all with two NPIs. Endato (1.72%), RocketReach (0.95%) and DRDB (0.90%) follow. HealthLink (120 emails) and QuantumMedica (28) have very few. The long tail sits in Endato, where one email is linked to 2,172 NPIs, and RocketReach, where the maximum is 24.

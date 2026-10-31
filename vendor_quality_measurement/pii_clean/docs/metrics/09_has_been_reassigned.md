# Has been reassigned

**Principle:** detect changes in the reported NPI set between observed days, within one vendor/email. This is an email-history flag: even records preceding the change receive `true`.

**Where:** `iceberg.jteixeira_ipa.pii__int_<vendor>__metrics` and `iceberg.jteixeira_ipa.pii_clean`. Inputs: `source`, `email`, `npi`, exact `observed_days` and `undated_observation_count`. Output: nullable boolean `has_been_reassigned`.

## How it is computed

For each vendor/email/day, collect the distinct NPIs into a sorted set. Compare those sets across the email's observed days:

```sql
array_sort(array_agg(DISTINCT npi)) AS daily_npis
```

```sql
count(DISTINCT daily_npis) > 1 AS observed_reassignment
```

`undated_record_count` counts this vendor/email's records with any unknown observation day. Apply the following rule to every row in its history:

```sql
CASE WHEN observed_reassignment THEN true
     WHEN email_npi_count = 1 THEN false
     WHEN undated_record_count > 0 THEN NULL
     ELSE false
END AS has_been_reassigned
```

Endato, RocketReach and DRDB have no delivery days: multiple NPIs give unknown reassignment; one NPI gives false.

Set additions, removals and replacements qualify; this is evidence of changing attribution, not proof of mailbox ownership transfer. Calendar gaps are not filled. No cross-vendor comparisons or row deduplication apply.

## Real examples

Executed October 31, 2026, against canonical snapshot `8811920360682490090`. These selected cases explain outcomes; they do not measure prevalence.

[Executed example SQL](../../sql/examples/09_has_been_reassigned.sql):

```sql
WITH selected AS (
    SELECT *
    FROM iceberg.jteixeira_ipa.pii_clean FOR VERSION AS OF 8811920360682490090
    WHERE (source = 'endato' AND metric_row_id IN (
        '01C4523510AD571FF0100E5AD6390B33758FCA91EA1A98BB39A1A47C4E5E54F3'))
       OR (source = 'healthlink' AND metric_row_id IN (
        'A881C610E7DFEE6D6B325E7584BE5A93D111097E21DA9F9614EF5D9BDBBD997D'))
       OR (source = 'quantummedica' AND metric_row_id IN (
        '5084F30B68BF7BE6EF578F1E2035E1868F1AD45605EB2542687E9AB72B88437D'))
)
SELECT m.source,
       m.email,
       m.npi,
       m.email_npi_count,
       m.observed_days,
       m.conflict_days,
       m.email_observed_day_count AS email_days,
       m.link_observed_day_count AS link_days,
       m.has_been_reassigned,
       m.has_conflict_linkage
FROM selected m
ORDER BY m.source, m.metric_row_id
```

| source | email | npi | email_npi_count | observed_days | conflict_days | email_days | link_days | has_been_reassigned | has_conflict_linkage |
|---|---|---|---|---|---|---|---|---|---|
| endato | tloan@yahoo.com | 1639195316 | 2 | [] | [] | 0 | 0 | NULL | true |
| healthlink | jjacobson@mchswecare.com | 1366933715 | 2 | [2026-10-03] | [] | 245 | 1 | true | false |
| quantummedica | pknudson@primecare.org | 1811935018 | 2 | [2025-09-14, 2025-10-15, 2025-11-15, 2025-12-15, 2026-01-15, 2026-02-15, 2026-03-15, 2026-04-15, 2026-06-15, 2026-09-15, 2026-10-15] | [2025-09-14, 2025-10-15, 2025-11-15, 2025-12-15, 2026-01-15, 2026-02-15, 2026-03-15, 2026-04-15, 2026-06-15, 2026-09-15, 2026-10-15] | 11 | 11 | false | true |

**What differentiates these cases:** Changing dated NPI sets gives reassignment true even without same-day conflict. A repeated conflicting set can remain false for reassignment. Undated competing NPIs establish conflict in the vendor snapshot but cannot establish chronological change. Day counts describe coverage, not calendar continuity.

## Statistics by source

Measured **October 31, 2026** from `iceberg.jteixeira_ipa.pii_clean` snapshot `8811920360682490090`. These are exact published-population counts across retained eligible history, not a sample. Stored evaluation dates remain unchanged.

[Executed statistics SQL](../../sql/statistics/09_has_been_reassigned.sql)

| Source | Distinct emails | True: emails, n (%) | Unknown: emails, n (%) | True: records, n (%) |
|---|---|---|---|---|
| HealthLink | 7,688,331 | 120 (0.001561%) | 0 (0.000000%) | 271 (0.002429%) |
| QuantumMedica | 1,705,695 | 1 (0.000059%) | 0 (0.000000%) | 2 (0.000117%) |
| Medscape | 3,550,359 | 109,289 (3.078252%) | 0 (0.000000%) | 2,359,930 (5.003629%) |
| Endato | 5,324,318 | 0 (0.000000%) | 91,841 (1.724935%) | 0 (0.000000%) |
| RocketReach | 3,163,679 | 0 (0.000000%) | 29,990 (0.947947%) | 0 (0.000000%) |
| DRDB | 819,454 | 0 (0.000000%) | 7,400 (0.903040%) | 0 (0.000000%) |
| Haymarket | 4,223,245 | 0 (0.000000%) | 0 (0.000000%) | 0 (0.000000%) |

Email percentages use distinct source/emails; record percentages use metric records. Email-level conflict means at least one conflicting record. Unknown chronology remains separate from false.

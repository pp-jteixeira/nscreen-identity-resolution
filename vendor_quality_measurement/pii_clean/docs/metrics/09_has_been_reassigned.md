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

**Illustrative examples:**

| Daily NPI sets | Reassigned | Interpretation |
|---|---|---|
| Day 1 `{A}`; day 2 `{B}` | true | Reported association changes. |
| Day 1 `{A}`; day 2 `{B,C}` | true | Reassignment and day-2 conflict coexist. |
| Day 1 `{A,B}`; day 2 `{A,B}` | false | Unchanged conflicting set. |
| Day 1 `{A}`; day 2 `{A,B}` | true | Adding an NPI changes the reported set. |
| Undated `{A,B}` | unknown | Order cannot be established. |

Set additions, removals and replacements qualify; this is evidence of changing attribution, not proof of mailbox ownership transfer. Calendar gaps are not filled. No cross-vendor comparisons or row deduplication apply.

## Statistics by vendor

[Statistics SQL](../../sql/statistics/09_has_been_reassigned.sql). This file preserves the executed read-only SQL behind these statistics, including the original measurement relation. Re-running it requires that relation and reference inputs; changing sources will change the results.

Historical baseline: `pii__evidence` was the measurement relation at the stated extraction time; it is outside the current managed build. This table is not a live population report. Medscape counts precede the October 29 population in the project README.

Measured **October 28, 2026**, on `iceberg.jteixeira_ipa.pii__evidence` across all retained source history. Exact counts; email percentages use each vendor's distinct emails, and row percentages use its metric rows. Extraction timestamp: `2026-10-28T21:27:21.738506+00:00`.

| Vendor | Reassigned emails, n (%) | Unknown emails, n (%) | Reassigned metric rows, n (%) |
|---|---:|---:|---:|
| HealthLink | 120 (0.00156%) | 0 (0.00000%) | 271 (0.00243%) |
| QuantumMedica | 1 (0.00006%) | 0 (0.00000%) | 2 (0.00012%) |
| Medscape | 109,146 (3.07495%) | 0 (0.00000%) | 2,351,014 (5.00414%) |
| Endato | 0 (0.00000%) | 91,841 (1.72493%) | 0 (0.00000%) |
| RocketReach | 0 (0.00000%) | 29,990 (0.94795%) | 0 (0.00000%) |
| DRDB | 0 (0.00000%) | 7,400 (0.90304%) | 0 (0.00000%) |
| Haymarket | 0 (0.00000%) | 0 (0.00000%) | 0 (0.00000%) |

Endato, RocketReach and DRDB have no dated history. Their multi-NPI emails are unknown for reassignment; the remaining emails have one retained NPI and are false.

Measured counts and executed SQL (local-only: `../../results/email_linkage_measurements.json`) · Native fixtures and preservation checks (local-only: `../../results/email_linkage_native_validation.json`)

[Profile SQL](../../sql/email_linkage_profile.sql) · [Independent chronological check](../../tests/email_linkage_history.sql) · [Conflict](10_has_conflict_linkage.md) · [Source date limitations](../00_source_map.md)

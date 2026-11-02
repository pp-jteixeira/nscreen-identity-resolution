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

No examples have been executed against this definition yet.

Cases worth contrasting: a dated email whose NPI set changes without same-day conflict (true), a dated email that repeats the same conflicting NPI set every day (false for reassignment, true for conflict), and an undated email with competing NPIs (unknown chronology). Day counts describe coverage, not calendar continuity.

## Statistics by source

No measurements exist yet for this definition. [Statistics SQL](../../sql/statistics/09_has_been_reassigned.sql) reports, per source, distinct emails, reassigned and unknown emails, and reassigned links.

Email percentages use distinct source/emails; link percentages use the source's links. Unknown chronology remains separate from false.

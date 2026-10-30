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

## Real examples: contrasting outcomes

Selected real records, queried October 30, 2026, from `iceberg.jteixeira_ipa.pii_clean` at snapshot `8096642935433856886`. These examples explain outcomes; they are not prevalence estimates. `email_key` is a shortened SHA-256 display label. Counts are stored distinct known-day denominators.

[Runnable example SQL](../../sql/examples/09_has_been_reassigned.sql):

```sql
WITH selected AS (
    SELECT *
    FROM iceberg.jteixeira_ipa.pii_clean FOR VERSION AS OF 8096642935433856886
    WHERE (source = 'endato' AND metric_row_id IN (
        '01C4523510AD571FF0100E5AD6390B33758FCA91EA1A98BB39A1A47C4E5E54F3'))
       OR (source = 'healthlink' AND metric_row_id IN (
        'A881C610E7DFEE6D6B325E7584BE5A93D111097E21DA9F9614EF5D9BDBBD997D'))
       OR (source = 'quantummedica' AND metric_row_id IN (
        '5084F30B68BF7BE6EF578F1E2035E1868F1AD45605EB2542687E9AB72B88437D'))
)
SELECT m.source,
       substr(to_hex(sha256(to_utf8(m.email))), 1, 12) AS email_key,
       m.email_npi_count,
       m.email_observed_day_count AS email_days,
       m.link_observed_day_count AS link_days,
       m.has_been_reassigned,
       m.has_conflict_linkage
FROM selected m
ORDER BY m.source, m.metric_row_id
```

**Result:** 3 rows.

| source | email_key | email_npi_count | email_days | link_days | has_been_reassigned | has_conflict_linkage |
|---|---|---|---|---|---|---|
| endato | B06783EF2BF2 | 2 | 0 | 0 | NULL | true |
| healthlink | 4184231AAA7E | 2 | 267 | 1 | true | false |
| quantummedica | 3F56C1D61FDA | 2 | 11 | 11 | false | true |

**What differentiates these cases:** Changing dated NPI sets gives reassignment true even without same-day conflict. A repeated conflicting set can remain false for reassignment. Undated competing NPIs establish conflict in the vendor snapshot but cannot establish chronological change. Day counts describe coverage, not calendar continuity.

Stored indicators are unchanged by display helpers. Reproduction requires the pinned snapshot to remain available.

## Statistics by vendor

[Statistics SQL](../../sql/statistics/09_has_been_reassigned.sql) was executed against the current published `iceberg.jteixeira_ipa.pii_clean` table.

Measured **October 29, 2026**, across all retained source history. Extraction completed at `2026-10-29T17:20:30.647913+01:00`. Published snapshot `6346435822181920647` remained unchanged throughout the six-query refresh. Counts are exact. Email percentages use each vendor's distinct emails. Row percentages use its metric rows.

| Vendor | Reassigned emails, n (%) | Unknown emails, n (%) | Reassigned metric rows, n (%) |
|---|---:|---:|---:|
| HealthLink | 120 (0.00156%) | 0 (0.00000%) | 271 (0.00243%) |
| QuantumMedica | 1 (0.00006%) | 0 (0.00000%) | 2 (0.00012%) |
| Medscape | 109,243 (3.07722%) | 0 (0.00000%) | 2,355,717 (5.00447%) |
| Endato | 0 (0.00000%) | 91,841 (1.72493%) | 0 (0.00000%) |
| RocketReach | 0 (0.00000%) | 29,990 (0.94795%) | 0 (0.00000%) |
| DRDB | 0 (0.00000%) | 7,400 (0.90304%) | 0 (0.00000%) |
| Haymarket | 0 (0.00000%) | 0 (0.00000%) | 0 (0.00000%) |

Endato, RocketReach and DRDB have no dated history. Their multi-NPI emails are unknown for reassignment; the remaining emails have one retained NPI and are false.

Current measured counts, executed SQL and snapshot checks (historical output, not retained: `../../results/published_metric_refresh_20261029.json`) · Native fixtures and preservation checks (historical output, not retained: `../../results/email_linkage_native_validation.json`)

[Profile SQL](../../sql/email_linkage_profile.sql) · [Independent chronological check](../../tests/email_linkage_history.sql) · [Conflict](10_has_conflict_linkage.md) · [Source date limitations](../00_source_map.md)

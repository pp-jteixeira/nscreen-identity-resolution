# Email–NPI multiplicity

**Principle:** count how many distinct reported NPIs one vendor associates with an email across its retained history.

**Where:** `iceberg.jteixeira_ipa.pii__int_<vendor>__metrics` and `iceberg.jteixeira_ipa.pii_clean`. Inputs: `source`, cleaned `email`, trimmed `npi`. Outputs: `email_npi_count` and `email_has_multiple_npis`.

## How it is computed

Group retained records by `source`, `email` and count different nonempty, trimmed NPIs. Then flag counts above one:

```sql
count(DISTINCT npi) AS email_npi_count
```

```sql
email_npi_count > 1 AS email_has_multiple_npis
```

Every metric row for the same vendor/email receives the same count. Vendors are never pooled. DRDB's two inputs belong to one vendor. Repeated records, duplicate email slots and repeated dates cannot increase the distinct-NPI count. Missing email/NPI keys remain in staging; malformed nonempty NPIs still count because validity is a separate question.

Multiplicity does not distinguish historical changes from same-day conflicts or establish ownership. See [reassignment](09_has_been_reassigned.md) and [conflict](10_has_conflict_linkage.md). Aggregation computes the indicator only: existing `source`, `metric_row_id` rows remain, and email–NPI deduplication is deferred.

## Real examples: contrasting outcomes

Selected real records, queried October 30, 2026, from `iceberg.jteixeira_ipa.pii_clean` at snapshot `8096642935433856886`. These examples explain outcomes; they are not prevalence estimates. `email_key` is a shortened SHA-256 display label for the email; it is neither the address nor an ownership identifier.

[Runnable example SQL](../../sql/examples/08_email_npi_multiplicity.sql):

```sql
WITH selected AS (
    SELECT *
    FROM iceberg.jteixeira_ipa.pii_clean FOR VERSION AS OF 8096642935433856886
    WHERE (source = 'endato' AND metric_row_id IN (
        '2BB0A675D0303E69146D4E78DA29BFA8FA827A7B4299222CF647CACE91D06D07'))
       OR (source = 'healthlink' AND metric_row_id IN (
        '459E67998FCF06BC27D79A7CFC02EB236B0D36FEE1DCE6BCAD713ACD5FE6CEF5',
        '8CE13EFACD6E7ACB950A70D33FF7C820166332BF9E41BB9972E0978C00F82D63'))
)
SELECT m.source,
       substr(to_hex(sha256(to_utf8(m.email))), 1, 12) AS email_key,
       m.email_npi_count,
       m.email_has_multiple_npis,
       m.has_been_reassigned,
       m.has_conflict_linkage
FROM selected m
ORDER BY m.source, m.metric_row_id
```

**Result:** 3 rows.

| source | email_key | email_npi_count | email_has_multiple_npis | has_been_reassigned | has_conflict_linkage |
|---|---|---|---|---|---|
| endato | 0B3A3D3999F2 | 2 | true | NULL | true |
| healthlink | 268900E64004 | 2 | true | true | false |
| healthlink | AD6C5BBD22FC | 1 | false | false | false |

**What differentiates these cases:** Two NPIs can mean changing dated attribution without conflict, or competing undated reports with unknown order. Repeated observations of one NPI still count as one. Multiplicity alone cannot distinguish these situations.

Stored indicators are unchanged by display helpers. Reproduction requires the pinned snapshot to remain available.

## Statistics by vendor

[Statistics SQL](../../sql/statistics/08_email_npi_multiplicity.sql) was executed against the current published `iceberg.jteixeira_ipa.pii_clean` table.

Measured **October 29, 2026**, across all retained source history. Extraction completed at `2026-10-29T17:20:30.558322+01:00`. Published snapshot `6346435822181920647` remained unchanged throughout the six-query refresh. Counts are exact. Email percentages use each vendor's distinct emails. Row percentages use its metric rows.

| Vendor | Distinct emails | Multiple NPIs: emails, n (%) | Affected metric rows, n (%) | Maximum NPIs/email |
|---|---:|---:|---:|---:|
| HealthLink | 7,688,331 | 120 (0.00156%) | 271 (0.00243%) | 2 |
| QuantumMedica | 1,705,695 | 28 (0.00164%) | 56 (0.00328%) | 2 |
| Medscape | 3,550,052 | 109,244 (3.07725%) | 2,355,719 (5.00447%) | 3 |
| Endato | 5,324,318 | 91,841 (1.72493%) | 194,982 (3.59251%) | 2,172 |
| RocketReach | 3,163,679 | 29,990 (0.94795%) | 96,287 (1.97953%) | 24 |
| DRDB | 819,454 | 7,400 (0.90304%) | 22,404 (2.00858%) | 5 |
| Haymarket | 4,223,245 | 0 (0.00000%) | 0 (0.00000%) | 1 |

Current measured counts, executed SQL and snapshot checks (historical output, not retained: `../../results/published_metric_refresh_20261029.json`) · Native fixtures and preservation checks (historical output, not retained: `../../results/email_linkage_native_validation.json`)

[Profile SQL](../../sql/email_npi_profile.sql) · [Population check](../../tests/email_npi_multiplicity.sql) · [Source tables and fields](../00_source_map.md)

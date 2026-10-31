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

## Real examples

Executed October 31, 2026, against canonical snapshot `8811920360682490090`. These selected cases explain outcomes; they do not measure prevalence.

[Executed example SQL](../../sql/examples/08_email_npi_multiplicity.sql):

```sql
WITH selected AS (
    SELECT *
    FROM iceberg.jteixeira_ipa.pii_clean FOR VERSION AS OF 8811920360682490090
    WHERE (source = 'endato' AND metric_row_id IN (
        '2BB0A675D0303E69146D4E78DA29BFA8FA827A7B4299222CF647CACE91D06D07'))
       OR (source = 'healthlink' AND metric_row_id IN (
        '459E67998FCF06BC27D79A7CFC02EB236B0D36FEE1DCE6BCAD713ACD5FE6CEF5',
        '8CE13EFACD6E7ACB950A70D33FF7C820166332BF9E41BB9972E0978C00F82D63'))
)
SELECT m.source,
       m.email,
       m.npi,
       m.email_npi_count,
       m.email_has_multiple_npis,
       m.has_been_reassigned,
       m.has_conflict_linkage
FROM selected m
ORDER BY m.source, m.metric_row_id
```

| source | email | npi | email_npi_count | email_has_multiple_npis | has_been_reassigned | has_conflict_linkage |
|---|---|---|---|---|---|---|
| endato | redmundial1@gmail.com | 1366620270 | 2 | true | NULL | true |
| healthlink | joseph.oliver@bmhcc.org | 1699798306 | 2 | true | true | false |
| healthlink | laurahay@gillettechildrens.com | 1881298099 | 1 | false | false | false |

**What differentiates these cases:** Two NPIs can mean changing dated attribution without conflict, or competing undated reports with unknown order. Repeated observations of one NPI still count as one. Multiplicity alone cannot distinguish these situations.

## Statistics by source

Measured **October 31, 2026** from `iceberg.jteixeira_ipa.pii_clean` snapshot `8811920360682490090`. These are exact published-population counts across retained eligible history, not a sample. Stored evaluation dates remain unchanged.

[Executed statistics SQL](../../sql/statistics/08_email_npi_multiplicity.sql)

| Source | Distinct emails | Multiple NPIs: emails, n (%) | Affected records, n (%) | Maximum NPIs/email |
|---|---|---|---|---|
| HealthLink | 7,688,331 | 120 (0.001561%) | 271 (0.002429%) | 2 |
| QuantumMedica | 1,705,695 | 28 (0.001642%) | 56 (0.003283%) | 2 |
| Medscape | 3,550,359 | 109,290 (3.078280%) | 2,359,932 (5.003633%) | 3 |
| Endato | 5,324,318 | 91,841 (1.724935%) | 194,982 (3.592510%) | 2,172 |
| RocketReach | 3,163,679 | 29,990 (0.947947%) | 96,287 (1.979526%) | 24 |
| DRDB | 819,454 | 7,400 (0.903040%) | 22,404 (2.008580%) | 5 |
| Haymarket | 4,223,245 | 0 (0.000000%) | 0 (0.000000%) | 1 |

Email percentages use distinct emails within each source. Affected-record percentages use that source’s metric records. Multiplicity does not identify overlap timing or ownership.

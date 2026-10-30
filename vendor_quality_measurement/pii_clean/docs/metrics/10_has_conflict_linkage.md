# Has conflict linkage

**Principle:** flag competing reported NPIs at the same observation time, within one vendor/email. Output: nullable boolean `has_conflict_linkage` in `iceberg.jteixeira_ipa.pii__int_<vendor>__metrics` and `iceberg.jteixeira_ipa.pii_clean`.

## How it is computed

For dated vendors, count distinct NPIs within `source`, `email`, actual delivery day. Collect days with more than one NPI into `email_conflict_days`, then keep only days observed for this record:

```sql
count(DISTINCT npi) AS daily_npi_count
```

```sql
array_sort(array_intersect(observed_days, email_conflict_days)) AS conflict_days
```

Endato, RocketReach and DRDB compare all current records within each vendor, including both DRDB inputs. This assumes comparability, not a common collection date.

```sql
CASE WHEN source IN ('endato', 'rocketreach', 'drdb') THEN email_npi_count > 1
     WHEN cardinality(conflict_days) > 0 THEN true
     WHEN email_npi_count = 1 THEN false
     WHEN undated_observation_count > 0 THEN NULL
     ELSE false
END AS has_conflict_linkage
```

Repeated copies of one NPI do not create conflict. Unknown days in dated vendors remain unknown; date ranges are never expanded.

Otherwise-identical records can span several days. `conflict_days` lists exactly which of that record's `observed_days` conflict; any such day makes its flag true. Undated-vendor conflicts have an empty `conflict_days` array. A conflict may reflect a shared mailbox or reporting error; it does not identify the correct NPI. Source metric rows remain intact.

## Real examples: contrasting outcomes

Selected real records, queried October 30, 2026, from `iceberg.jteixeira_ipa.pii_clean` at snapshot `8096642935433856886`. These examples explain outcomes; they are not prevalence estimates. `email_key` is a shortened SHA-256 display label. The day count is a display helper over stored exact conflict dates.

[Runnable example SQL](../../sql/examples/10_has_conflict_linkage.sql):

```sql
WITH selected AS (
    SELECT *
    FROM iceberg.jteixeira_ipa.pii_clean FOR VERSION AS OF 8096642935433856886
    WHERE (source = 'endato' AND metric_row_id IN (
        '301CF08DDB677315479773A9D4F728F00F664700BC7F030088C7A8BA0AF05ECF'))
       OR (source = 'healthlink' AND metric_row_id IN (
        '4E8278D37C840774C11F0182CFB16FF3C1F32F292E6769A17B6E328688FE1A26'))
       OR (source = 'quantummedica' AND metric_row_id IN (
        'CA266C53D1E739500DDF891E13D3117AF4CB7478E74A5F6F42E31D9510149D1C'))
)
SELECT m.source,
       substr(to_hex(sha256(to_utf8(m.email))), 1, 12) AS email_key,
       m.email_npi_count,
       m.has_been_reassigned,
       m.has_conflict_linkage,
       cardinality(m.conflict_days) AS conflict_day_count
FROM selected m
ORDER BY m.source, m.metric_row_id
```

**Result:** 3 rows.

| source | email_key | email_npi_count | has_been_reassigned | has_conflict_linkage | conflict_day_count |
|---|---|---|---|---|---|
| endato | B524E4C52FD2 | 2 | NULL | true | 0 |
| healthlink | AE295CE738C9 | 2 | true | false | 0 |
| quantummedica | D03CA99B36BA | 2 | false | true | 11 |

**What differentiates these cases:** Reassignment can occur without overlap; persistent overlap can occur without reassignment. The undated Endato conflict has zero known conflict days because its rule compares available vendor records, not dated observations. Zero known days therefore does not undo its true conflict flag.

Stored indicators are unchanged by display helpers. Reproduction requires the pinned snapshot to remain available.

## Statistics by vendor

[Statistics SQL](../../sql/statistics/10_has_conflict_linkage.sql) was executed against the current published `iceberg.jteixeira_ipa.pii_clean` table.

Measured **October 29, 2026**, across all retained source history. Extraction completed at `2026-10-29T17:20:34.911008+01:00`. Published snapshot `6346435822181920647` remained unchanged throughout the six-query refresh. Counts are exact. Email percentages use each vendor's distinct emails. Row percentages use its metric rows.

| Vendor | Emails with conflict, n (%) | Conflicting metric rows, n (%) | Unknown metric rows, n (%) |
|---|---:|---:|---:|
| HealthLink | 0 (0.00000%) | 0 (0.00000%) | 0 (0.00000%) |
| QuantumMedica | 28 (0.00164%) | 56 (0.00328%) | 0 (0.00000%) |
| Medscape | 16 (0.00045%) | 46 (0.00010%) | 0 (0.00000%) |
| Endato | 91,841 (1.72493%) | 194,982 (3.59251%) | 0 (0.00000%) |
| RocketReach | 29,990 (0.94795%) | 96,287 (1.97953%) | 0 (0.00000%) |
| DRDB | 7,400 (0.90304%) | 22,404 (2.00858%) | 0 (0.00000%) |
| Haymarket | 0 (0.00000%) | 0 (0.00000%) | 0 (0.00000%) |

An email counts once if any of its records conflicts. Only the conflicting records contribute to the row count. Endato, RocketReach and DRDB use the undated-data comparison described above.

Current measured counts, executed SQL and snapshot checks (historical output, not retained: `../../results/published_metric_refresh_20261029.json`) · Native fixtures and preservation checks (historical output, not retained: `../../results/email_linkage_native_validation.json`)

[Profile SQL](../../sql/email_linkage_profile.sql) · [Population check](../../tests/email_linkage_history.sql) · [Reassignment](09_has_been_reassigned.md) · [Source tables](../00_source_map.md)

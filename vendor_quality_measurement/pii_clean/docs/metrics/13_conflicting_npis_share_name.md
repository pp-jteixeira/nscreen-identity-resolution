# Conflicting NPIs share a name

**Question:** does this record share a fuzzy-matching vendor name with another NPI in its conflict context? A shared name does not establish which NPI is correct.

**Where:** `conflicting_npis_share_name` in `iceberg.jteixeira_ipa.pii__int_<vendor>__metrics` and `iceberg.jteixeira_ipa.pii_clean`; key: `source`, `metric_row_id`.

## How it is computed

Within the same vendor/email, compare this record’s `source_name_values` with records on other NPIs whose `conflict_days` overlap. Endato, RocketReach and DRDB instead use one current snapshot per vendor, including both DRDB feeds. Never infer overlap from date bounds or use names from unrelated dates.

Both first and last names must agree under [metric 07’s fuzzy rules](07_vendor_name_matches_registry_name.md). Each peer comparison is true for any matching name pair, false when usable names exist on both sides but none match, or null when either side lacks usable names.

```sql
CASE WHEN has_conflict_linkage AND cardinality(conflicting_npi_name_comparisons) > 0
     THEN any_match(conflicting_npi_name_comparisons, p -> p.shares_name)
END AS conflicting_npis_share_name
```

Any true wins; otherwise a missing comparison leaves null. False requires every peer comparison to be a known mismatch. Without an established conflict, the result is null: not applicable when `has_conflict_linkage = false`, unknown timing when that flag is null.

HealthLink’s HCP-reference names have no date alignment. Registry names never fill missing names. A true result can coexist with disagreeing peers; records remain separate.

`conflicting_npi_name_comparisons` retains peer NPIs, names, overlapping days and outcomes for [full manual inspection](../../sql/conflicting_names_debug.sql). Undated comparisons have empty day arrays.

## Real examples: contrasting outcomes

Selected real records, queried October 30, 2026, from `iceberg.jteixeira_ipa.pii_clean` at snapshot `8096642935433856886`. These examples explain outcomes; they are not prevalence estimates. Conflict examples are selected with exactly one peer comparison, so the displayed peer fully explains the aggregate outcome. Undated Endato comparisons use the available vendor snapshot.

[Runnable example SQL](../../sql/examples/13_conflicting_npis_share_name.sql):

```sql
WITH selected AS (
    SELECT *
    FROM iceberg.jteixeira_ipa.pii_clean FOR VERSION AS OF 8096642935433856886
    WHERE (source = 'endato' AND metric_row_id IN (
        '730FB3822EC1EB3855BF21A4E1C10C1F2788A9DAA943ED02124432207C2B0194',
        '9E1C49D1B6D6366B653D9BBBA7FB85204BD28AEA2CAAD89533B14325A83E98F4',
        'E303163DBAEAE62D4A912EB2F410B50DEE23ADE4ECA621053834DE90C8C0EDFF'))
       OR (source = 'haymarket' AND metric_row_id IN (
        '1577CCE5C0DE4DA85CBD4D8D5897CC938ADF6B1EB6170CB69C2ED4C93F231E8F'))
)
SELECT m.source,
       m.npi,
       (element_at(m.conflicting_npi_name_comparisons, 1)).npi AS peer_npi,
       transform(m.source_name_values, n -> concat(n.first_name, ' ', n.last_name)) AS own_values,
       transform((element_at(m.conflicting_npi_name_comparisons, 1)).names, n -> concat(n.first_name, ' ', n.last_name)) AS peer_values,
       m.has_conflict_linkage AS conflict,
       m.conflicting_npis_share_name AS shares_name
FROM selected m
ORDER BY m.source, m.metric_row_id
```

**Result:** 4 rows.

| source | npi | peer_npi | own_values | peer_values | conflict | shares_name |
|---|---|---|---|---|---|---|
| endato | 1114929445 | 1922090380 | [ANGRETTE MCCLOSKEY] | [TAHANI MCCLOSKEY] | true | false |
| endato | 1104264514 | 1649302860 | [] | [] | true | NULL |
| endato | 1477722270 | 1740371913 | [JOHN SEAWORTH] | [JOHN SEAWORTH] | true | true |
| haymarket | 1235433285 | NULL | [DENVER CHAO] | NULL | false | NULL |

**What differentiates these cases:** A qualifying fuzzy name match gives true; known fuzzy disagreement gives false. With an established conflict, missing evidence leaves NULL. Without a conflict, NULL is not applicable. Names use the same fuzzy first/last rules as metric 07; agreement does not identify the correct NPI.

Stored indicators are unchanged by display helpers. Reproduction requires the pinned snapshot to remain available.

## Statistics by vendor

[Statistics SQL](../../sql/statistics/13_conflicting_npis_share_name.sql) was executed against the current published `iceberg.jteixeira_ipa.pii_clean` table.

Measured **October 29, 2026**, across all retained source history. Extraction completed at `2026-10-29T17:20:40.438733+01:00`. Published snapshot `6346435822181920647` remained unchanged throughout the six-query refresh. Counts are exact. Percentages use each vendor’s conflict rows. — means that the vendor has no conflict rows.

| Vendor | Conflict rows | Shared name, n (%) | Different names, n (%) | Unknown names, n (%) |
|---|---:|---:|---:|---:|
| HealthLink | 0 | 0 (—) | 0 (—) | 0 (—) |
| QuantumMedica | 56 | 0 (0.00%) | 0 (0.00%) | 56 (100.00%) |
| Medscape | 46 | 21 (45.65%) | 21 (45.65%) | 4 (8.70%) |
| Endato | 194,982 | 131,452 (67.42%) | 63,516 (32.58%) | 14 (0.01%) |
| RocketReach | 96,287 | 29,601 (30.74%) | 66,538 (69.10%) | 148 (0.15%) |
| DRDB | 22,404 | 17,010 (75.92%) | 4,985 (22.25%) | 409 (1.83%) |
| Haymarket | 0 | 0 (—) | 0 (—) | 0 (—) |

Across 75,564,265 metric rows, 75,250,490 are not applicable and 0 have unknown conflict timing. Both groups have a null name-sharing flag. Rows for one email–NPI link can differ.

Current measured counts, executed SQL and snapshot checks (historical output, not retained: `../../results/published_metric_refresh_20261029.json`) · Native fixtures and preservation (historical output, not retained: `../../results/conflicting_names_native_validation.json`) · Published-table validation (historical output, not retained: `../../results/final_build.json`)

[Calculation](../../macros/name_consistency.sql) · [Independent check](../../tests/conflicting_names.sql) · [Profile SQL](../../sql/conflicting_names_profile.sql)

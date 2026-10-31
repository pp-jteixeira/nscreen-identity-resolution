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

## Real examples

Executed October 31, 2026, against canonical snapshot `8811920360682490090`. These selected cases explain outcomes; they do not measure prevalence.

[Executed example SQL](../../sql/examples/13_conflicting_npis_share_name.sql):

```sql
WITH selected AS (
    SELECT *
    FROM iceberg.jteixeira_ipa.pii_clean FOR VERSION AS OF 8811920360682490090
    WHERE (source = 'endato' AND metric_row_id IN (
        '730FB3822EC1EB3855BF21A4E1C10C1F2788A9DAA943ED02124432207C2B0194',
        '9E1C49D1B6D6366B653D9BBBA7FB85204BD28AEA2CAAD89533B14325A83E98F4',
        'E303163DBAEAE62D4A912EB2F410B50DEE23ADE4ECA621053834DE90C8C0EDFF'))
       OR (source = 'haymarket' AND metric_row_id IN (
        '1577CCE5C0DE4DA85CBD4D8D5897CC938ADF6B1EB6170CB69C2ED4C93F231E8F'))
)
SELECT m.source,
       m.email,
       m.npi,
       (element_at(m.conflicting_npi_name_comparisons, 1)).npi AS peer_npi,
       transform(m.source_name_values, n -> concat(n.first_name, ' ', n.last_name)) AS own_values,
       transform((element_at(m.conflicting_npi_name_comparisons, 1)).names, n -> concat(n.first_name, ' ', n.last_name)) AS peer_values,
       m.has_conflict_linkage AS conflict,
       m.conflicting_npis_share_name AS shares_name
FROM selected m
ORDER BY m.source, m.metric_row_id
```

| source | email | npi | peer_npi | own_values | peer_values | conflict | shares_name |
|---|---|---|---|---|---|---|---|
| endato | cmizelle@att.net | 1114929445 | 1922090380 | [ANGRETTE MCCLOSKEY] | [TAHANI MCCLOSKEY] | true | false |
| endato | njordanfnp@outlook.com | 1104264514 | 1649302860 | [] | [] | true | NULL |
| endato | joyce.rodrigue@gmail.com | 1477722270 | 1740371913 | [JOHN SEAWORTH] | [JOHN SEAWORTH] | true | true |
| haymarket | denverchao@bemg.org | 1235433285 | NULL | [DENVER CHAO] | NULL | false | NULL |

**What differentiates these cases:** A qualifying fuzzy name match gives true; known fuzzy disagreement gives false. With an established conflict, missing evidence leaves NULL. Without a conflict, NULL is not applicable. Names use the same fuzzy first/last rules as metric 07; agreement does not identify the correct NPI.

## Statistics by source

Measured **October 31, 2026** from `iceberg.jteixeira_ipa.pii_clean` snapshot `8811920360682490090`. These are exact published-population counts across retained eligible history, not a sample. Stored evaluation dates remain unchanged.

[Executed statistics SQL](../../sql/statistics/13_conflicting_npis_share_name.sql)

| Source | Conflict records | Shared, n (%) | Disjoint, n (%) | Unknown, n (%) |
|---|---|---|---|---|
| HealthLink | 0 | 0 (—) | 0 (—) | 0 (—) |
| QuantumMedica | 56 | 0 (0.000000%) | 0 (0.000000%) | 56 (100.000000%) |
| Medscape | 46 | 21 (45.652174%) | 21 (45.652174%) | 4 (8.695652%) |
| Endato | 194,982 | 131,452 (67.417505%) | 63,516 (32.575315%) | 14 (0.007180%) |
| RocketReach | 96,287 | 29,601 (30.742468%) | 66,538 (69.103825%) | 148 (0.153707%) |
| DRDB | 22,404 | 17,010 (75.923942%) | 4,985 (22.250491%) | 409 (1.825567%) |
| Haymarket | 0 | 0 (—) | 0 (—) | 0 (—) |

Percentages use records with `has_conflict_linkage = true`, not all records. A zero conflict denominator is shown as —. Records without an established conflict are not counted as unknown conflicts.

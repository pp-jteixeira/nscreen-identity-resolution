# Conflicting NPIs share a name

**Question:** does this link share a fuzzy-matching vendor name with another NPI in its conflict context? A shared name does not establish which NPI is correct.

**Where:** `conflicting_npis_share_name` in `iceberg.jteixeira_ipa.pii__int_<vendor>__metrics` and `iceberg.jteixeira_ipa.pii_clean`; key: `source`, `link_id` (one source/email/NPI link).

## How it is computed

Within the same vendor/email, compare this link's `source_name_values` with the links of other NPIs whose `conflict_days` overlap. Both sides use the union of usable names across all versions of the link. Endato, RocketReach and DRDB instead compare every other NPI of the email in one current snapshot per vendor, including both DRDB feeds. Never infer overlap from date bounds or use names from unrelated dates.

Both first and last names must agree under [metric 07's fuzzy rules](07_vendor_name_matches_registry_name.md). Each peer comparison is true for any matching name pair, false when usable names exist on both sides but none match, or null when either side lacks usable names.

```sql
CASE WHEN has_conflict_linkage AND cardinality(conflicting_npi_name_comparisons) > 0
     THEN any_match(conflicting_npi_name_comparisons, p -> p.shares_name)
END AS conflicting_npis_share_name
```

Any true wins; otherwise a missing comparison leaves null. False requires every peer comparison to be a known mismatch. Without an established conflict, the result is null: not applicable when `has_conflict_linkage = false`, unknown timing when that flag is null. This metric has no `_latest` form.

HealthLink's HCP-reference names have no date alignment. Registry names never fill missing names. A true result can coexist with disagreeing peers.

`conflicting_npi_name_comparisons` retains peer NPIs, names, overlapping days and outcomes for [full manual inspection](../../sql/conflicting_names_debug.sql). Undated comparisons have empty day arrays.

## Real examples

Executed November 2, 2026, against `iceberg.jteixeira_ipa.pii_clean` snapshot `2837737034249693554`. These selected cases explain outcomes; they do not measure prevalence.

```sql
SELECT source, email, npi, record_count,
       transform(source_name_values, n -> n.first_name || ' ' || n.last_name) AS link_names,
       transform(conflicting_npi_name_comparisons, p -> p.npi || ': ' || array_join(transform(p.names, n -> n.first_name || ' ' || n.last_name), ', ')) AS peer_names,
       has_conflict_linkage, conflicting_npis_share_name
FROM iceberg.jteixeira_ipa.pii_clean
WHERE (source = 'endato' AND link_id IN ('0000D99684BF16BE7602BA1F9A425F5BAC8E6AC57A0EA41D47F76C41805EA27A', '0001C709726BB99DFFA4AE0200D2B2F8D4508BAFA94D2706F32A7FB6552D2C2E', '13C720AFCA05FFDB3DF9F3DB624DA9ECD68CFE4FB14226C77ED441E052C33138'))
   OR (source = 'medscape' AND link_id IN ('4C7468EBC1D99D7914693F0F05ED57FF0F55BDBF5DC6277B2801FC795FED5D19', '104FEB7B41C783C46968F7ADCC1FFAC4397B2B7A8DC8A5E29A197F1DEA75A987'))
   OR (source = 'quantummedica' AND link_id IN ('B1BF32E78A2E6EDF12ACF41194D025D4BBF1C4828370D72D4E42629AD83095BB'))
   OR (source = 'healthlink' AND link_id IN ('011A4E3469D63171B176507DBDB51E1A4A7FE27976A32920F81AB683684A4A21'))
ORDER BY source, link_id
```

| source | email | npi | record_count | link_names | peer_names | has_conflict_linkage | conflicting_npis_share_name |
|---|---|---|---|---|---|---|---|
| endato | ppaulaj7i20@verizon.net | 1871569921 | 1 | ['PAULA LAWRENCE'] | ['1265075410: PAULA LAWRENCE'] | true | true |
| endato | jessgene045@gmail.com | 1326082884 | 1 | ['KRISHAN MATHUR'] | ['1770928194: ANISHA MATHUR'] | true | false |
| endato | clnan@yahoo.com | 1679544712 | 1 | ['CHEN LINAN'] | ['1659739936: '] | true | NULL |
| healthlink | kchuang@memorialcare.org | 1205998929 | 1 | ['KENNETH CHUANG'] | [] | false | NULL |
| medscape | fangchenmd@gmail.com | 1407193790 | 1 | ['FANG CHEN'] | ['1255455689: FANG CHEN'] | true | true |
| medscape | pawnking4@netscape.net | 1033420419 | 2 | ['NATHAN PATEL'] | ['1861566606: TUSHAR PATEL'] | true | false |
| quantummedica | aroman@prongersmith.com | 1174520019 | 1 | [] | ['1659335578: '] | true | NULL |

**What differentiates these cases:**

- **Matching name (true):** the Endato link for `ppaulaj7i20@verizon.net` and the Medscape link for `fangchenmd@gmail.com` each have a peer NPI that reports the same name (PAULA LAWRENCE, FANG CHEN).
- **Known disagreement (false):** the Endato link for `jessgene045@gmail.com` reports KRISHAN MATHUR while its peer reports ANISHA MATHUR. The Medscape link for `pawnking4@netscape.net` (2 versions) reports NATHAN PATEL while its peer reports TUSHAR PATEL. The surnames agree but the first names do not.
- **Missing evidence (NULL, unknown):** the Endato link for `clnan@yahoo.com` has a peer without usable names, and the QuantumMedica link for `aroman@prongersmith.com` has no usable names itself. A conflict exists, but there is nothing to compare.
- **No conflict (NULL, not applicable):** the HealthLink link for `kchuang@memorialcare.org` has names but no conflict (`has_conflict_linkage` false), so the metric does not apply. Agreement does not identify the correct NPI.

## Statistics by source

Measured **November 2, 2026** from `iceberg.jteixeira_ipa.pii_clean` snapshot `2837737034249693554`. These are exact published-population counts across retained eligible history, not a sample. Source data period (first to last observed day): HealthLink 2026-01-07 to 2026-10-03, QuantumMedica 2025-09-14 to 2026-10-15, Medscape 2024-01-10 to 2026-11-01 and Haymarket 2021-07-06 (a single day). Endato, RocketReach and DRDB are undated.

[Statistics SQL](../../sql/statistics/13_conflicting_npis_share_name.sql)

| Source | Links | Conflict links, n (% of links) | Shares a name, n (% of conflict links) | Different names, n (% of conflict links) | Unknown, n (% of conflict links) |
|---|---|---|---|---|---|
| HealthLink | 7,688,451 | 0 (0.000000%) | 0 (undefined) | 0 (undefined) | 0 (undefined) |
| QuantumMedica | 1,705,723 | 56 (0.003283%) | 0 (0.000000%) | 0 (0.000000%) | 56 (100.000000%) |
| Medscape | 3,661,537 | 32 (0.000874%) | 14 (43.750000%) | 14 (43.750000%) | 4 (12.500000%) |
| Endato | 5,427,459 | 194,982 (3.592510%) | 131,452 (67.417505%) | 63,516 (32.575315%) | 14 (0.007180%) |
| RocketReach | 3,199,535 | 65,846 (2.057987%) | 18,756 (28.484646%) | 46,982 (71.351335%) | 108 (0.164019%) |
| DRDB | 826,886 | 14,832 (1.793718%) | 11,602 (78.222762%) | 3,219 (21.703074%) | 11 (0.074164%) |
| Haymarket | 4,223,245 | 0 (0.000000%) | 0 (undefined) | 0 (undefined) | 0 (undefined) |

Percentages of shared, different and unknown outcomes use links with `has_conflict_linkage = true`, not all links. A zero conflict denominator gives an undefined percentage. Links without an established conflict are not counted as unknown conflicts. No link has unknown conflict timing, so every link outside a conflict is not applicable.

HealthLink and Haymarket have no conflicts, so the metric is not applicable to all their links. Among the sources with conflicts, Endato shows a shared name for 67.417505% of conflict links and DRDB for 78.222762%, while RocketReach shows 28.484646%. QuantumMedica has no usable vendor names, so all 56 of its conflict links are unknown. Medscape has only 32 conflict links, split evenly between shared and different names with 4 unknown.

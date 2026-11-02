# Vendor name matches registry name

**Question:** do a vendor-supplied name and a registry name for the same NPI agree under fuzzy comparison? Agreement does not prove they identify the same person.

**Where:** `vendor_name_matches_registry_name` and `vendor_name_matches_registry_name_latest` in `iceberg.jteixeira_ipa.pii__int_<vendor>__metrics`; key: `source`, `link_id` (one source/email/NPI link). Vendors: `healthlink`, `quantummedica`, `medscape`, `endato`, `rocketreach`, `drdb`, `haymarket`. Vendor [name inputs](../00_source_map.md#name-comparison-inputs) join the [registry name pairs](../../models/intermediate/int_npi__names.sql) by trimmed NPI.

## How it is computed

Compare normalized first and last names separately. Both parts must agree:

- First names: exact names, a shared space-separated token, a first-token prefix of at least three characters, overlapping nickname expansions, or allowed edits.
- Last names: equal letters-only forms, a shared space/hyphen-separated token, or allowed edits.
- Allowed edits: at most one when both parts have at least five letters; at most two when both have at least eight. These lengths apply to the compared name parts, not the email.

For each name pair, `fk` and `lk` are the first- and last-name match classes (`none` means disagreement). Missing usable names produce null.

```sql
CASE WHEN source_name_usable AND registry_name_usable
     THEN fk <> 'none' AND lk <> 'none'
END AS vendor_registry_match
```

**All versions.** `vendor_name_matches_registry_name` aggregates comparisons of every distinct vendor name pair across the link's versions with every registry name of the NPI:

```sql
bool_or(vendor_registry_match) AS vendor_name_matches_registry_name
```

Any qualifying pair gives true; usable comparisons without a match give false; all-null comparisons stay unknown. Usability requires one first-name letter and two last-name letters.

**Latest version.** `vendor_name_matches_registry_name_latest` applies the same rule to the name of the link's latest version only (`latest_record_id`, see [observation counts](01_observation_counts.md)). It is null when the link has no single latest version. A link can be true over all versions and false for its latest version when only an earlier vendor name agrees with the registry.

**Limits:** common names, shared tokens and broad nickname mappings can produce false matches. Only this link's vendor names and current readable registry variants contribute; HealthLink uses its separate HCP reference by NPI, so its latest column equals the all-version column. No historical as-of alignment is implied. Endato compares its returned person's name, not the NPI-holder name supplied as input. No score or filtering is applied.

## Stored comparison explanations

Stored core also retains `name_match_evidence`, `vendor_registry_match_classes`, `name_match_evaluated_at` and `name_match_definition_version`. They describe the all-version comparisons. The array keeps distinct comparisons and their component kinds; the class set includes every outcome, including `first_only`, `last_only`, `none` and `unknown`. Exact/nickname/token/edit comparisons make the boolean true. No scoring weights are added. [Stored evidence documentation](../name_match_evidence.md) describes the classes.

## Real examples

Executed November 2, 2026, against `iceberg.jteixeira_ipa.pii_clean` snapshot `2837737034249693554`. These selected cases explain outcomes; they do not measure prevalence. Registry names come from the current readable name view; the stored indicators come from the pinned snapshot.

```sql
SELECT m.source,
       m.email,
       m.npi,
       array_join(transform(m.source_name_values, n -> n.first_name || ' ' || n.last_name), ' / ') AS vendor_names,
       r.registry_names,
       array_join(m.vendor_registry_match_classes, ',') AS match_classes,
       m.record_count,
       m.vendor_name_matches_registry_name,
       m.vendor_name_matches_registry_name_latest
FROM iceberg.jteixeira_ipa.pii_clean FOR VERSION AS OF 2837737034249693554 m
LEFT JOIN (SELECT npi, array_join(array_agg(first_name || ' ' || last_name ORDER BY first_name, last_name), ' / ') AS registry_names FROM iceberg.jteixeira_ipa.pii__int_npi__names GROUP BY npi) r ON m.npi = r.npi
WHERE (source = 'endato' AND link_id IN (
        '000008A4EA6ECF2F20198FD9A0F624BBEDD4D992F96C6D5A2E6A837CFEED23E0',
        '00076D49BD94174B0A58EB111362272B0DF3C803C532F0B7122C21BB4BD75F9B',
        '00003015A07FF7279D1EEF2F75DF87469DBE1885BAF025ED1E55E8697F7DF4A3',
        '00009717AD10223F84C2C2954400B73ABD2A3A7E0ACACADC1BEBF86DC8B6587B',
        '000176FE5B0F72621EE9AD5313E0D36666190D49B460E0500D3EFD816F77FD40',
        '00044A8CA56F88419DFAB241F536318D2D54D9DFAF5890A0514C5FC6423869F8'))
   OR (source = 'medscape' AND link_id IN (
        '0035B70A83E848FA32CBD81DCA84300554A7743E9ED34C3E59EFF32C78E1AB3F'))
ORDER BY m.source, m.npi
```

| source | email | npi | vendor_names | registry_names | match_classes | record_count | vendor_name_matches_registry_name | vendor_name_matches_registry_name_latest |
|---|---|---|---|---|---|---|---|---|
| endato | hclague@gmail.com | 1245287663 | HEATHER CLAGUE | NULL | unknown | 1 | NULL | NULL |
| endato | dcwiest605@yahoo.com | 1306815659 | DAVID WIEST | DAVID GROUNDS | first_only | 1 | false | false |
| endato | www.jazz_50cent@yahoo.com | 1467439232 | WILLIE LAGO | WILLIAM LAGO | nickname | 1 | true | true |
| endato | abriggs699@gmail.com | 1841362241 | MOHAMMAD ISLAMI | MOHAMMAD ISLAMI MANUCHEHRY | token | 1 | true | true |
| endato | tiahamilton@gmail.com | 1902999519 | VIRGINIA HAMILTON | VIRGINA HAMILTON | edit | 1 | true | true |
| endato | wkraybill@gmail.com | 1982602363 | WILLIAM KRAYBILL | WILLIAM KRAYBILL | exact | 1 | true | true |
| medscape | mel161977@aol.com | 1548830219 | JANICE HARVEY / JANICE SMITH | JANICE HARVEY | exact,first_only | 2 | true | false |

**What differentiates these cases:**

- **Exact versus fuzzy agreement:** WILLIAM KRAYBILL matches exactly (class `exact`). WILLIE/WILLIAM matches through nickname expansions. MOHAMMAD ISLAMI against MOHAMMAD ISLAMI MANUCHEHRY matches through a shared token. Each has a matching surname.
- **Permissive edit rule:** VIRGINIA/VIRGINA differs by one deleted letter and the surname agrees, so the rule accepts it (class `edit`). Such edits can also accept different people.
- **One matching part is insufficient:** DAVID agrees but WIEST/GROUNDS does not, so the class is `first_only` and the result is false.
- **Unknown differs from disagreement:** HEATHER CLAGUE has no registry name for the NPI, so the result is NULL, not false.
- **All versions versus latest:** The Medscape link has two versions, JANICE HARVEY and JANICE SMITH. The registry name JANICE HARVEY matches the earlier one, so the all-version result is true (classes `exact` and `first_only`) while the latest version's result is false.

## Statistics by source

Measured **November 2, 2026** from `iceberg.jteixeira_ipa.pii_clean` snapshot `2837737034249693554`. These are exact published-population counts across retained eligible history, not a sample.

Source data period (first to last observed day): HealthLink 2026-01-07 to 2026-10-03; QuantumMedica 2025-09-14 to 2026-10-15; Medscape 2024-01-10 to 2026-11-01; Haymarket 2021-07-06 (a single day). Endato, RocketReach and DRDB are undated.

[Statistics SQL](../../sql/statistics/07_vendor_name_matches_registry_name.sql) reports, per source, links and the match, no-match and unknown counts for the all-version column. The [any-version versus latest companion](../../sql/statistics/07_vendor_name_matches_registry_name_statement_002.sql) compares it with `vendor_name_matches_registry_name_latest`, and the [class statistics](../../sql/statistics/07_name_match_classes.sql) report the stored match-class distribution.

| Source | Links | Match, n (%) | No match, n (%) | Unknown, n (%) |
|---|---:|---:|---:|---:|
| HealthLink | 7,688,451 | 7,254,867 (94.360581%) | 384,427 (5.000058%) | 49,157 (0.639362%) |
| QuantumMedica | 1,705,723 | 0 (0.000000%) | 0 (0.000000%) | 1,705,723 (100.000000%) |
| Medscape | 3,661,537 | 3,166,375 (86.476663%) | 390,459 (10.663800%) | 104,703 (2.859537%) |
| Endato | 5,427,459 | 1,279,079 (23.566811%) | 4,103,800 (75.611810%) | 44,580 (0.821379%) |
| RocketReach | 3,199,535 | 3,066,586 (95.844740%) | 98,754 (3.086511%) | 34,195 (1.068749%) |
| DRDB | 826,886 | 814,759 (98.533413%) | 4,528 (0.547597%) | 7,599 (0.918990%) |
| Haymarket | 4,223,245 | 3,756,468 (88.947433%) | 224,434 (5.314255%) | 242,343 (5.738313%) |

**All versions versus latest version**

| Source | Links | Links with a single latest version | Multi-version links | Links where any-version and latest differ | Any-version true, latest false | Any-version true, latest NULL |
|---|---:|---:|---:|---:|---:|---:|
| HealthLink | 7,688,451 | 7,688,249 | 2,995,627 | 0 | 0 | 0 |
| QuantumMedica | 1,705,723 | 1,705,723 | 0 | 0 | 0 | 0 |
| Medscape | 3,661,537 | 3,661,506 | 86,484 | 1,160 | 1,036 | 110 |
| Endato | 5,427,459 | 5,427,459 | 0 | 0 | 0 | 0 |
| RocketReach | 3,199,535 | 3,199,535 | 0 | 0 | 0 | 0 |
| DRDB | 826,886 | 607,740 | 219,146 | 0 | 0 | 0 |
| Haymarket | 4,223,245 | 4,223,245 | 0 | 0 | 0 | 0 |

**Stored match-class distribution**

Each cell counts links whose stored `vendor_registry_match_classes` contains the class, as a share of the source's links. Percentages are not disjoint: a link with several vendor names or registry names can hold several classes.

| Source | `exact` | `nickname` | `token` | `edit` | `first_only` | `last_only` | `none` | `unknown` |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| HealthLink | 7,162,050 (93.153354%) | 2,423 (0.031515%) | 79,659 (1.036086%) | 10,748 (0.139794%) | 360,317 (4.686471%) | 19,747 (0.256840%) | 4,418 (0.057463%) | 49,157 (0.639362%) |
| QuantumMedica | 0 (0.000000%) | 0 (0.000000%) | 0 (0.000000%) | 0 (0.000000%) | 0 (0.000000%) | 0 (0.000000%) | 0 (0.000000%) | 1,705,723 (100.000000%) |
| Medscape | 2,899,355 (79.184097%) | 50,415 (1.376881%) | 201,094 (5.492065%) | 16,424 (0.448555%) | 172,759 (4.718210%) | 145,730 (3.980023%) | 74,707 (2.040318%) | 104,703 (2.859537%) |
| Endato | 1,179,897 (21.739400%) | 20,063 (0.369657%) | 64,849 (1.194832%) | 14,270 (0.262922%) | 129,049 (2.377706%) | 2,246,581 (41.392869%) | 1,728,170 (31.841235%) | 44,580 (0.821379%) |
| RocketReach | 2,970,254 (92.833927%) | 11,279 (0.352520%) | 54,429 (1.701153%) | 30,624 (0.957139%) | 47,640 (1.488966%) | 32,223 (1.007115%) | 18,891 (0.590430%) | 34,195 (1.068749%) |
| DRDB | 810,252 (97.988356%) | 75 (0.009070%) | 3,675 (0.444439%) | 2,235 (0.270291%) | 10,985 (1.328478%) | 863 (0.104367%) | 2,082 (0.251788%) | 7,599 (0.918990%) |
| Haymarket | 3,625,470 (85.845600%) | 6,209 (0.147020%) | 111,469 (2.639416%) | 13,320 (0.315397%) | 159,536 (3.777569%) | 52,269 (1.237650%) | 12,629 (0.299035%) | 242,343 (5.738313%) |

Links holding more than one class: HealthLink 68, Medscape 3,639, DRDB 10,880, and none for the other sources.

Percentages use all links within each source. Categories partition links in the boolean table. Distinct-email outcomes cannot be inferred by adding link counts. Unknown is NULL, not disagreement.

QuantumMedica has no usable vendor names, so all 1,705,723 links are unknown and the comparison is unavailable for that source. DRDB (98.53%), RocketReach (95.84%) and HealthLink (94.36%) agree with the registry most often. Endato agrees for 23.57% of its links and disagrees for 75.61%; its most frequent classes are `last_only` and `none` (41.39% and 31.84%), that is, the surname agrees with the registry name but the first name does not, or neither part agrees.

The all-version and latest columns differ only for Medscape: 1,160 of its 86,484 multi-version links, of which 1,036 are true over all versions and false for the latest version and 110 are true over all versions with a NULL latest result. DRDB's 219,146 links without a single latest version have no latest comparison.

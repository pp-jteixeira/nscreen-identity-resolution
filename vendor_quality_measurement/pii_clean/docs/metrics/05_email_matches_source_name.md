# Email matches source name

**Question:** does the email's mailbox text resemble a name supplied by this vendor? A match is name evidence, not proof of ownership.

**Where:** `email_matches_source_name` and `email_matches_source_name_latest` in `iceberg.jteixeira_ipa.pii__int_<vendor>__metrics`, keyed by `source`, `link_id` (one source/email/NPI link). Vendors: `healthlink`, `quantummedica`, `medscape`, `endato`, `rocketreach`, `drdb`, `haymarket`. Inputs and name parsing are listed in the [source map](../00_source_map.md#name-comparison-inputs).

## How it is computed

Normalize each paired first/last name: uppercase, supported accents removed, spaces/hyphens/apostrophes retained; empty, `NULL`, `NaN` and `\N` become missing. Expand first names through the [nickname list](../../seeds/nicknames.csv). Reduce the email mailbox to lowercase letters:

```sql
regexp_replace(lower(regexp_extract(email, '^([^@]*)@', 1)), '[^a-z]', '') AS local_letters
```

For each usable name, compute `source_match` using these rules:

- Both first and last names occur anywhere; each needs two letters.
- Or the local part starts with the first initial and ends with the last name, or the reverse. It must be longer than the last name.
- Or a local part of six or more letters differs by at most one insertion, deletion or substitution from first+last, last+first, initial+last or last+initial.

A usable name needs at least one first-name letter and two last-name letters. `source_name_usable` records availability.

**All versions.** A link can merge several source record versions with different names. `email_matches_source_name` compares the email with every distinct vendor name pair across the link's versions: any matching name gives true; usable names with no match give false; no usable name leaves unknown.

```sql
bool_or(source_match) AS email_matches_source_name
```

**Latest version.** `email_matches_source_name_latest` applies the same rule to the name of the link's latest version only (`latest_record_id`, see [observation counts](01_observation_counts.md)). It is null when the link has no single latest version. Comparing the two columns shows whether the current vendor name still supports the email.

Names stay paired within their version. HealthLink alone attaches distinct HCP-reference names by NPI across retained history, without date alignment; its latest column therefore equals the all-version column. Repeated observations add no weight. `source_name_values` lists the usable names across all versions.

Format validation is separate. RocketReach and DRDB full-name parsing can mistake titles or suffixes for name parts.

## Real examples

Executed November 2, 2026, against `iceberg.jteixeira_ipa.pii_clean` snapshot `2837737034249693554`. These selected cases explain outcomes; they do not measure prevalence.

```sql
SELECT source,
       email,
       npi,
       record_count,
       array_join(transform(source_name_values, n -> n.first_name || ' ' || n.last_name), ' / ') AS vendor_names,
       email_matches_source_name,
       email_matches_source_name_latest,
       latest_record_id IS NOT NULL AS has_latest_record
FROM iceberg.jteixeira_ipa.pii_clean FOR VERSION AS OF 2837737034249693554
WHERE (source = 'healthlink' AND link_id IN (
        '000003EF65550016D15786DAA9351C829F608354411ECD4C845B5E20C1276CC8',
        '00000FDBBE490B347739EDAB8535DCBD459D3F7F6A8BC9B12EC70D466FD2978C',
        '014EB1A111CDC57BD07A399841514124BF1C420FFE913EBEB8D7116D7FD13679'))
   OR (source = 'medscape' AND link_id IN (
        '004E25F3D011F290F0353B20D2073DA624C17753264D6D6694B6D1DA7A3DAEF8',
        '006830BBDBD447EBB2277782EEA22CB328E8CF01F64975B46DE36AF56C9B4353'))
   OR (source = 'drdb' AND link_id IN (
        '000016421AFD3B585B294CA0C5360789770F24578685F0F7E0C5C956318A2D3B'))
   OR (source = 'quantummedica' AND link_id IN (
        '00000BA286ADECF777EA438FAA70261EEA429A67DBD4E6C1A467307C957CEE9A'))
ORDER BY source, email, npi
```

| source | email | npi | record_count | vendor_names | email_matches_source_name | email_matches_source_name_latest | has_latest_record |
|---|---|---|---|---|---|---|---|
| drdb | katherine.chiu.md@gmail.com | 1518040575 | 2 | KATHERINE CHIU | true | NULL | false |
| healthlink | emily_ann_schuster@yahoo.com | 1154185684 | 1 |  | NULL | NULL | true |
| healthlink | jnance219676@cookchildrens.direct-ci.com | 1770745390 | 1 | JENNIFER NANCE | true | true | true |
| healthlink | sss27f@hotmail.com | 1306880141 | 1 | HUMAM FARAH | false | false | true |
| medscape | brian.j.swansiger@kp.org | 1780734236 | 2 | BRIAN DELETED / BRIAN SWANSIGER | true | false | true |
| medscape | keelee109@yahoo.com | 1376833582 | 2 | KATELYN CHANG / KATELYN BOKYONG LEE | true | false | true |
| quantummedica | angiescanales@yahoo.com | 1942511381 | 1 |  | NULL | NULL | true |

**What differentiates these cases:** `jnance219676@` against JENNIFER NANCE matches through the initial/surname rule; `sss27f@` against HUMAM FARAH has a usable name and no match, so it is false. The HealthLink link with an empty name array and the QuantumMedica link (QuantumMedica supplies no usable vendor names) are NULL, not false. The Medscape link `keelee109@yahoo.com` has two versions: the earlier one carried KATELYN BOKYONG LEE, which matches the mailbox, and the latest carries KATELYN CHANG, which does not, so the all-version column is true and the `_latest` column is false. The other Medscape link shows the same pattern: the latest version replaces the surname SWANSIGER with a placeholder, so only the earlier name matches `brian.j.swansiger@kp.org`. The DRDB link merges two undated versions and has no single latest version, so its `_latest` column is NULL while the all-version column is true. Registry evidence never fills a missing vendor name, and mailbox resemblance does not prove ownership.

## Statistics by source

Measured **November 2, 2026** from `iceberg.jteixeira_ipa.pii_clean` snapshot `2837737034249693554`. These are exact published-population counts across retained eligible history, not a sample.

Source data period (first to last observed day): HealthLink 2026-01-07 to 2026-10-03; QuantumMedica 2025-09-14 to 2026-10-15; Medscape 2024-01-10 to 2026-11-01; Haymarket 2021-07-06 (a single day). Endato, RocketReach and DRDB are undated.

[Statistics SQL](../../sql/statistics/05_email_matches_source_name.sql) reports, per source, links and the match, no-match and unknown counts for the all-version column. The [any-version versus latest companion](../../sql/statistics/05_email_matches_source_name_statement_002.sql) compares it with `email_matches_source_name_latest`.

| Source | Links | Match, n (%) | No match, n (%) | Unknown, n (%) |
|---|---:|---:|---:|---:|
| HealthLink | 7,688,451 | 5,204,768 (67.695925%) | 2,483,168 (32.297377%) | 515 (0.006698%) |
| QuantumMedica | 1,705,723 | 0 (0.000000%) | 1 (0.000059%) | 1,705,722 (99.999941%) |
| Medscape | 3,661,537 | 1,912,213 (52.224325%) | 1,704,623 (46.554848%) | 44,701 (1.220826%) |
| Endato | 5,427,459 | 1,999,756 (36.845161%) | 3,427,481 (63.150749%) | 222 (0.004090%) |
| RocketReach | 3,199,535 | 1,945,989 (60.820994%) | 1,251,588 (39.117809%) | 1,958 (0.061196%) |
| DRDB | 826,886 | 600,696 (72.645564%) | 226,128 (27.346938%) | 62 (0.007498%) |
| Haymarket | 4,223,245 | 2,528,601 (59.873415%) | 1,502,730 (35.582354%) | 191,914 (4.544231%) |

**All versions versus latest version**

| Source | Links | Links with a single latest version | Multi-version links | Links where any-version and latest differ | Any-version true, latest false | Any-version true, latest NULL |
|---|---:|---:|---:|---:|---:|---:|
| HealthLink | 7,688,451 | 7,688,249 | 2,995,627 | 0 | 0 | 0 |
| QuantumMedica | 1,705,723 | 1,705,723 | 0 | 0 | 0 | 0 |
| Medscape | 3,661,537 | 3,661,506 | 86,484 | 1,396 | 1,269 | 51 |
| Endato | 5,427,459 | 5,427,459 | 0 | 0 | 0 | 0 |
| RocketReach | 3,199,535 | 3,199,535 | 0 | 0 | 0 | 0 |
| DRDB | 826,886 | 607,740 | 219,146 | 0 | 0 | 0 |
| Haymarket | 4,223,245 | 4,223,245 | 0 | 0 | 0 | 0 |

Percentages use all links within each source. Categories partition links. Distinct-email outcomes cannot be inferred by adding link counts. Unknown is NULL, not disagreement.

QuantumMedica supplies no usable vendor names: 1,705,722 of its 1,705,723 links are unknown, and the single no-match link is the row whose email value is the literal text `email`. Among the other sources, Endato has the smallest match share (36.85%) and DRDB the largest (72.65%). Haymarket has the largest unknown share (4.54%) of the sources with names, followed by Medscape (1.22%).

The all-version and latest columns differ only for Medscape: 1,396 of its 86,484 multi-version links, of which 1,269 are true over all versions and false for the latest version and 51 are true over all versions with a NULL latest result. HealthLink has multi-version links, but its latest column equals the all-version column by construction. DRDB's 219,146 multi-version links have no single latest version, so no latest comparison exists for them.

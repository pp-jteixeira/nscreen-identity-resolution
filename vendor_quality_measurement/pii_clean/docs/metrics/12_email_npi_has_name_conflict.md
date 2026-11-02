# Email–NPI name conflict

**Principle:** flag incompatible usable names reported for the same vendor/email/NPI link across all its versions and retained history.

**Where:** `iceberg.jteixeira_ipa.pii__int_<vendor>__metrics` and `iceberg.jteixeira_ipa.pii_clean`. Inputs: `source`, `email`, `npi`, `source_name_values`. Output: nullable boolean `email_npi_has_name_conflict`, one value per link.

## How it is computed

Collect the link's distinct usable names, across all its versions, into `pair_names`. Compare every pair. In this excerpt, `has_disagreeing_pair` means at least one pair fails the fuzzy first/last-name rules below; it is false when there is only one name or all pairs agree.

```sql
CASE WHEN cardinality(pair_names) = 0 THEN NULL
     ELSE has_disagreeing_pair
END AS email_npi_has_name_conflict
```

Both first and last names must agree under [metric 07's fuzzy rules](07_vendor_name_matches_registry_name.md): nicknames, shared tokens, permitted first-name prefixes and small spelling differences. First-name-only agreement is insufficient. Missing/partial names do not create disagreement; registry names never fill missing vendor names.

Every pair is checked: a compound surname cannot hide disagreement between SMITH and JONES. Different names attached only to different NPIs do not create this flag. The separate `has_conflict_linkage` metric checks competing NPIs at the observation time or within current undated vendor data.

HealthLink uses its retained HCP names without date alignment. This metric includes name changes between versions; `attribute_versions` shows when each name was observed. A true result does not establish an incorrect identity. Vendors remain separate.

## Real examples

Executed November 2, 2026, against `iceberg.jteixeira_ipa.pii_clean` snapshot `2837737034249693554`. These selected cases explain outcomes; they do not measure prevalence.

```sql
SELECT source, email, npi,
       transform(source_name_values, n -> n.first_name || ' ' || n.last_name) AS link_names,
       record_count, email_npi_has_name_conflict
FROM iceberg.jteixeira_ipa.pii_clean
WHERE (source = 'medscape' AND link_id IN ('001B3FAFCB6C15A16FE008A248CDAA336337B490832693299EB9C7A35BA856C2', '002C39C01CE6E6FA06DE1AEC726E467650530955C59B8BD36E122CFFC1C86704', '000079952FA31C8C7313E567F6212C3370FD86580B7D34D7A11477881D36A574'))
   OR (source = 'drdb' AND link_id IN ('001A3498B34018A99A784A356EDB76758FB2B1638503B859DC8C501E87BC8614', '004DE8F476B514C7086A49959873063169744EB1AEA5891F40630B2604698FA3'))
   OR (source = 'healthlink' AND link_id IN ('002AD8303F037864987A6EBDE43F518674B34D304B701429F97839A3CC562F6C'))
   OR (source = 'haymarket' AND link_id IN ('00002F95A062B49A66DC511705A527F648D6B7EBDCD336743F84F8280A853434'))
ORDER BY source, link_id
```

| source | email | npi | link_names | record_count | email_npi_has_name_conflict |
|---|---|---|---|---|---|
| drdb | pepinchop@hotmail.com | 1013919968 | ['RICHARD BELMONT', 'RICHARD JR'] | 2 | true |
| drdb | mbolton@hotmail.com | 1215956081 | ['MARY BOLTON', 'MARYBETH BOLTON'] | 2 | false |
| haymarket | liliane.vaal@bwmc.umms.org | 1225097603 | [] | 1 | NULL |
| healthlink | pranusha.naidu@adventhealth.com | 1487187506 | ['PRANUSHA BAXI', 'PRANUSHA NAIDU'] | 1 | true |
| medscape | drkotesh@hotmail.com | 1164600235 | [] | 1 | NULL |
| medscape | nowsayahhh@aol.com | 1255415253 | ['LINDA ALVAREZ-THULL', 'LINDA THULL'] | 2 | false |
| medscape | karen.broderick@dignityhealth.org | 1669823530 | ['KAREN BRODERICK', 'KAREN STRUPP'] | 2 | true |

**What differentiates these cases:**

- **Compatible spellings (false):** the Medscape link for `nowsayahhh@aol.com` holds LINDA ALVAREZ-THULL and LINDA THULL, which share a surname token. The DRDB link for `mbolton@hotmail.com` holds MARY BOLTON and MARYBETH BOLTON, which agree through the permitted first-name prefix.
- **Incompatible pair (true):** the Medscape link for `karen.broderick@dignityhealth.org` holds KAREN BRODERICK and KAREN STRUPP, and the HealthLink link for `pranusha.naidu@adventhealth.com` holds PRANUSHA BAXI and PRANUSHA NAIDU. The first names agree but the last names do not, which is not enough.
- **Parsing effect (true):** the DRDB link for `pepinchop@hotmail.com` holds RICHARD BELMONT and RICHARD JR. The suffix JR was parsed as a last name, so the flag compares parsed pairs and does not show that two people share the email.
- **No usable names (NULL):** the Haymarket link and the Medscape link for `drkotesh@hotmail.com` have no usable names, so the result is NULL rather than false.

## Statistics by source

Measured **November 2, 2026** from `iceberg.jteixeira_ipa.pii_clean` snapshot `2837737034249693554`. These are exact published-population counts across retained eligible history, not a sample. Source data period (first to last observed day): HealthLink 2026-01-07 to 2026-10-03, QuantumMedica 2025-09-14 to 2026-10-15, Medscape 2024-01-10 to 2026-11-01 and Haymarket 2021-07-06 (a single day). Endato, RocketReach and DRDB are undated.

[Statistics SQL](../../sql/statistics/12_email_npi_has_name_conflict.sql)

| Source | Links | True: links, n (%) | False: links, n (%) | Unknown: links, n (%) |
|---|---|---|---|---|
| HealthLink | 7,688,451 | 51 (0.000663%) | 7,687,885 (99.992638%) | 515 (0.006698%) |
| QuantumMedica | 1,705,723 | 0 (0.000000%) | 1 (0.000059%) | 1,705,722 (99.999941%) |
| Medscape | 3,661,537 | 2,885 (0.078792%) | 3,613,951 (98.700382%) | 44,701 (1.220826%) |
| Endato | 5,427,459 | 0 (0.000000%) | 5,427,237 (99.995910%) | 222 (0.004090%) |
| RocketReach | 3,199,535 | 0 (0.000000%) | 3,197,577 (99.938804%) | 1,958 (0.061196%) |
| DRDB | 826,886 | 10,781 (1.303807%) | 816,043 (98.688695%) | 62 (0.007498%) |
| Haymarket | 4,223,245 | 0 (0.000000%) | 4,031,331 (95.455769%) | 191,914 (4.544231%) |

Percentages use the source's links. A missing usable name pair leaves unknown; conflicting spellings do not prove different people.

Conflicts occur only where a link carries at least two usable names. Endato, RocketReach, Haymarket and QuantumMedica never carry more than one name per link, so they have no conflicts (QuantumMedica has one false link, the placeholder row). The measured conflicts are DRDB 10,781 links (1.303807%), Medscape 2,885 links (0.078792%) and HealthLink 51 links (0.000663%). Unknown links are 4.544231% of Haymarket and 1.220826% of Medscape, and 99.999941% of QuantumMedica.

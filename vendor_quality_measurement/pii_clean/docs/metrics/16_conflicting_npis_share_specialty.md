# Conflicting NPIs share an NPPES specialty

**Question:** does another NPI in this link’s conflict context share an exact recognized NPPES taxonomy code? Vendor-reported specialty and profession are not compared. Separate published metrics `conflicting_npis_share_vendor_specialty` and `conflicting_npis_share_vendor_profession` compare vendor labels.

**Target:** `conflicting_npis_share_nppes_specialty`, `specialty_code_values`, `specialty_reference_table`, `specialty_definition_version`, `conflicting_npi_specialty_comparisons` in `iceberg.jteixeira_ipa.pii__int_<vendor>__metrics` and `iceberg.jteixeira_ipa.pii_clean`. One row per source/email/NPI link; key: `source`, `link_id`.

## How it is computed

Join the link's `npi` to text-converted `iceberg.npi.nppes_npidata_latest.npi`. Read `healthcare_provider_taxonomy_code_1` through `_15`. Trim, uppercase, validate against `iceberg.npi.npi_taxonomy.code`, and deduplicate per NPI. Include all slots without preferring primary flags. Vendor specialty labels and broad classification names are not substituted. Taxonomy evidence depends only on the NPI, so every version of a link shares it.

Compare other NPIs within vendor/email on exact overlapping `conflict_days`; Endato, RocketReach and both DRDB feeds use undated vendor contexts, so every other NPI of the email is a peer. Simplified peer expression:

```sql
CASE WHEN cardinality(specialty_code_values) > 0
          AND cardinality(peer.specialties) > 0
     THEN arrays_overlap(specialty_code_values, peer.specialties)
END AS shares_specialty
```

Any match gives true. False requires known disjoint retained sets for every peer. Otherwise null means missing evidence, unknown timing or inapplicable conflict. Preserve peer NPIs, dates, code sets and intersections. Lookup aggregation preserves link grain. This metric has no `_latest` form.

Current NPPES evidence is not aligned to historical vendor dates. Disjoint codes do not prove clinically unrelated providers; shared codes do not establish email ownership.

## Real examples

Executed November 2, 2026, against `iceberg.jteixeira_ipa.pii_clean` snapshot `2837737034249693554`. These selected cases explain outcomes; they do not measure prevalence.

```sql
SELECT source, email, npi, specialty_code_values,
       transform(conflicting_npi_specialty_comparisons, p -> p.npi || ': ' || array_join(p.specialty_codes, ', ')) AS peer_codes,
       has_conflict_linkage, conflicting_npis_share_nppes_specialty
FROM iceberg.jteixeira_ipa.pii_clean
WHERE (source = 'endato' AND link_id IN ('0007E8B8DE2379DD45E6831D231ACDE09D75987CFAB1F8E24E239D61F9F85C3C', '0007DCF798323647D6B39A339DA665A816D86BFA6E959327914ED2FEE1E6D827'))
   OR (source = 'medscape' AND link_id IN ('104FEB7B41C783C46968F7ADCC1FFAC4397B2B7A8DC8A5E29A197F1DEA75A987', '07F90157AC8FA07254DD4BF552EB4E4AEF27B83FDB65D97827B7FCDB7E7324A7', '49ACB9DAB9CDDA108843AC106AF50C1449EA9CBF288588A500407D2416A4D9BB'))
   OR (source = 'quantummedica' AND link_id IN ('B1BF32E78A2E6EDF12ACF41194D025D4BBF1C4828370D72D4E42629AD83095BB'))
   OR (source = 'healthlink' AND link_id IN ('011A4E3469D63171B176507DBDB51E1A4A7FE27976A32920F81AB683684A4A21'))
ORDER BY source, link_id
```

| source | email | npi | specialty_code_values | peer_codes | has_conflict_linkage | conflicting_npis_share_nppes_specialty |
|---|---|---|---|---|---|---|
| endato | kathy.emerson@gmail.com | 1730150061 | [] | ['1003393224: 363LF0000X'] | true | NULL |
| endato | haydnschroader@yahoo.com | 1700841624 | ['207R00000X'] | ['1265420996: 207RC0000X'] | true | false |
| healthlink | kchuang@memorialcare.org | 1205998929 | ['207P00000X'] | [] | false | NULL |
| medscape | usmanayubkhan@gmail.com | 1346658416 | ['207R00000X', '207RH0003X'] | ['1437227543: 207RN0300X'] | true | false |
| medscape | fangchenmd@gmail.com | 1407193790 | ['207R00000X', '208M00000X'] | ['1255455689: 207R00000X'] | true | true |
| medscape | jigneshpatel100@hotmail.com | 1639256696 | ['207Q00000X'] | ['1053334060: '] | true | NULL |
| quantummedica | aroman@prongersmith.com | 1174520019 | ['208100000X'] | ['1659335578: 208600000X'] | true | false |

**What differentiates these cases:**

- **Shared code (true):** the Medscape link for `fangchenmd@gmail.com` has codes `207R00000X` and `208M00000X`, and its peer has `207R00000X`. One exact code is enough.
- **Known disjoint codes (false):** the QuantumMedica link for `aroman@prongersmith.com` has `208100000X` and its peer has `208600000X`. The Medscape link for `usmanayubkhan@gmail.com` has `207R00000X` and `207RH0003X`, and its peer has `207RN0300X`.
- **Shared prefix is not a match (false):** the Endato link for `haydnschroader@yahoo.com` has `207R00000X` and its peer has `207RC0000X`. The codes share the prefix `207R` but not an exact value.
- **Missing evidence (NULL, unknown):** the Medscape link for `jigneshpatel100@hotmail.com` has `207Q00000X` but its peer has no codes. The Endato link for `kathy.emerson@gmail.com` has no codes although its peer has `363LF0000X`.
- **No conflict (NULL, not applicable):** the HealthLink link for `kchuang@memorialcare.org` has `207P00000X` but no conflict, so the metric does not apply.

## Statistics by source

Measured **November 2, 2026** from `iceberg.jteixeira_ipa.pii_clean` snapshot `2837737034249693554`. These are exact published-population counts across retained eligible history, not a sample. Source data period (first to last observed day): HealthLink 2026-01-07 to 2026-10-03, QuantumMedica 2025-09-14 to 2026-10-15, Medscape 2024-01-10 to 2026-11-01 and Haymarket 2021-07-06 (a single day). Endato, RocketReach and DRDB are undated.

[Statistics SQL 1](../../sql/statistics/16_conflicting_npis_share_specialty.sql) · [Statistics SQL 2](../../sql/statistics/16_conflicting_npis_share_specialty_statement_002.sql)

| Source | Links | With taxonomy codes, n (% of links) | Conflict links, n (% of links) | Shares a code, n (% of conflict links) | Different codes, n (% of conflict links) | Unknown, n (% of conflict links) |
|---|---|---|---|---|---|---|
| HealthLink | 7,688,451 | 7,675,098 (99.826324%) | 0 (0.000000%) | 0 (undefined) | 0 (undefined) | 0 (undefined) |
| QuantumMedica | 1,705,723 | 1,697,632 (99.525656%) | 56 (0.003283%) | 8 (14.285714%) | 48 (85.714286%) | 0 (0.000000%) |
| Medscape | 3,661,537 | 3,528,669 (96.371251%) | 32 (0.000874%) | 6 (18.750000%) | 22 (68.750000%) | 4 (12.500000%) |
| Endato | 5,427,459 | 5,238,071 (96.510559%) | 194,982 (3.592510%) | 21,991 (11.278477%) | 157,786 (80.923367%) | 15,205 (7.798156%) |
| RocketReach | 3,199,535 | 3,126,256 (97.709698%) | 65,846 (2.057987%) | 10,521 (15.978192%) | 50,906 (77.310695%) | 4,419 (6.711114%) |
| DRDB | 826,886 | 784,667 (94.894218%) | 14,832 (1.793718%) | 1,292 (8.710895%) | 11,699 (78.876753%) | 1,841 (12.412352%) |
| Haymarket | 4,223,245 | 4,040,009 (95.661251%) | 0 (0.000000%) | 0 (undefined) | 0 (undefined) | 0 (undefined) |

Coverage uses all links. Shared, different and unknown percentages use links with an established conflict. Zero-conflict percentages are undefined. Haymarket and HealthLink have no conflict links, so only their coverage is shown, and they have no outcome rows. No link has unknown conflict timing.

NPPES taxonomy evidence is available for most links in every source (from 94.894218% for DRDB to 99.826324% for HealthLink), so unknown outcomes are far fewer than for facilities. Different codes is the most common outcome: QuantumMedica 85.714286%, Endato 80.923367% and DRDB 78.876753%. Shared codes range from 8.710895% (DRDB) to 18.750000% (Medscape, 6 of 32 links). Unknown outcomes range from none (QuantumMedica) to 12.412352% (DRDB).

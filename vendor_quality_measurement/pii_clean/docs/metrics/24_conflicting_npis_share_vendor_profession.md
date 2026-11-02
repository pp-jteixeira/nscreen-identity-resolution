# 24. Conflicting NPIs share vendor profession

**Question:** does another NPI reported for the same vendor/email share a vendor profession on an eligible conflict date?

## How it is computed

Read `profession` from `iceberg.thirdparty.quantummedica_hcpmeta` and `iceberg.thirdparty.medscape_pii_meta_global`. Match NPI and exact delivery day; Medscape additionally matches registration `guid`, joining each GUID of the link only on that GUID's own observed days. Collapse duplicate metadata groups before joining. Missing metadata preserves the link with empty evidence arrays.

Normalize case and whitespace using the same rules as [vendor specialty](23_conflicting_npis_share_vendor_specialty.md). Unknown/unspecified placeholders, `OTHER` and CSV header labels are unusable. HealthLink provider-type codes and credentials, RocketReach job titles, NPPES entity types and specialty names do not supply fallback professions.

```sql
CASE WHEN cardinality(own_values) > 0 AND cardinality(peer_values) > 0
     THEN arrays_overlap(own_values, peer_values)
END AS shares_profession
```

Compare only different NPIs for the same vendor/email and actual conflict date. Any exact normalized overlap gives true. False requires all eligible comparisons to have usable disjoint values. Missing profession evidence, unknown timing or no applicable conflict gives NULL. The result is one value per link across all its days, versions and GUIDs; it has no `_latest` form. A shared broad profession does not prove shared identity or email ownership.

**Illustrative example:** two conflicting NPIs labelled `Physician` share profession even when their specialties differ. `Physician` and `Nurse/Advanced Practice Nurse` are disjoint labels. Credentials such as `MD` are not mapped to `Physician`.

`conflicting_npis_share_vendor_profession` retains `source_vendor_profession_values` and `conflicting_npi_vendor_profession_comparisons`. Shared `vendor_professional_evidence` preserves raw labels, normalized labels, delivery dates and source tables; its definition version identifies the comparison rules.

## Real examples

Executed November 2, 2026, against `iceberg.jteixeira_ipa.pii_clean` snapshot `2837737034249693554`. These selected cases explain outcomes; they do not measure prevalence.

```sql
SELECT source, email, npi, has_conflict_linkage, source_vendor_profession_values,
       conflicting_npis_share_vendor_profession, source_vendor_specialty_values,
       conflicting_npis_share_vendor_specialty
FROM iceberg.jteixeira_ipa.pii_clean
WHERE ROW(source, link_id) IN (
    ROW('medscape', '07F90157AC8FA07254DD4BF552EB4E4AEF27B83FDB65D97827B7FCDB7E7324A7'),
    ROW('medscape', '3CCA9A789F67035B76B5B720BC21BA5ECC7BFB0FB9E8B540C7FE1D851F930852'),
    ROW('medscape', '1751963BAF7F8719CCA77175665E582725B05C7D006D4915E13AA17C79DEFAF9'),
    ROW('medscape', '744566FD5593DAF536D095AB1739398F86408BCADDBA0529E41F81468588A1E4'),
    ROW('medscape', '000003E89687B0747799F66B933F62332C57BB2FD0FDFE3D96D63F41944A4C61'),
    ROW('quantummedica', '0411C6CA8D68C5ABE8FECFA3D00029BF7C461C8356B3A7AEB7A336877F30F528'),
    ROW('drdb', '00029C2772E1E1B93BE53EDB2ABE92C48087FE3E936210B3F61FB45FB591CC4A'))
ORDER BY source, link_id
```

| source | email | npi | has_conflict_linkage | source_vendor_profession_values | conflicting_npis_share_vendor_profession | source_vendor_specialty_values | conflicting_npis_share_vendor_specialty |
|---|---|---|---|---|---|---|---|
| drdb | redwards@mcvh-vcu.edu | 1831275874 | true | [] | NULL | [INTERNAL MEDICINE] | true |
| medscape | roadrunner262001@yahoo.com | 1003803560 | false | [NURSE/ADVANCED PRACTICE NURSE] | NULL | [ANESTHESIOLOGY] | NULL |
| medscape | usmanayubkhan@gmail.com | 1346658416 | true | [PHYSICIAN] | true | [HEMATOLOGY] | false |
| medscape | cdknoblauch@comcast.net | 1194772020 | true | [PHYSICIAN] | false | [OB/GYN & WOMEN'S HEALTH] | false |
| medscape | tonyatownsend2015@gmail.com | 1275748881 | true | [PHYSICIAN] | true | [GENERAL PRACTICE] | true |
| medscape | vlravenna@gmail.com | 243683 | true | [HEALTH BUSINESS/ADMINISTRATION, PHARMACIST] | false | [HIV/AIDS] | NULL |
| quantummedica | kshahzad@wwbh.org | 1407056278 | true | [] | NULL | [INTERNAL MEDICINE] | false |

**What differentiates these cases:** Medscape `usmanayubkhan@gmail.com` shares PHYSICIAN with its conflicting peer (true) even though its specialty comparison is false (HEMATOLOGY against another specialty); `tonyatownsend2015@gmail.com` shares PHYSICIAN as well. Medscape `cdknoblauch@comcast.net` is PHYSICIAN and its peer has no PHYSICIAN label (false). `vlravenna@gmail.com` carries HEALTH BUSINESS/ADMINISTRATION and PHARMACIST labels that its peer does not share (false), while its specialty comparison is NULL. Medscape `roadrunner262001@yahoo.com` has a profession label but no conflict, so the comparison is not applicable (NULL). QuantumMedica `kshahzad@wwbh.org` has a conflict but no usable profession label (NULL), and DRDB `redwards@mcvh-vcu.edu` has a conflict but no profession field (NULL), although both have specialty labels.

## Statistics by source

Measured **November 2, 2026** from `iceberg.jteixeira_ipa.pii_clean` snapshot `2837737034249693554`. These are exact published-population counts across retained eligible history, not a sample.

Source data period (first and last observed day): HealthLink 2026-01-07 to 2026-10-03, QuantumMedica 2025-09-14 to 2026-10-15, Medscape 2024-01-10 to 2026-11-01 and Haymarket 2021-07-06 (one snapshot day). Endato, RocketReach and DRDB are undated.

[Statistics SQL](../../sql/statistics/24_conflicting_npis_share_vendor_profession.sql)

| Source | Links | with vendor labels, n (%) | links with conflict, n | shared, n (% of conflict) | disjoint, n (% of conflict) | unknown, n (% of conflict) |
|---|---|---|---|---|---|---|
| HealthLink | 7,688,451 | 0 (0.000000%) | 0 | — | — | — |
| QuantumMedica | 1,705,723 | 0 (0.000000%) | 56 | 0 (0.000000%) | 0 (0.000000%) | 56 (100.000000%) |
| Medscape | 3,661,537 | 3,661,525 (99.999672%) | 32 | 28 (87.500000%) | 4 (12.500000%) | 0 (0.000000%) |
| Endato | 5,427,459 | 0 (0.000000%) | 194,982 | 0 (0.000000%) | 0 (0.000000%) | 194,982 (100.000000%) |
| RocketReach | 3,199,535 | 0 (0.000000%) | 65,846 | 0 (0.000000%) | 0 (0.000000%) | 65,846 (100.000000%) |
| DRDB | 826,886 | 0 (0.000000%) | 14,832 | 0 (0.000000%) | 0 (0.000000%) | 14,832 (100.000000%) |
| Haymarket | 4,223,245 | 0 (0.000000%) | 0 | — | — | — |

Label coverage uses all links. Outcome percentages use only links with an established conflict. Zero-conflict percentages are undefined (—), not measured zero agreement. Only Medscape and QuantumMedica read a profession field, and only Medscape fills it. Unsupported sources do not acquire fallback professions.

Only Medscape has usable profession labels (99.9997% of its links). Its 32 conflict links split into 28 shared (87.5%) and 4 disjoint (12.5%). QuantumMedica reads a profession field, but its source column `profession` in `iceberg.thirdparty.quantummedica_hcpmeta` holds no usable value (11 non-blank values among 11,206,173 rows, all the CSV header label, which is excluded), so its 56 conflict links are all unknown. Endato, RocketReach and DRDB conflicts are all unknown, and HealthLink and Haymarket have no conflict links.

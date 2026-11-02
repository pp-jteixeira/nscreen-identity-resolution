# 23. Conflicting NPIs share vendor specialty

**Question:** does another NPI reported for the same vendor/email share a vendor specialty on an eligible conflict date?

## How it is computed

HealthLink uses `iceberg.thirdparty.healthlink_hcp.specialty`, joined by NPI and exact delivery day. QuantumMedica uses the three specialty slots in `iceberg.thirdparty.quantummedica_hcpmeta`, also by NPI/day. Medscape uses those slots in `iceberg.thirdparty.medscape_pii_meta_global`, matching NPI, day and registration `guid`; each GUID of the link is joined only on that GUID's own observed days. Both DRDB feeds use the raw `specialty` labels of all versions of the undated link. Endato, RocketReach and Haymarket have no supported specialty input.

Trim, uppercase and collapse whitespace. Exclude blanks, nulls, unknown/unspecified placeholders, `OTHER`, and CSV column-header labels. Preserve punctuation and compare whole labels exactly; no synonym mapping, hierarchy expansion or delimiter splitting occurs. Raw labels remain in `vendor_professional_evidence`.

```sql
CASE WHEN cardinality(own_values) > 0 AND cardinality(peer_values) > 0
     THEN arrays_overlap(own_values, peer_values)
END AS shares_specialty
```

Compare different NPIs within source/email on the same actual conflict date. DRDB uses its available undated snapshot. Any matching peer/date gives true. False requires every comparison to be known and disjoint. Missing values or same-day metadata, unknown timing and no applicable conflict remain NULL. Metadata duplicates collapse before joining; no links are removed or multiplied. The result is one value per link across all its days, versions and GUIDs; it has no `_latest` form.

**Illustrative example:** ` family medicine ` matches `FAMILY MEDICINE`; `Cardiology` does not match `Internal Medicine/Cardiology`. Matching labels on different dates do not establish overlap.

`conflicting_npis_share_vendor_specialty` is accompanied by `source_vendor_specialty_values`, day-specific `vendor_professional_evidence`, `conflicting_npi_vendor_specialty_comparisons` and `vendor_professional_definition_version`. `source_vendor_specialty_values` is the display union across the link's observation days, versions and GUIDs; it never replaces date-specific comparison inputs. Each comparison entry identifies the peer by `npi` and `link_id`.

## Real examples

Executed November 2, 2026, against `iceberg.jteixeira_ipa.pii_clean` snapshot `2837737034249693554`. These selected cases explain outcomes; they do not measure prevalence.

```sql
SELECT source, email, npi, has_conflict_linkage, source_vendor_specialty_values,
       conflicting_npis_share_vendor_specialty
FROM iceberg.jteixeira_ipa.pii_clean
WHERE ROW(source, link_id) IN (
    ROW('drdb', '00029C2772E1E1B93BE53EDB2ABE92C48087FE3E936210B3F61FB45FB591CC4A'),
    ROW('drdb', '000237BCB5C91910BF9F50C3EAC9EC1056F541B8CFB012ABAFFCBA6FF98143FB'),
    ROW('medscape', '3CCA9A789F67035B76B5B720BC21BA5ECC7BFB0FB9E8B540C7FE1D851F930852'),
    ROW('medscape', '07F90157AC8FA07254DD4BF552EB4E4AEF27B83FDB65D97827B7FCDB7E7324A7'),
    ROW('medscape', '744566FD5593DAF536D095AB1739398F86408BCADDBA0529E41F81468588A1E4'),
    ROW('quantummedica', '19BB23311EE3B20FFF383F90B1BE273623215463DFBBE2837F5AB27F9CEB2F7C'),
    ROW('healthlink', '000003E1464D72618D55F78C6D464B854F2B8213906F0546468EE5C189A1376A'),
    ROW('endato', '00003802A8CE34DD8965C61E7BE1BB21523DEBE773892466127DA8BD78D03939'))
ORDER BY source, link_id
```

| source | email | npi | has_conflict_linkage | source_vendor_specialty_values | conflicting_npis_share_vendor_specialty |
|---|---|---|---|---|---|
| drdb | rnfrank@med.wayne.edu | 1265479042 | true | [OPTOMETRY] | false |
| drdb | redwards@mcvh-vcu.edu | 1831275874 | true | [INTERNAL MEDICINE] | true |
| endato | mmurray01@hotmail.com | 1033307111 | true | [] | NULL |
| healthlink | csteele@hotmail.com | 1720286941 | false | [NEONATAL-PERINATAL MEDICINE] | NULL |
| medscape | usmanayubkhan@gmail.com | 1346658416 | true | [HEMATOLOGY] | false |
| medscape | tonyatownsend2015@gmail.com | 1275748881 | true | [GENERAL PRACTICE] | true |
| medscape | vlravenna@gmail.com | 243683 | true | [HIV/AIDS] | NULL |
| quantummedica | robert.biggs@lvh.com | 1164417721 | true | [ALLOPATHIC & OSTEOPATHIC PHYSICIANS/INTERNAL MEDICINE, CARDIOVASCULAR DISEASE] | true |

**What differentiates these cases:** DRDB `redwards@mcvh-vcu.edu` shares INTERNAL MEDICINE with a conflicting NPI (true), while DRDB `rnfrank@med.wayne.edu` has OPTOMETRY and every peer label is different (false). Medscape `tonyatownsend2015@gmail.com` shares GENERAL PRACTICE with its peer (true). Medscape `usmanayubkhan@gmail.com` is HEMATOLOGY and its conflicting peer NPI is INTERNAL MEDICINE on the shared days (false). Medscape `vlravenna@gmail.com` has a conflict and a label, but its peer link has no usable specialty label, so the result is NULL. QuantumMedica `robert.biggs@lvh.com` shares its full raw label with its peer (true). HealthLink `csteele@hotmail.com` has a label but no conflict, so the comparison is not applicable (NULL). Endato `mmurray01@hotmail.com` has a conflict but no supported specialty input (NULL). DRDB compares its undated links; their NULL evidence day does not invent chronology.

## Statistics by source

Measured **November 2, 2026** from `iceberg.jteixeira_ipa.pii_clean` snapshot `2837737034249693554`. These are exact published-population counts across retained eligible history, not a sample.

Source data period (first and last observed day): HealthLink 2026-01-07 to 2026-10-03, QuantumMedica 2025-09-14 to 2026-10-15, Medscape 2024-01-10 to 2026-11-01 and Haymarket 2021-07-06 (one snapshot day). Endato, RocketReach and DRDB are undated.

[Statistics SQL](../../sql/statistics/23_conflicting_npis_share_vendor_specialty.sql)

| Source | Links | with vendor labels, n (%) | links with conflict, n | shared, n (% of conflict) | disjoint, n (% of conflict) | unknown, n (% of conflict) |
|---|---|---|---|---|---|---|
| HealthLink | 7,688,451 | 7,499,350 (97.540454%) | 0 | — | — | — |
| QuantumMedica | 1,705,723 | 1,705,722 (99.999941%) | 56 | 8 (14.285714%) | 48 (85.714286%) | 0 (0.000000%) |
| Medscape | 3,661,537 | 3,045,479 (83.174880%) | 32 | 8 (25.000000%) | 22 (68.750000%) | 2 (6.250000%) |
| Endato | 5,427,459 | 0 (0.000000%) | 194,982 | 0 (0.000000%) | 0 (0.000000%) | 194,982 (100.000000%) |
| RocketReach | 3,199,535 | 0 (0.000000%) | 65,846 | 0 (0.000000%) | 0 (0.000000%) | 65,846 (100.000000%) |
| DRDB | 826,886 | 826,886 (100.000000%) | 14,832 | 4,207 (28.364347%) | 10,625 (71.635653%) | 0 (0.000000%) |
| Haymarket | 4,223,245 | 0 (0.000000%) | 0 | — | — | — |

Label coverage uses all links. Outcome percentages use only links with an established conflict. Zero-conflict percentages are undefined (—), not measured zero agreement. Endato, RocketReach and Haymarket have no supported specialty labels, so their conflicts remain unknown.

Endato (194,982 links) and RocketReach (65,846) have the most conflict links, because undated vendors compare every other NPI of the email, and all of them are unknown. DRDB has 14,832 conflict links, of which 28.4% share a label and 71.6% are disjoint. Dated vendors have few conflict links: Medscape 32 (8 shared, 22 disjoint, 2 unknown) and QuantumMedica 56 (8 shared, 48 disjoint). HealthLink has labels for 97.5% of links but no link with a conflict, and Haymarket has neither.

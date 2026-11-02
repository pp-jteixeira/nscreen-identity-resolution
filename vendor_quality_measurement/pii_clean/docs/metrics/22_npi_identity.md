# 22. NPI validity and entity type

This metric checks identifier structure and reports whether NPPES identifies an individual or organization. Mathematical validity, registry presence, entity type and [lifecycle status](17_npi_registry_status.md) remain separate. None establishes email ownership or current clinical activity.

## How it is computed

The [macro](../../macros/npi_identity.sql) evaluates distinct `npi` values, then joins back to each source/email/NPI link without changing the link grain. The check applies to the main stored `npi`, not replacement, facility or peer identifiers. The stored value is not repaired, padded, stripped of punctuation or replaced. Upstream staging already trims vendor NPI text and preserves the original in each version's `record_payload` inside `attribute_versions`.

| Field | Rule |
|---|---|
| `npi_format_valid` | Exactly ten ASCII digits, beginning with 1–4. NULL for null, empty or whitespace-only input. |
| `npi_checksum_valid` | Luhn check over `80840` followed by the ten digits. NULL unless the input has ten ASCII digits. Evaluated independently of the prefix rule. |
| `npi_structure_valid` | Format and checksum both pass. Missing input stays NULL; malformed input is false. |
| `npi_structure_reason` | `missing`, `malformed`, `unsupported_prefix`, `checksum_failure`, then `valid`, in that priority order. |
| `npi_entity_type` | `individual`, `organization` or `unknown`, from registry consensus. |
| `npi_entity_type_reason` | `not_found`, `conflicting_reference_records`, `missing_entity_type`, `unrecognized_entity_type` or `registry_consensus`. |

Format follows the published [CMS claims-validation criteria](https://www.cms.gov/Regulations-and-Guidance/Guidance/Transmittals/downloads/R299OTN.pdf), including allowed leading digits 1–4. The [CMS checksum specification](https://www.cms.gov/Regulations-and-Guidance/Administrative-Simplification/NationalProvIdentStand/Downloads/NPIcheckdigit.pdf) adds the equivalent prefix contribution of 24. These are structural rules, not proof of issuance. Entity type never comes from the leading digit.

Registry evidence comes from `iceberg.npi.nppes_npidata_latest`, grouped by trimmed text `npi`. [NPPES entity codes](https://www.cms.gov/regulations-and-guidance/administrative-simplification/nationalprovidentstand/downloads/data_dissemination_file-code_values.pdf) are `1` for individual and `2` for organization. Duplicate identical codes agree. Trimmed blank/null counts as a missing variant; a known code mixed with missing evidence remains conflicting. A single unrecognized code stays unknown. Structural failure does not suppress registry evidence.

`npi_entity_type_evidence` retains distinct raw `ROW(entity_type_code varchar)` entries, including nulls. `npi_entity_type_reference_row_count` counts matched rows; `npi_entity_type_variant_count` counts normalized variants, including missing. No match gives an empty evidence array and zero counts. `npi_identity_as_of_day` records evaluation day, defaulting to America/New_York today, with an explicit override available. It is not a reference delivery date. `npi_identity_reference_table` and `npi_identity_definition_version` identify the source and rules.

## Real examples

Executed November 2, 2026, against `iceberg.jteixeira_ipa.pii_clean` snapshot `2837737034249693554`. These selected cases explain outcomes; they do not measure prevalence.

```sql
SELECT source, email, npi, npi_format_valid, npi_checksum_valid, npi_structure_valid,
       npi_structure_reason, npi_entity_type, npi_entity_type_reason,
       npi_entity_type_evidence, npi_entity_type_reference_row_count
FROM iceberg.jteixeira_ipa.pii_clean
WHERE ROW(source, link_id) IN (
    ROW('healthlink', '000003E1464D72618D55F78C6D464B854F2B8213906F0546468EE5C189A1376A'),
    ROW('medscape', '00023B3F88319FAC5964F6F86AEFF7C971BFC38751C583A7C0C303AF2EA66225'),
    ROW('medscape', '0173DFDCB0ECF0F29911314BAAB45F47CB8456628E52C1B80C41B5D9F938BACD'),
    ROW('medscape', '0008355B3A69057AFC8293EC703F6B765548A8642A788D6D2DC4628B2E33C512'),
    ROW('haymarket', '000C2F1A8B9EEC2BEC7FF38DD3D6E3EDD6341E8DED0CF98DB06898650C051B07'),
    ROW('medscape', '00006B53E946ECAC740ECC9A76001E908568285CB7982397EB7C54A1B09B86CE'),
    ROW('medscape', '00035B889083A0FFD47DE94A64500973091BA2FE8F841E264C38F975240BD022'))
ORDER BY npi_structure_reason, npi_entity_type_reason, link_id
```

| source | email | npi | npi_format_valid | npi_checksum_valid | npi_structure_valid | npi_structure_reason | npi_entity_type | npi_entity_type_reason | npi_entity_type_evidence | npi_entity_type_reference_row_count |
|---|---|---|---|---|---|---|---|---|---|---|
| medscape | aprilkimball23@gmail.com | 2019002623 | true | false | false | checksum_failure | unknown | not_found | [] | 0 |
| medscape | perftest170820201151263323495@yopmail.com | 1225185 | false | NULL | false | malformed | unknown | not_found | [] | 0 |
| medscape | dorafavy@gmail.com | 8136528886 | false | false | false | unsupported_prefix | unknown | not_found | [] | 0 |
| medscape | dsi2286@yahoo.com | 1750666087 | true | true | true | valid | unknown | missing_entity_type | [(entity_type_code: None)] | 1 |
| haymarket | mennasharaf82@yahoo.com | 1234567893 | true | true | true | valid | unknown | not_found | [] | 0 |
| healthlink | csteele@hotmail.com | 1720286941 | true | true | true | valid | individual | registry_consensus | [(entity_type_code: '1')] | 1 |
| medscape | perk@psychod.com | 1205856101 | true | true | true | valid | organization | registry_consensus | [(entity_type_code: '2')] | 1 |

**What differentiates these cases:** `1720286941` (HealthLink) passes every rule and NPPES reports entity type code `1`, so it is an individual with `registry_consensus`. `1205856101` (Medscape) is structurally valid and reports code `2`, an organization. `1750666087` is structurally valid and has one NPPES row whose type code is empty, so the entity type is `unknown` with `missing_entity_type`. `1234567893` (Haymarket) is structurally valid but has no NPPES row (`not_found`). `2019002623` has ten digits and an allowed prefix, but fails the checksum (`checksum_failure`, structure false, checksum false). `8136528886` fails both the prefix and the checksum, and the reason reports `unsupported_prefix` first. `1225185` is malformed, so the checksum result is NULL, and no registry match exists. The first digit does not encode entity type: individual and organization NPIs both begin with 1.

## Statistics by source

Measured **November 2, 2026** from `iceberg.jteixeira_ipa.pii_clean` snapshot `2837737034249693554`. These are exact published-population counts across retained eligible history, not a sample. The stored evaluation day (`npi_identity_as_of_day`) is 2026-11-02.

[Statistics SQL](../../sql/statistics/22_npi_identity.sql)

Structure (`npi_structure_reason`):

| Source | Distinct NPIs | Links | valid, n (%) | checksum failure, n (%) | malformed, n (%) | unsupported prefix, n (%) |
|---|---|---|---|---|---|---|
| HealthLink | 3,453,960 | 7,688,451 | 3,453,960 (100.000000%) | 0 (0.000000%) | 0 (0.000000%) | 0 (0.000000%) |
| QuantumMedica | 1,022,015 | 1,705,723 | 1,022,014 (99.999902%) | 0 (0.000000%) | 1 (0.000098%) | 0 (0.000000%) |
| Medscape | 2,191,605 | 3,661,537 | 2,181,214 (99.525873%) | 1,734 (0.079120%) | 8,394 (0.383007%) | 263 (0.012000%) |
| Endato | 1,194,462 | 5,427,459 | 1,194,462 (100.000000%) | 0 (0.000000%) | 0 (0.000000%) | 0 (0.000000%) |
| RocketReach | 593,028 | 3,199,535 | 593,028 (100.000000%) | 0 (0.000000%) | 0 (0.000000%) | 0 (0.000000%) |
| DRDB | 580,189 | 826,886 | 580,187 (99.999655%) | 2 (0.000345%) | 0 (0.000000%) | 0 (0.000000%) |
| Haymarket | 1,712,938 | 4,223,245 | 1,709,361 (99.791177%) | 3,577 (0.208823%) | 0 (0.000000%) | 0 (0.000000%) |

Entity type (`npi_entity_type`):

| Source | Distinct NPIs | Links | individual, n (%) | organization, n (%) | unknown, n (%) |
|---|---|---|---|---|---|
| HealthLink | 3,453,960 | 7,688,451 | 3,444,877 (99.737026%) | 0 (0.000000%) | 9,083 (0.262974%) |
| QuantumMedica | 1,022,015 | 1,705,723 | 1,017,306 (99.539244%) | 0 (0.000000%) | 4,709 (0.460756%) |
| Medscape | 2,191,605 | 3,661,537 | 2,098,626 (95.757493%) | 7,197 (0.328389%) | 85,782 (3.914118%) |
| Endato | 1,194,462 | 5,427,459 | 1,152,638 (96.498507%) | 214 (0.017916%) | 41,610 (3.483577%) |
| RocketReach | 593,028 | 3,199,535 | 579,639 (97.742265%) | 72 (0.012141%) | 13,317 (2.245594%) |
| DRDB | 580,189 | 826,886 | 547,524 (94.369938%) | 1,195 (0.205967%) | 31,470 (5.424095%) |
| Haymarket | 1,712,938 | 4,223,245 | 1,627,068 (94.986976%) | 907 (0.052950%) | 84,963 (4.960074%) |

Entity-type reason (`npi_entity_type_reason`):

| Source | Distinct NPIs | Links | registry consensus, n (%) | missing entity type, n (%) | not found, n (%) |
|---|---|---|---|---|---|
| HealthLink | 3,453,960 | 7,688,451 | 3,444,877 (99.737026%) | 5,723 (0.165694%) | 3,360 (0.097280%) |
| QuantumMedica | 1,022,015 | 1,705,723 | 1,017,306 (99.539244%) | 4,704 (0.460267%) | 5 (0.000489%) |
| Medscape | 2,191,605 | 3,661,537 | 2,105,823 (96.085882%) | 75,126 (3.427899%) | 10,656 (0.486219%) |
| Endato | 1,194,462 | 5,427,459 | 1,152,852 (96.516423%) | 41,608 (3.483409%) | 2 (0.000167%) |
| RocketReach | 593,028 | 3,199,535 | 579,711 (97.754406%) | 13,313 (2.244919%) | 4 (0.000675%) |
| DRDB | 580,189 | 826,886 | 548,719 (94.575905%) | 31,466 (5.423405%) | 4 (0.000689%) |
| Haymarket | 1,712,938 | 4,223,245 | 1,627,975 (95.039926%) | 81,059 (4.732162%) | 3,904 (0.227913%) |

Percentages use distinct NPIs within each source and stored evaluation day; the Links column counts source/email/NPI links. Structure, entity type and entity-reason distributions are separate and must not be summed. Source populations overlap. Mathematical validity does not prove issuance; missing registry evidence is not a conclusion about a provider's existence.

HealthLink, Endato and RocketReach NPIs are all structurally valid. Failures concentrate in Medscape (0.47% of NPIs, mostly 8,394 malformed values) and Haymarket (3,577 checksum failures, 0.21%). Individuals are at least 94.4% of NPIs in every source and organizations are absent from HealthLink and QuantumMedica. Unknown entity type is the sum of `missing_entity_type` and `not_found` in every source (no conflicting or unrecognized codes occur), and is highest for DRDB (5.4%) and Haymarket (5.0%).

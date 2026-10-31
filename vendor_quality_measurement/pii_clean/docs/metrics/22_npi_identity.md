# 22. NPI validity and entity type

This metric checks identifier structure and reports whether NPPES identifies an individual or organization. Mathematical validity, registry presence, entity type and [lifecycle status](17_npi_registry_status.md) remain separate. None establishes email ownership or current clinical activity.

## How it is computed

The [macro](../../macros/npi_identity.sql) evaluates distinct `npi` values, then joins back without changing any source record or email position. The check applies to the main stored `npi`, not replacement, facility or peer identifiers. The stored value is not repaired, padded, stripped of punctuation or replaced. Upstream staging already trims vendor NPI text and preserves the original in `record_payload`.

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

`npi_entity_type_evidence` retains distinct raw `ROW(entity_type_code varchar)` entries, including nulls. `npi_entity_type_reference_row_count` counts matched rows; `npi_entity_type_variant_count` counts normalized variants, including missing. No match gives an empty evidence array and zero counts. `npi_identity_as_of_day` records evaluation day, defaulting to Europe/Paris today, with an explicit override available. It is not a reference delivery date. `npi_identity_reference_table` and `npi_identity_definition_version` identify the source and rules.

## Real examples

Executed October 31, 2026, against canonical snapshot `8811920360682490090`. These selected cases explain outcomes; they do not measure prevalence.

[Executed example SQL](../../sql/examples/22_npi_identity.sql):

```sql
SELECT source, npi,
       npi_format_valid AS format_ok,
       npi_checksum_valid AS checksum_ok,
       npi_structure_reason AS structure_reason,
       npi_entity_type AS entity_type,
       npi_entity_type_reason AS entity_reason,
       transform(npi_entity_type_evidence, x -> x.entity_type_code) AS registry_codes,
       npi_identity_as_of_day AS as_of_day
FROM iceberg.jteixeira_ipa.pii_clean FOR VERSION AS OF 8811920360682490090
WHERE source = 'medscape'
  AND metric_row_id IN (
      '00042DFD2EA561D524FBCDA83E5B6BC990D5A9A812A530BBE3DFA0C549A284FE',
      '000000292E237796D17BEC9BB60DA00A81701AF9AE2B875BF008FEE8FE171D10',
      '00011E630C888A9F3B6D0B056B07877D4F6847B35C6A1A1DED8BE1516B56C4FD',
      '00000287D1459B8F05DA2E13092907BD3F5B2BE2772508A8112DE2F7D2D892B9',
      '002A106AB3246FFBA17BBB57755220C0FFD4B992583B69D5611A67AF8626D015',
      '00023ACB680E3BFCF0763E28CA1A0F80603DBC1A05F3FD95150280A8600F2216',
      '000C0DBF773B88D71F427DE968BA87E92010E239DA17BEABDE6301FF15245212'
  )
ORDER BY source, npi_structure_reason, npi_entity_type_reason, npi
```

| source | npi | format_ok | checksum_ok | structure_reason | entity_type | entity_reason | registry_codes | as_of_day |
|---|---|---|---|---|---|---|---|---|
| medscape | 1487194295 | true | false | checksum_failure | unknown | not_found | [] | 2026-10-30 |
| medscape | 12345 | false | NULL | malformed | unknown | not_found | [] | 2026-10-30 |
| medscape | 9919111017 | false | false | unsupported_prefix | unknown | not_found | [] | 2026-10-30 |
| medscape | 1235680307 | true | true | valid | unknown | missing_entity_type | [NULL] | 2026-10-30 |
| medscape | 2011017805 | true | true | valid | unknown | not_found | [] | 2026-10-30 |
| medscape | 1578866182 | true | true | valid | organization | registry_consensus | [2] | 2026-10-30 |
| medscape | 1871571513 | true | true | valid | individual | registry_consensus | [1] | 2026-10-30 |

**What differentiates these cases:** `12345` cannot receive a checksum result, while `1487194295` has the right format but fails its checksum. `9919111017` fails both checks; the reason reports the unsupported prefix first. `2011017805` passes structure but has no NPPES match. `1235680307` has a registry match with a missing type code. Both the individual and organization examples begin with 1, showing that the first digit does not encode entity type.

## Statistics by source

Measured **October 31, 2026** from `iceberg.jteixeira_ipa.pii_clean` snapshot `8811920360682490090`. These are exact published-population counts across retained eligible history, not a sample. Stored evaluation dates remain unchanged.

[Executed statistics SQL](../../sql/statistics/22_npi_identity.sql)

| Source | Stored evaluation day | Distinct NPIs | Structurally valid, n (%) | Individual, n (%) | Organization, n (%) | Unknown type, n (%) |
|---|---|---|---|---|---|---|
| HealthLink | 2026-10-30 | 3,453,960 | 3,453,960 (100.000000%) | 3,444,877 (99.737026%) | 0 (0.000000%) | 9,083 (0.262974%) |
| QuantumMedica | 2026-10-30 | 1,022,015 | 1,022,014 (99.999902%) | 1,017,306 (99.539244%) | 0 (0.000000%) | 4,709 (0.460756%) |
| Medscape | 2026-10-30 | 2,190,514 | 2,180,123 (99.525636%) | 2,097,536 (95.755425%) | 7,197 (0.328553%) | 85,781 (3.916022%) |
| Endato | 2026-10-30 | 1,194,462 | 1,194,462 (100.000000%) | 1,152,638 (96.498507%) | 214 (0.017916%) | 41,610 (3.483577%) |
| RocketReach | 2026-10-30 | 593,028 | 593,028 (100.000000%) | 579,639 (97.742265%) | 72 (0.012141%) | 13,317 (2.245594%) |
| DRDB | 2026-10-30 | 580,189 | 580,187 (99.999655%) | 547,524 (94.369938%) | 1,195 (0.205967%) | 31,470 (5.424095%) |
| Haymarket | 2026-10-30 | 1,712,938 | 1,709,361 (99.791177%) | 1,627,068 (94.986976%) | 907 (0.052950%) | 84,963 (4.960074%) |

Percentages use distinct NPIs within each source and stored evaluation day. Structure, entity type and entity-reason distributions are separate and must not be summed. Source populations overlap. Mathematical validity does not prove issuance; missing registry evidence is not a conclusion about a provider’s existence.

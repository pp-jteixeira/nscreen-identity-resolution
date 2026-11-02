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

`npi_entity_type_evidence` retains distinct raw `ROW(entity_type_code varchar)` entries, including nulls. `npi_entity_type_reference_row_count` counts matched rows; `npi_entity_type_variant_count` counts normalized variants, including missing. No match gives an empty evidence array and zero counts. `npi_identity_as_of_day` records evaluation day, defaulting to Europe/Paris today, with an explicit override available. It is not a reference delivery date. `npi_identity_reference_table` and `npi_identity_definition_version` identify the source and rules.

## Real examples

No executed examples exist yet for this definition.

**What differentiates outcomes:** a malformed value such as `12345` cannot receive a checksum result, while a ten-digit value with an allowed prefix can still fail its checksum. A value that fails both the prefix and checksum rules reports the unsupported prefix first. A structurally valid NPI can still have no NPPES match, or a registry match with a missing type code. Individual and organization NPIs can both begin with 1, so the first digit does not encode entity type.

## Statistics by source

No measurements exist yet for this definition.

[Statistics SQL](../../sql/statistics/22_npi_identity.sql)

Percentages use distinct NPIs within each source and stored evaluation day. Structure, entity type and entity-reason distributions are separate and must not be summed. Source populations overlap. Mathematical validity does not prove issuance; missing registry evidence is not a conclusion about a provider’s existence.

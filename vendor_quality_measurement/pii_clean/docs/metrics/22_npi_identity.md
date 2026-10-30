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

## Real examples: contrasting outcomes

Seven real Medscape records, queried October 30, 2026, from the validated candidate `iceberg.jteixeira_ipa.pii_clean_candidate_npi_identity_39b808aed2af` at snapshot `2593466519988720108`. **Metric 22 is not yet published to canonical `pii_clean`.** Each selected key identifies one exact source record and email position. These cases illustrate outcomes, not prevalence. Emails and names are omitted; NPI values are displayed unchanged.

The query aliases stored fields for display and projects the raw entity codes from their evidence rows. `[]` means no registry match; `[NULL]` means a matched row with no entity code. The evaluation date is not a reference delivery date.

[Runnable example SQL](../../sql/examples/22_npi_identity.sql):

```sql
SELECT source, npi,
       npi_format_valid AS format_ok,
       npi_checksum_valid AS checksum_ok,
       npi_structure_reason AS structure_reason,
       npi_entity_type AS entity_type,
       npi_entity_type_reason AS entity_reason,
       transform(npi_entity_type_evidence, x -> x.entity_type_code) AS registry_codes,
       npi_identity_as_of_day AS as_of_day
FROM iceberg.jteixeira_ipa.pii_clean_candidate_npi_identity_39b808aed2af FOR VERSION AS OF 2593466519988720108
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

**Result:** 7 rows.

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

No conflicting or unrecognized entity-code outcomes occurred in the measured candidate population, so none is invented here. Reproduction requires the pinned candidate snapshot to remain available. Query ID: `20261030_124025_36476_6efcm`.

## Statistics and validation

[Standalone statistics SQL](../../sql/statistics/22_npi_identity.sql) returns separate structure, entity-type and entity-reason distributions. Each vendor/NPI contributes once to identifier counts; its retained records contribute to record counts. Percentages use all identifiers or all records within that vendor and evaluation date. The three distributions overlap and must not be summed together. Vendor distinct-NPI counts also overlap and cannot be summed into a global provider count. Missing-key records remain in staging and are outside the published metric population.

Tests cover the CMS checksum example, generated checksums for allowed and unsupported prefixes, Unicode and malformed values, missing input, absent references, duplicate/conflicting/missing codes, record preservation and independent invariant failures. Current registry evidence does not reconstruct entity type on historical vendor observation days. No scores, row filters or lifecycle changes are applied.

### Candidate population, October 30, 2026

Measured from the validated candidate below, not yet the canonical publication. Each percentage uses the vendor’s distinct-NPI denominator. Original records are retained. Vendor populations overlap, so their distinct-NPI counts must not be summed.

| Vendor | Distinct NPIs | Structurally valid | Individual | Organization | Unknown type |
|---|---:|---:|---:|---:|---:|
| drdb | 580,189 | 580,187 (99.99966%) | 547,524 (94.36994%) | 1,195 (0.20597%) | 31,470 (5.42409%) |
| endato | 1,194,462 | 1,194,462 (100.00000%) | 1,152,638 (96.49851%) | 214 (0.01792%) | 41,610 (3.48358%) |
| haymarket | 1,712,938 | 1,709,361 (99.79118%) | 1,627,068 (94.98698%) | 907 (0.05295%) | 84,963 (4.96007%) |
| healthlink | 3,453,960 | 3,453,960 (100.00000%) | 3,444,877 (99.73703%) | 0 (0.00000%) | 9,083 (0.26297%) |
| medscape | 2,190,293 | 2,179,902 (99.52559%) | 2,097,309 (95.75472%) | 7,197 (0.32859%) | 85,787 (3.91669%) |
| quantummedica | 1,022,015 | 1,022,014 (99.99990%) | 1,017,306 (99.53924%) | 0 (0.00000%) | 4,709 (0.46076%) |
| rocketreach | 593,028 | 593,028 (100.00000%) | 579,639 (97.74227%) | 72 (0.01214%) | 13,317 (2.24559%) |

Medscape has 10,391 structurally invalid NPIs: 8,394 malformed values, 1,734 checksum failures and 263 unsupported prefixes. Haymarket has 3,577 checksum failures, DRDB has two, and QuantumMedica has one malformed value. Structural reasons use the documented priority order; individual flags remain available for overlapping failures.

Unknown entity types reflect missing NPPES codes or absent reference records. No conflicting or unrecognized entity-code outcomes appeared in these vendor populations. These results do not establish why codes are missing or whether an absent NPI was ever issued.

Executed [statistics SQL](../../sql/statistics/22_npi_identity.sql) with the published-table relation replaced by `iceberg.jteixeira_ipa.pii_clean_candidate_npi_identity_39b808aed2af`, snapshot `2593466519988720108`. The candidate reads canonical snapshot `8096642935433856886` and NPPES snapshot `4824930614863268861`. [Candidate validation and publication status](../../results/npi_identity_20261030/report.md).

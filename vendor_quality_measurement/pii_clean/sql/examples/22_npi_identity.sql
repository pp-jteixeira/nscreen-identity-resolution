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

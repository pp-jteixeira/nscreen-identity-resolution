-- Stored name comparisons from the verified core, October 31 2026
SELECT m.source, m.metric_row_id, m.email, m.npi,
       e.source_first_name, e.source_last_name,
       e.registry_first_name, e.registry_last_name,
       e.first_name_match_kind, e.last_name_match_kind, e.match_class,
       e.comparison_vendor_match, m.vendor_name_matches_registry_name AS record_vendor_match,
       m.vendor_registry_match_classes, m.name_match_evaluated_at, m.name_match_definition_version
FROM iceberg.jteixeira_ipa.pii__int_pii__metrics FOR VERSION AS OF 3003274000539755025 m
CROSS JOIN UNNEST(m.name_match_evidence) AS e(
    source_first_name, source_last_name, registry_first_name, registry_last_name,
    first_name_match_kind, last_name_match_kind, match_class,
    email_matches_source_name, email_matches_registry_name, comparison_vendor_match)
WHERE (m.source = 'endato'
  AND m.metric_row_id IN (
      '06AB31EC5574E57D8BB1D4D59458B398E5389AD406E98827B2DC8823A8DB5763',
      '001632ED6AB8E6E8E2C8D203E1988812E3F950707428DBA8D78289AB202A87CC',
      '00B93621FC5F2483F73C12B32DECBAD80480445C3CD407F0322BFF1A8E12D2B7',
      '0266F98E9735CB80EDAF62E5EAB302C958544CDFD4E70512AC1EFC7DAFCA7898',
      '5E463BFBBFA7821EA11FD393E13084C53B86EE3F55799BD657C9040A7F8E7460',
      '0457353A2653E64F33BC90E1AA0FC845139B0055EEAAD8FF6E861054D7751091',
      '01F2DBC4D54F8DCB79678C8F5AC82F7828B0EFC6ECBFC06DB1E15FE592682357',
      '4EECBDD928AADF1D1FDB329664AB8B99D218EB6B4733CDAC63A3BD71F90E18E5',
      'DCB1AB6D00A4FF0F1B7A787BD6341A1240E38F5A55DAFCA2A37CCF506A0BDFD9'
  )) OR (m.source = 'healthlink' AND m.metric_row_id IN (
      '8DC2FAC07EDFFA360BDFDF799686AC1B272A7B36687BFD56F26BC14C3A0CBDEC',
      '68F30A7549648B7914AED7460DD6D63E766331459FC0214B2B131E8704DBC2DA'
  ))
ORDER BY m.npi, m.metric_row_id, e.match_class, e.source_first_name, e.source_last_name,
         e.registry_first_name, e.registry_last_name

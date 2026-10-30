SELECT DISTINCT
    m.source,
    m.npi,
    concat(s.first_name, ' ', s.last_name) AS vendor_name,
    concat(r.first_name, ' ', r.last_name) AS registry_name,
    m.source_name_usable,
    m.registry_name_usable,
    m.vendor_name_matches_registry_name AS matches
FROM iceberg.jteixeira_ipa.pii_clean m
LEFT JOIN UNNEST(m.source_name_values)
    AS s(first_name, last_name, first_variants) ON true
LEFT JOIN iceberg.jteixeira_ipa.pii__int_npi__names r ON m.npi = r.npi
WHERE m.source = 'endato'
  AND m.metric_row_id IN (
      '06AB31EC5574E57D8BB1D4D59458B398E5389AD406E98827B2DC8823A8DB5763',
      '001632ED6AB8E6E8E2C8D203E1988812E3F950707428DBA8D78289AB202A87CC',
      '00B93621FC5F2483F73C12B32DECBAD80480445C3CD407F0322BFF1A8E12D2B7',
      '0266F98E9735CB80EDAF62E5EAB302C958544CDFD4E70512AC1EFC7DAFCA7898',
      '5E463BFBBFA7821EA11FD393E13084C53B86EE3F55799BD657C9040A7F8E7460',
      '0457353A2653E64F33BC90E1AA0FC845139B0055EEAAD8FF6E861054D7751091',
      '01F2DBC4D54F8DCB79678C8F5AC82F7828B0EFC6ECBFC06DB1E15FE592682357'
  )
ORDER BY m.npi

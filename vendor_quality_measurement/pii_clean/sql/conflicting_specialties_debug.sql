-- After specialty publication: inspect exact standardized codes and peer/date contexts.
SELECT source, metric_row_id, email, npi, specialty_code_values,
       specialty_reference_table, specialty_definition_version,
       observed_days, conflict_days, conflicting_npis_share_specialty,
       peer_npi, overlapping_days, peer_codes, shared_codes, shares_specialty
FROM iceberg.jteixeira_ipa.pii_clean
CROSS JOIN UNNEST(conflicting_npi_specialty_comparisons)
    AS peer(peer_npi, overlapping_days, peer_codes, shared_codes, shares_specialty)

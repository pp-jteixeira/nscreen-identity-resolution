-- Inspect stored facility identifiers and exact peer/date contexts.
SELECT source, metric_row_id, email, npi, facility_npi_values,
       facility_reference_table, facility_definition_version,
       observed_days, conflict_days, conflicting_npis_share_facility,
       peer_npi, overlapping_days, peer_facilities, shared_facilities, shares_facility
FROM iceberg.jteixeira_ipa.pii_clean
CROSS JOIN UNNEST(conflicting_npi_facility_comparisons)
    AS peer(peer_npi, overlapping_days, peer_facilities, shared_facilities, shares_facility)

-- Post-publication inspection for one email; no query has been executed here.
SELECT source, metric_row_id, npi, source_state_values, facility_primary_state,
       facility_reference_status, facility_rank1_rows, facility_rank1_state_count,
       vendor_state_evidence, vendor_state_corroborated, location_evaluation_day
FROM iceberg.jteixeira_ipa.pii_clean
WHERE email = lower(trim('person@example.test'))
ORDER BY source, npi, metric_row_id

-- Post-publication summary inspection; these are counts/states, not raw UID mappings.
SELECT source, metric_row_id, npi, cookie_location_status, cookie_count,
       cookie_mapped_uid_days, cookie_observed_uid_days, cookie_located_uid_days,
       cookie_eligible_uid_days, cookie_state_values, cookie_uid_types,
       cookie_primary_state_tied_count, cookie_primary_state_multistate_count,
       cookie_vendor_state_evidence, cookie_facility_state_evidence,
       cookie_location_first_day, cookie_location_last_day,
       cookie_mapping_missing_days, cookie_location_missing_days,
       cookie_location_window_start, cookie_location_window_end
FROM iceberg.jteixeira_ipa.pii_clean
WHERE email = lower(trim('person@example.test'))
ORDER BY source, npi, metric_row_id

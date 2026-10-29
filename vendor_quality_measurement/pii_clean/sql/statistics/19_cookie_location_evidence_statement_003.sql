-- Statistics over published evidence in iceberg.jteixeira_ipa.pii_clean.
-- Reference evidence and evaluation dates come from the stored publication.
SELECT source,
       CASE WHEN grouping(cookie_location_status) = 0 THEN 'location_status'
            WHEN grouping(cookie_vendor_state_evidence) = 0 THEN 'vendor_state'
            WHEN grouping(cookie_facility_state_evidence) = 0 THEN 'facility_state'
            ELSE 'totals' END AS section,
       cookie_location_status, cookie_vendor_state_evidence, cookie_facility_state_evidence,
       count(*) AS metric_rows, count(DISTINCT metric_row_id) AS unique_metric_rows,
       count(DISTINCT ROW(email, npi)) AS distinct_links, count(DISTINCT email) AS distinct_emails,
       count_if(cookie_count IS NULL OR cookie_count < 0
   OR cookie_mapped_uid_days < cookie_count
   OR cookie_observed_uid_days > cookie_mapped_uid_days
   OR cookie_located_uid_days > cookie_observed_uid_days
   OR cookie_eligible_uid_days > cookie_located_uid_days
   OR cookie_located_count > cookie_count
   OR cookie_primary_state_tied_count > cookie_count
   OR cookie_primary_state_multistate_count > cookie_count
   OR cookie_mapping_days > 7 OR cookie_eligible_observed_days > cookie_mapping_days
   OR cookie_state_values IS NULL OR cookie_uid_types IS NULL
   OR cookie_state_values IS DISTINCT FROM array_sort(array_distinct(cookie_state_values))
   OR cookie_state_count <> cardinality(cookie_state_values)
   OR (cookie_eligible_uid_days > 0) IS DISTINCT FROM (cookie_location_status = 'observed')
   OR (cookie_eligible_uid_days = 0) IS DISTINCT FROM (cookie_location_first_day IS NULL)
   OR (cookie_eligible_uid_days = 0) IS DISTINCT FROM (cookie_location_last_day IS NULL)
   OR cookie_location_first_day < cookie_location_window_start
   OR cookie_location_last_day > cookie_location_window_end
   OR cookie_location_first_day > cookie_location_last_day
   OR cookie_mapping_available_days + cardinality(cookie_mapping_missing_days) <> 7
   OR cookie_location_available_days + cardinality(cookie_location_missing_days) <> 7
   OR cookie_location_window_status IS DISTINCT FROM
      CASE WHEN cookie_mapping_available_days = 7 AND cookie_location_available_days = 7
           THEN 'all_source_days_present' ELSE 'missing_source_days' END
   OR (cookie_count = 0 AND (cookie_location_status <> 'no_mapping' OR cardinality(cookie_state_values) <> 0))
   OR cookie_vendor_state_evidence IS DISTINCT FROM
      CASE WHEN cookie_location_status <> 'observed' THEN 'unknown_cookie_location'
           WHEN cardinality(source_state_values) = 0 THEN 'unknown_reference_state'
           WHEN cardinality(array_intersect(source_state_values, cookie_state_values)) = 0 THEN 'not_observed'
           WHEN cardinality(source_state_values) = 1 AND cookie_state_count = 1 THEN 'corroborated'
           ELSE 'mixed_state_evidence' END) AS invariant_failures,
       count(DISTINCT IF(cookie_primary_state_tied_count > 0, email, NULL)) AS emails_with_tied_uids,
       count(DISTINCT IF(cookie_primary_state_multistate_count > 0, email, NULL)) AS emails_with_multistate_uids
FROM iceberg.jteixeira_ipa.pii_clean
GROUP BY GROUPING SETS ((source), (source,cookie_location_status),
    (source,cookie_vendor_state_evidence), (source,cookie_facility_state_evidence))
ORDER BY source, section, cookie_location_status, cookie_vendor_state_evidence, cookie_facility_state_evidence

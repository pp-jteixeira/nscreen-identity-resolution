SELECT source, count(*) AS failing_metric_rows
FROM {{ ref(var('metric_model')) }}
WHERE cookie_location_window_days IS NULL OR cookie_location_window_days < 1
   OR date_diff('day', cookie_location_window_start, cookie_location_window_end) + 1 <> cookie_location_window_days
   OR cookie_location_status IS NULL
   OR cookie_location_status NOT IN ('no_mapping', 'observed', 'ambiguous_primary_state', 'unknown_state', 'no_state_observation') OR cookie_count IS NULL OR cookie_count < 0
   OR cookie_mapped_uid_days < cookie_count
   OR cookie_observed_uid_days > cookie_mapped_uid_days
   OR cookie_located_uid_days > cookie_observed_uid_days
   OR cookie_eligible_uid_days > cookie_located_uid_days
   OR cookie_located_count > cookie_count
   OR cookie_primary_state_tied_count > cookie_count
   OR cookie_primary_state_multistate_count > cookie_count
   OR cookie_mapping_days > cookie_location_window_days OR cookie_eligible_observed_days > cookie_mapping_days
   OR cookie_state_values IS NULL OR cookie_uid_types IS NULL
   OR cookie_state_values IS DISTINCT FROM array_sort(array_distinct(cookie_state_values))
   OR cookie_state_count <> cardinality(cookie_state_values)
   OR (cookie_eligible_uid_days > 0) IS DISTINCT FROM (cookie_location_status = 'observed')
   OR (cookie_eligible_uid_days = 0) IS DISTINCT FROM (cookie_location_first_day IS NULL)
   OR (cookie_eligible_uid_days = 0) IS DISTINCT FROM (cookie_location_last_day IS NULL)
   OR cookie_location_first_day < cookie_location_window_start
   OR cookie_location_last_day > cookie_location_window_end
   OR cookie_location_first_day > cookie_location_last_day
   OR cookie_mapping_available_days + cardinality(cookie_mapping_missing_days) <> cookie_location_window_days
   OR cookie_location_available_days + cardinality(cookie_location_missing_days) <> cookie_location_window_days
   OR cookie_location_window_status IS DISTINCT FROM
      CASE WHEN cookie_mapping_available_days = cookie_location_window_days AND cookie_location_available_days = cookie_location_window_days
           THEN 'all_source_days_present' ELSE 'missing_source_days' END
   OR (cookie_count = 0 AND (cookie_location_status <> 'no_mapping' OR cardinality(cookie_state_values) <> 0))
   OR cookie_vendor_state_evidence IS DISTINCT FROM
      CASE WHEN cookie_location_status <> 'observed' THEN 'unknown_cookie_location'
           WHEN cardinality(source_state_values) = 0 THEN 'unknown_reference_state'
           WHEN cardinality(array_intersect(source_state_values, cookie_state_values)) = 0 THEN 'not_observed'
           WHEN cardinality(source_state_values) = 1 AND cookie_state_count = 1 THEN 'corroborated'
           ELSE 'mixed_state_evidence' END
GROUP BY source

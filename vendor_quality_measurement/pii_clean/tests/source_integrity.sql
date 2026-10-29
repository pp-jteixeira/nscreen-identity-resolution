-- Return failed checks. Calculate all totals in one pass over the metric view.
WITH totals AS (
    SELECT count(*) - count(DISTINCT ROW(source, metric_row_id)) AS duplicate_keys,
           count_if(source IS NULL OR email IS NULL OR npi IS NULL OR email = '' OR npi = '' OR metric_row_id IS NULL OR record_id IS NULL OR record_payload IS NULL OR email_ordinal IS NULL OR email_ordinal < 1 OR email_origin IS NULL) AS empty_keys,
           count_if(first_seen_day > last_seen_day) AS reversed_dates,
           count_if(observation_count < 1 OR undated_observation_count > observation_count
               OR invalid_day_observation_count > undated_observation_count
               OR observed_day_count > observation_count - undated_observation_count) AS invalid_counts,
           count_if((observed_day_count IS NULL) <> (first_seen_day IS NULL)
               OR (first_seen_day IS NULL) <> (last_seen_day IS NULL)) AS inconsistent_dates,
           count_if(email_format_valid IS DISTINCT FROM {{ email_format_valid('email') }}) AS email_format_mismatch,
           count_if(email_role_account IS NULL OR email_role_account IS DISTINCT FROM {{ email_role_account('email') }}) AS email_role_mismatch,
           count_if(email_domain_class IS NULL OR email_domain_class NOT IN ('institutional', 'free', 'custom', 'unknown')
               OR email_domain_class IS DISTINCT FROM {{ email_domain_class('email') }}) AS email_domain_mismatch,
           count_if(source_name_usable IS NULL OR registry_name_usable IS NULL OR registry_npi_present IS NULL
               OR (email_matches_source_name IS NOT NULL) IS DISTINCT FROM source_name_usable
               OR (email_matches_registry_name IS NOT NULL) IS DISTINCT FROM registry_name_usable
               OR (vendor_name_matches_registry_name IS NOT NULL) IS DISTINCT FROM (source_name_usable AND registry_name_usable)
               OR (registry_name_usable AND NOT registry_npi_present)) AS name_coverage_mismatch,
           count_if(email_npi_count IS NULL OR email_npi_count < 1
               OR email_has_multiple_npis IS DISTINCT FROM (email_npi_count > 1)) AS multiplicity_mismatch,
           count_if(observed_days IS NULL
               OR cardinality(observed_days) <> coalesce(observed_day_count, 0)
               OR cardinality(observed_days) <> cardinality(array_distinct(observed_days))
               OR observed_days IS DISTINCT FROM array_sort(observed_days)
               OR element_at(observed_days, 1) IS DISTINCT FROM first_seen_day
               OR element_at(observed_days, -1) IS DISTINCT FROM last_seen_day) AS observed_days_mismatch,
           count_if(conflict_days IS NULL
               OR cardinality(array_intersect(conflict_days, observed_days)) <> cardinality(conflict_days)
               OR (cardinality(conflict_days) > 0 AND has_conflict_linkage IS DISTINCT FROM true)) AS conflict_days_mismatch,
           count_if((has_been_reassigned OR has_conflict_linkage) AND email_npi_count < 2) AS temporal_mismatch,
           count_if(source_name_values IS NULL OR email_name_count IS NULL OR email_name_count < 0
               OR source_name_usable IS DISTINCT FROM (cardinality(source_name_values) > 0)
               OR email_name_count < cardinality(source_name_values)
               OR (email_name_count = 0 AND email_npi_has_name_conflict IS NOT NULL)
               OR (email_npi_has_name_conflict AND email_name_count < 2)) AS name_consistency_mismatch
    FROM {{ ref(var('metric_model')) }}
)
SELECT reason, failures
FROM totals
CROSS JOIN UNNEST(ARRAY[
    ROW('duplicate_keys', duplicate_keys),
    ROW('empty_keys', empty_keys),
    ROW('reversed_dates', reversed_dates),
    ROW('invalid_counts', invalid_counts),
    ROW('inconsistent_dates', inconsistent_dates),
    ROW('email_format_mismatch', email_format_mismatch),
    ROW('email_role_mismatch', email_role_mismatch),
    ROW('email_domain_mismatch', email_domain_mismatch),
    ROW('name_coverage_mismatch', name_coverage_mismatch),
    ROW('multiplicity_mismatch', multiplicity_mismatch),
    ROW('observed_days_mismatch', observed_days_mismatch),
    ROW('conflict_days_mismatch', conflict_days_mismatch),
    ROW('temporal_mismatch', temporal_mismatch),
    ROW('name_consistency_mismatch', name_consistency_mismatch)
]) AS checks(reason, failures)
WHERE failures > 0

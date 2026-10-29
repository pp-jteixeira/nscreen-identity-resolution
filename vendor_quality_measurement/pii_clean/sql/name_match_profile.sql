-- One scan, three independent metrics. Email outcome counts can overlap across records and NPIs.
WITH metric_rows AS (
/* EVALUATED_SQL */
)
SELECT source, metric,
       count(*) AS metric_rows, count(DISTINCT email) AS distinct_emails,
       count(*) - count(DISTINCT ROW(source, metric_row_id)) AS duplicate_keys,
       to_hex(checksum(ROW(source, email, npi, first_seen_day, last_seen_day,
           observed_day_count, observation_count, undated_observation_count,
           invalid_day_observation_count, source_tables, source_feeds,
           definition_version, email_format_valid, email_role_account, email_domain_class))) AS evidence_checksum,
       count_if(source_name_usable IS NULL OR registry_name_usable IS NULL OR registry_npi_present IS NULL
           OR (email_matches_source_name IS NOT NULL) IS DISTINCT FROM source_name_usable
           OR (email_matches_registry_name IS NOT NULL) IS DISTINCT FROM registry_name_usable
           OR (vendor_name_matches_registry_name IS NOT NULL) IS DISTINCT FROM (source_name_usable AND registry_name_usable)
           OR (registry_name_usable AND NOT registry_npi_present)) AS coverage_failures,
       count(value) AS evaluated_metric_rows,
       count_if(value) AS matched_metric_rows,
       count_if(value = false) AS unmatched_metric_rows,
       count_if(value IS NULL) AS unknown_metric_rows,
       100e0 * count_if(value) / nullif(count(*), 0) AS matched_metric_rows_pct,
       100e0 * count_if(value = false) / nullif(count(*), 0) AS unmatched_metric_rows_pct,
       100e0 * count_if(value IS NULL) / nullif(count(*), 0) AS unknown_metric_rows_pct,
       100e0 * count_if(value) / nullif(count(value), 0) AS matched_evaluated_pct,
       count(DISTINCT email) FILTER (WHERE value) AS matched_distinct_emails,
       count(DISTINCT email) FILTER (WHERE value = false) AS unmatched_distinct_emails,
       count(DISTINCT email) FILTER (WHERE value IS NULL) AS unknown_distinct_emails,
       count_if(NOT source_name_usable) AS source_name_unusable_metric_rows,
       count_if(NOT registry_name_usable) AS registry_name_unusable_metric_rows,
       count_if(NOT registry_npi_present) AS registry_npi_absent_metric_rows
FROM metric_rows
CROSS JOIN UNNEST(ARRAY[
    ROW('email_matches_source_name', email_matches_source_name),
    ROW('email_matches_registry_name', email_matches_registry_name),
    ROW('vendor_name_matches_registry_name', vendor_name_matches_registry_name)
]) AS results(metric, value)
GROUP BY source, metric
ORDER BY source, metric

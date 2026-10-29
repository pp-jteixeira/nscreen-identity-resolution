WITH evidence AS (
/* EVIDENCE_SQL */
)
SELECT source,
       count(*) AS metric_rows,
       count(DISTINCT record_id) AS distinct_source_records,
       count(DISTINCT ROW(email, npi)) AS distinct_links,
       count(DISTINCT email) AS distinct_emails,
       count(DISTINCT npi) AS distinct_npis,
       sum(observation_count) AS observations,
       count_if(observation_count > 1) AS repeated_observation_metric_rows,
       100e0 * count_if(observation_count > 1) / nullif(count(*), 0) AS repeated_observation_metric_rows_pct,
       approx_percentile(observation_count, 0.5) AS median_observations_approx,
       approx_percentile(observation_count, 0.95) AS p95_observations_approx,
       max(observation_count) AS max_observations,
       min(first_seen_day) AS first_seen_day,
       max(last_seen_day) AS last_seen_day,
       count_if(observed_day_count IS NOT NULL) AS dated_metric_rows,
       100e0 * count_if(observed_day_count IS NOT NULL) / nullif(count(*), 0) AS dated_metric_rows_pct,
       count_if(observed_day_count > 1) AS multiple_day_metric_rows,
       100e0 * count_if(observed_day_count > 1) / nullif(count(*), 0) AS multiple_day_metric_rows_pct,
       count_if(undated_observation_count > 0) AS metric_rows_with_undated_observations,
       100e0 * count_if(undated_observation_count > 0) / nullif(count(*), 0) AS metric_rows_with_undated_observations_pct,
       sum(invalid_day_observation_count) AS invalid_day_observations,
       approx_percentile(observed_day_count, 0.5) AS median_observed_days_approx,
       max(observed_day_count) AS max_observed_days
FROM evidence
GROUP BY source
ORDER BY source

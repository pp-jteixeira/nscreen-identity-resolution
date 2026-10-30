-- One contribution per source/email/NPI link. Exact nearest-rank percentiles exclude unknown lags.
WITH measured AS (/* EVALUATED_SQL */), links AS (
    SELECT source, email, npi, link_freshness_as_of_day,
           source_latest_observed_day, source_age_days,
           link_last_observed_day, link_lag_days, count(*) AS metric_rows
    FROM measured
    GROUP BY source, email, npi, link_freshness_as_of_day,
             source_latest_observed_day, source_age_days, link_last_observed_day, link_lag_days
), lag_buckets AS (
    SELECT source, link_freshness_as_of_day, source_latest_observed_day, source_age_days,
           link_lag_days, sum(metric_rows) AS metric_rows, count(*) AS link_count,
           count_if(link_last_observed_day IS NOT NULL) AS dated_links,
           count_if(link_last_observed_day IS NULL) AS undated_links,
           count_if(link_last_observed_day > link_freshness_as_of_day) AS future_dated_links
    FROM links
    GROUP BY source, link_freshness_as_of_day, source_latest_observed_day, source_age_days, link_lag_days
), ranked_buckets AS (
    SELECT *,
           sum(CASE WHEN link_lag_days IS NOT NULL THEN link_count ELSE 0 END) OVER (
               PARTITION BY source, link_freshness_as_of_day, source_latest_observed_day, source_age_days
               ORDER BY link_lag_days NULLS LAST ROWS UNBOUNDED PRECEDING) AS cumulative_known_links,
           sum(CASE WHEN link_lag_days IS NOT NULL THEN link_count ELSE 0 END) OVER (
               PARTITION BY source, link_freshness_as_of_day, source_latest_observed_day, source_age_days) AS total_known_links
    FROM lag_buckets
)
SELECT source, link_freshness_as_of_day, source_latest_observed_day, source_age_days,
       sum(metric_rows) AS metric_rows, sum(link_count) AS distinct_links,
       sum(dated_links) AS dated_links, sum(undated_links) AS undated_links,
       100e0 * sum(undated_links) / sum(link_count) AS undated_link_pct,
       sum(future_dated_links) AS future_dated_links,
       max(total_known_links) AS known_lag_links,
       sum(CASE WHEN link_lag_days IS NULL THEN link_count ELSE 0 END) AS unknown_lag_links,
       sum(CASE WHEN link_lag_days = 0 THEN link_count ELSE 0 END) AS links_at_source_latest_day,
       100e0 * sum(CASE WHEN link_lag_days = 0 THEN link_count ELSE 0 END)
           / nullif(max(total_known_links), 0) AS latest_day_pct_of_known_lag_links,
       sum(CASE WHEN link_lag_days > 0 THEN link_count ELSE 0 END) AS links_behind_source_latest_day,
       min(link_lag_days) FILTER (WHERE cumulative_known_links * 2 >= total_known_links) AS p50_lag_days,
       min(link_lag_days) FILTER (WHERE cumulative_known_links * 100 >= total_known_links * 95) AS p95_lag_days,
       max(link_lag_days) AS maximum_lag_days
FROM ranked_buckets
GROUP BY source, link_freshness_as_of_day, source_latest_observed_day, source_age_days
ORDER BY source

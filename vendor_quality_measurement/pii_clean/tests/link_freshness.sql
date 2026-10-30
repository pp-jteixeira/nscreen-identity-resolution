-- Recompute dates from retained observations, independently of stored freshness fields.
WITH records AS (SELECT * FROM {{ ref(var('metric_model')) }}),
sources AS (
    SELECT source, max(last_seen_day) AS expected_source_day,
           count(DISTINCT link_freshness_as_of_day) AS evaluation_days
    FROM records GROUP BY source
), links AS (
    SELECT source, email, npi, max(last_seen_day) AS expected_link_day
    FROM records GROUP BY source, email, npi
)
SELECT r.source, count(*) AS failing_metric_rows
FROM records r
JOIN sources s ON r.source = s.source
JOIN links l ON r.source = l.source AND r.email = l.email AND r.npi = l.npi
WHERE r.link_freshness_as_of_day IS NULL OR s.evaluation_days <> 1
   OR r.source_latest_observed_day IS DISTINCT FROM s.expected_source_day
   OR r.link_last_observed_day IS DISTINCT FROM l.expected_link_day
   OR r.source_age_days IS DISTINCT FROM CASE WHEN s.expected_source_day <= r.link_freshness_as_of_day
       THEN date_diff('day', s.expected_source_day, r.link_freshness_as_of_day) END
   OR r.link_lag_days IS DISTINCT FROM CASE WHEN s.expected_source_day <= r.link_freshness_as_of_day
       AND l.expected_link_day <= r.link_freshness_as_of_day
       THEN date_diff('day', l.expected_link_day, s.expected_source_day) END
GROUP BY r.source

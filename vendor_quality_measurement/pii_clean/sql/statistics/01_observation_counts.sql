-- Read-only statistics for 01_observation_counts.
-- Denominators remain within each source. No email-NPI deduplication.
-- Equivalent direct aggregation of the published table. Exact weighted nearest-rank median/P95. Historical docs use saved October 29 grouped populations.
WITH counts AS (
    SELECT source, observation_count, count(*) AS row_count
    FROM iceberg.jteixeira_ipa.pii_clean FOR VERSION AS OF 8811920360682490090
    GROUP BY source, observation_count
), ranked AS (
    SELECT *, sum(row_count) OVER (PARTITION BY source) AS metric_rows,
           sum(row_count) OVER (PARTITION BY source ORDER BY observation_count
               ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS cumulative_rows
    FROM counts
)
SELECT source, max(metric_rows) AS metric_rows,
       sum(observation_count * row_count) AS email_position_observations,
       sum(IF(observation_count > 1, row_count, 0)) AS repeated_rows,
       100e0 * sum(IF(observation_count > 1, row_count, 0)) / max(metric_rows) AS repeated_row_pct,
       min(IF(cumulative_rows >= ceil(metric_rows * DECIMAL '0.5'), observation_count, NULL)) AS median_observations,
       min(IF(cumulative_rows >= ceil(metric_rows * DECIMAL '0.95'), observation_count, NULL)) AS p95_observations,
       max(observation_count) AS max_observations
FROM ranked GROUP BY source ORDER BY source

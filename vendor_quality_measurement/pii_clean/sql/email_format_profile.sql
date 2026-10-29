WITH evaluated AS (
/* EVALUATED_SQL */
)
SELECT source,
       count(*) AS metric_rows,
       min(first_seen_day) AS first_seen_day,
       max(last_seen_day) AS last_seen_day,
       count(email_format_valid) AS evaluated_metric_rows,
       100e0 * count(email_format_valid) / nullif(count(*), 0) AS evaluated_pct,
       count_if(email_format_valid) AS valid_metric_rows,
       100e0 * count_if(email_format_valid) / nullif(count(*), 0) AS valid_pct,
       count_if(NOT email_format_valid) AS invalid_metric_rows,
       100e0 * count_if(NOT email_format_valid) / nullif(count(*), 0) AS invalid_pct,
       count_if(email_format_valid IS NULL) AS unknown_metric_rows,
       100e0 * count_if(email_format_valid IS NULL) / nullif(count(*), 0) AS unknown_pct,
       count_if(email_format_valid IS DISTINCT FROM
           regexp_like(email, '^[a-z0-9._%+-]+@[a-z0-9.-]+[.][a-z]{2,}$')) AS mismatched_values,
       count(DISTINCT email) AS distinct_emails,
       count(DISTINCT email) FILTER (WHERE NOT email_format_valid) AS invalid_distinct_emails,
       100e0 * count(DISTINCT email) FILTER (WHERE NOT email_format_valid)
           / nullif(count(DISTINCT email), 0) AS invalid_distinct_emails_pct
FROM evaluated
GROUP BY source
ORDER BY source

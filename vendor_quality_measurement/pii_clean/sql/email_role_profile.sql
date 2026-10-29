-- Counts use record-level source outputs, with a separate distinct-email denominator.
WITH evaluated AS (
/* EVALUATED_SQL */
)
SELECT source,
       count(*) AS metric_rows,
       count_if(email_role_account IS DISTINCT FROM {{ email_role_account('email') }}) AS mismatched_values,
       count(email_role_account) AS evaluated_metric_rows,
       count_if(email_role_account IS NULL) AS unknown_metric_rows,
       count_if(email_role_account) AS role_metric_rows,
       100e0 * count_if(email_role_account) / nullif(count(*), 0) AS role_metric_rows_pct,
       count(DISTINCT email) AS distinct_emails,
       count(DISTINCT email) FILTER (WHERE email_role_account) AS role_distinct_emails,
       100e0 * count(DISTINCT email) FILTER (WHERE email_role_account)
           / nullif(count(DISTINCT email), 0) AS role_distinct_emails_pct
FROM evaluated
GROUP BY source
ORDER BY source

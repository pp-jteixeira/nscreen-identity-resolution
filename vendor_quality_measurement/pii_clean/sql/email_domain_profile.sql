-- Exact, mutually exclusive classes; denominators are source metric_rows and source emails.
WITH evaluated AS (
/* EVALUATED_SQL */
), counts AS (
    SELECT source, email_domain_class,
           count(*) AS class_metric_rows,
           count(DISTINCT email) AS class_distinct_emails,
           count_if(email_domain_class IS DISTINCT FROM {{ email_domain_class('email') }}) AS mismatched_values,
           count_if(NOT email_format_valid) AS format_invalid_metric_rows
    FROM evaluated
    GROUP BY source, email_domain_class
), totals AS (
    SELECT source, sum(class_metric_rows) AS metric_rows,
           sum(class_distinct_emails) AS distinct_emails
    FROM counts
    GROUP BY source
)
SELECT t.source, c.email_domain_class, t.metric_rows, t.distinct_emails,
       coalesce(n.class_metric_rows, 0) AS class_metric_rows,
       100e0 * coalesce(n.class_metric_rows, 0) / nullif(t.metric_rows, 0) AS class_metric_rows_pct,
       coalesce(n.class_distinct_emails, 0) AS class_distinct_emails,
       100e0 * coalesce(n.class_distinct_emails, 0) / nullif(t.distinct_emails, 0) AS class_distinct_emails_pct,
       coalesce(n.mismatched_values, 0) AS mismatched_values,
       coalesce(n.format_invalid_metric_rows, 0) AS format_invalid_metric_rows
FROM totals t
CROSS JOIN (VALUES 'institutional', 'free', 'custom', 'unknown') AS c(email_domain_class)
LEFT JOIN counts n ON n.source = t.source AND n.email_domain_class = c.email_domain_class
ORDER BY t.source, c.email_domain_class

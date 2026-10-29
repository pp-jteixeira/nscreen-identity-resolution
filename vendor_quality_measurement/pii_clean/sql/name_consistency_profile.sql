-- Exact email, email-NPI-link and metric-row denominators. no cross-vendor pooling.
WITH pairs AS (
    SELECT source, email, npi, count(*) AS metric_rows,
           min(email_name_count) AS minimum_name_count, max(email_name_count) AS name_count,
           bool_or(email_npi_has_name_conflict) AS conflict,
           count(DISTINCT coalesce(cast(email_npi_has_name_conflict AS varchar), 'unknown')) AS conflict_outcomes
    FROM (/* EVALUATED_SQL */)
    GROUP BY source, email, npi
), emails AS (
    SELECT source, email, max(name_count) AS name_count, sum(metric_rows) AS metric_rows,
           count(*) AS links, count_if(conflict) AS conflicting_links,
           count_if(conflict = false) AS nonconflicting_links,
           count_if(conflict IS NULL) AS unknown_links,
           sum(IF(conflict, metric_rows, 0)) AS conflicting_metric_rows,
           sum(IF(conflict IS NULL, metric_rows, 0)) AS unknown_metric_rows,
           min(minimum_name_count) <> max(name_count) OR max(conflict_outcomes) > 1 AS inconsistent
    FROM pairs GROUP BY source, email
)
SELECT source, count(*) AS distinct_emails, sum(links) AS distinct_links,
       sum(metric_rows) AS metric_rows,
       count_if(name_count = 0) AS no_name_emails,
       100e0 * count_if(name_count = 0) / count(*) AS no_name_email_pct,
       count_if(name_count = 1) AS one_name_emails,
       count_if(name_count = 2) AS two_name_emails,
       count_if(name_count = 3) AS three_name_emails,
       count_if(name_count >= 4) AS four_or_more_name_emails,
       count_if(name_count > 1) AS multiple_name_emails,
       100e0 * count_if(name_count > 1) / count(*) AS multiple_name_email_pct,
       sum(IF(name_count > 1, metric_rows, 0)) AS multiple_name_metric_rows,
       100e0 * sum(IF(name_count > 1, metric_rows, 0)) / sum(metric_rows) AS multiple_name_metric_row_pct,
       max(name_count) AS maximum_names_per_email,
       sum(conflicting_links) AS conflicting_links,
       100e0 * sum(conflicting_links) / sum(links) AS conflicting_link_pct,
       sum(nonconflicting_links) AS nonconflicting_links,
       sum(unknown_links) AS unknown_links,
       100e0 * sum(unknown_links) / sum(links) AS unknown_link_pct,
       sum(conflicting_metric_rows) AS conflicting_metric_rows,
       100e0 * sum(conflicting_metric_rows) / sum(metric_rows) AS conflicting_metric_row_pct,
       sum(unknown_metric_rows) AS unknown_metric_rows,
       100e0 * sum(unknown_metric_rows) / sum(metric_rows) AS unknown_metric_row_pct,
       count_if(inconsistent) AS mismatched_emails
FROM emails GROUP BY source ORDER BY source

-- Read-only statistics for 10_has_conflict_linkage.
-- Denominators remain within each source. no email-NPI deduplication.
-- Current published-table statistics. Metric-page counts were refreshed on October 29, 2026.
-- Reassignment and conflict outcomes
-- Conflict varies by record's observed days. reassignment describes vendor/email history.
WITH emails AS (
    SELECT source, email, count(*) AS metric_rows,
           bool_or(has_been_reassigned) AS reassigned,
           count(DISTINCT coalesce(cast(has_been_reassigned AS varchar), 'unknown')) AS reassignment_outcomes,
           count_if(has_conflict_linkage) AS conflict_rows,
           count_if(has_conflict_linkage IS NULL) AS conflict_unknown_rows
    FROM (SELECT * FROM iceberg.jteixeira_ipa.pii_clean)
    GROUP BY source, email
)
SELECT source, count(*) AS distinct_emails, sum(metric_rows) AS metric_rows,
       count_if(reassigned) AS reassigned_emails,
       100e0 * count_if(reassigned) / count(*) AS reassigned_email_pct,
       count_if(reassigned = false) AS not_reassigned_emails,
       count_if(reassigned IS NULL) AS reassignment_unknown_emails,
       sum(IF(reassigned, metric_rows, 0)) AS reassigned_metric_rows,
       100e0 * sum(IF(reassigned, metric_rows, 0)) / sum(metric_rows) AS reassigned_metric_row_pct,
       sum(IF(reassigned IS NULL, metric_rows, 0)) AS reassignment_unknown_metric_rows,
       100e0 * count_if(reassigned IS NULL) / count(*) AS reassignment_unknown_email_pct,
       count_if(conflict_rows > 0) AS conflict_emails,
       100e0 * count_if(conflict_rows > 0) / count(*) AS conflict_email_pct,
       count_if(conflict_rows = 0 AND conflict_unknown_rows = 0) AS no_conflict_emails,
       count_if(conflict_rows = 0 AND conflict_unknown_rows > 0) AS conflict_unknown_emails,
       sum(conflict_rows) AS conflict_metric_rows,
       100e0 * sum(conflict_rows) / sum(metric_rows) AS conflict_metric_row_pct,
       sum(conflict_unknown_rows) AS conflict_unknown_metric_rows,
       100e0 * count_if(conflict_rows = 0 AND conflict_unknown_rows > 0) / count(*) AS conflict_unknown_email_pct,
       count_if(reassigned AND conflict_rows > 0) AS both_flags_emails,
       count_if(reassignment_outcomes > 1) AS mismatched_emails
FROM emails GROUP BY source ORDER BY source

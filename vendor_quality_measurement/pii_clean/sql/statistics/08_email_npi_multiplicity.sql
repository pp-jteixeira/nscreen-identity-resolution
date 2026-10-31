-- Read-only statistics for 08_email_npi_multiplicity.
-- Denominators remain within each source. no email-NPI deduplication.
-- Current published-table statistics. Metric-page counts were refreshed on October 29, 2026.
-- Email multiplicity and exact vendor denominators
-- One summary per vendor. Email and metric-row denominators are separate.
WITH emails AS (
    SELECT source, email, count(*) AS metric_rows, count(DISTINCT npi) AS npi_count,
           min(first_seen_day) AS earliest_observed_day, max(last_seen_day) AS latest_observed_day,
           count_if(undated_observation_count > 0) AS undated_metric_rows,
           min(email_npi_count) AS minimum_stored_count, max(email_npi_count) AS maximum_stored_count,
           count_if(email_npi_count IS NULL OR email_has_multiple_npis IS DISTINCT FROM (email_npi_count > 1)) AS invalid_rows
    FROM (SELECT * FROM iceberg.jteixeira_ipa.pii_clean FOR VERSION AS OF 8811920360682490090)
    GROUP BY source, email
)
SELECT source, count(*) AS distinct_emails, sum(metric_rows) AS metric_rows,
       min(earliest_observed_day) AS earliest_observed_day, max(latest_observed_day) AS latest_observed_day,
       sum(undated_metric_rows) AS undated_metric_rows,
       count_if(npi_count > 1) AS multiple_npi_emails,
       100e0 * count_if(npi_count > 1) / count(*) AS multiple_npi_email_pct,
       sum(IF(npi_count > 1, metric_rows, 0)) AS affected_metric_rows,
       100e0 * sum(IF(npi_count > 1, metric_rows, 0)) / sum(metric_rows) AS affected_metric_row_pct,
       max(npi_count) AS maximum_npis_per_email,
       count_if(npi_count = 1) AS one_npi_emails,
       count_if(npi_count = 2) AS two_npi_emails,
       count_if(npi_count = 3) AS three_npi_emails,
       count_if(npi_count = 4) AS four_npi_emails,
       count_if(npi_count >= 5) AS five_or_more_npi_emails,
       count_if(invalid_rows > 0 OR minimum_stored_count <> npi_count OR maximum_stored_count <> npi_count) AS mismatched_emails
FROM emails
GROUP BY source
ORDER BY source

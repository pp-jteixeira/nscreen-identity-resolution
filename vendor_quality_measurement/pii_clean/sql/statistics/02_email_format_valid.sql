-- Read-only statistics for 02_email_format_valid.
-- Denominators remain within each source. no email-NPI deduplication.
-- Equivalent direct aggregation of the saved October 29 row-population statistics, not a new warehouse execution.
SELECT source, count(*) AS metric_rows,
       count_if(email_format_valid = false) AS invalid_rows,
       100e0 * count_if(email_format_valid = false) / count(*) AS invalid_row_pct
FROM iceberg.jteixeira_ipa.pii_clean FOR VERSION AS OF 8811920360682490090
GROUP BY source ORDER BY source

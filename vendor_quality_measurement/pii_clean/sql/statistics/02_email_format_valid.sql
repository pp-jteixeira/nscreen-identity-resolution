-- Read-only statistics for 02_email_format_valid.
-- Denominators remain within each source. Links are not pooled across sources.
SELECT source, count(*) AS metric_rows,
       count_if(email_format_valid = false) AS invalid_rows,
       100e0 * count_if(email_format_valid = false) / count(*) AS invalid_row_pct
FROM iceberg.jteixeira_ipa.pii_clean
GROUP BY source ORDER BY source

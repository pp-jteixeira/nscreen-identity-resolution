-- Read-only statistics for 04_email_domain_class.
-- Denominators remain within each source. no email-NPI deduplication.
-- Equivalent direct aggregation of the saved October 29 row-population statistics, not a new warehouse execution.
SELECT source,
       count(*) AS metric_rows,
       count_if(email_domain_class = 'institutional') AS institutional_rows,
       100e0 * count_if(email_domain_class = 'institutional') / count(*) AS institutional_row_pct,
       count_if(email_domain_class = 'free') AS free_rows,
       100e0 * count_if(email_domain_class = 'free') / count(*) AS free_row_pct,
       count_if(email_domain_class = 'custom') AS custom_rows,
       100e0 * count_if(email_domain_class = 'custom') / count(*) AS custom_row_pct,
       count_if(email_domain_class = 'unknown') AS unknown_rows,
       100e0 * count_if(email_domain_class = 'unknown') / count(*) AS unknown_row_pct
FROM iceberg.jteixeira_ipa.pii_clean
GROUP BY source ORDER BY source

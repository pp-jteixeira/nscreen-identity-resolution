-- Read-only statistics for 05_email_matches_source_name.
-- Denominators remain within each source. no email-NPI deduplication.
-- Equivalent direct aggregation of the saved October 29 row-population statistics, not a new warehouse execution.
SELECT source,
       count(*) AS metric_rows,
       count_if(email_matches_source_name) AS match_rows,
       100e0 * count_if(email_matches_source_name) / count(*) AS match_row_pct,
       count_if(email_matches_source_name = false) AS no_match_rows,
       100e0 * count_if(email_matches_source_name = false) / count(*) AS no_match_row_pct,
       count_if(email_matches_source_name IS NULL) AS unknown_rows,
       100e0 * count_if(email_matches_source_name IS NULL) / count(*) AS unknown_row_pct
FROM iceberg.jteixeira_ipa.pii_clean
GROUP BY source ORDER BY source

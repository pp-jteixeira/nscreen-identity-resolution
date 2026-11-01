-- Exact vendor denominators
SELECT source, count(*) AS metric_rows,
count(DISTINCT ROW(email,npi)) AS distinct_links FROM iceberg.jteixeira_ipa.pii_clean FOR VERSION AS OF 4233051104478921549 GROUP BY source ORDER BY source

-- Exact vendor denominators
SELECT source, count(*) AS metric_rows,
       count(DISTINCT ROW(email, npi)) AS distinct_links, count(DISTINCT npi) AS distinct_npis
FROM iceberg.jteixeira_ipa.pii_clean FOR VERSION AS OF 8811920360682490090 GROUP BY source ORDER BY source

SELECT
    source,
    grouping(source) AS is_global_total,
    count(*) AS row_count,
    count(DISTINCT ROW(email, npi)) AS distinct_pairs,
    count(DISTINCT email) AS distinct_emails,
    count(DISTINCT npi) AS distinct_npis
FROM iceberg.jteixeira_ipa.pii_clean
GROUP BY GROUPING SETS ((source), ())
ORDER BY is_global_total DESC, row_count DESC

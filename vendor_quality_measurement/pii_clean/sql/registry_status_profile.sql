-- Status has one reference outcome per NPI. link groups are mutually exclusive.
WITH measured AS (/* EVALUATED_SQL */)
SELECT source, npi_registry_status, npi_registry_status_reason,
       count(*) AS metric_rows, count(DISTINCT metric_row_id) AS unique_metric_rows,
       count(DISTINCT ROW(email, npi)) AS distinct_links,
       count(DISTINCT npi) AS distinct_npis
FROM measured GROUP BY source, npi_registry_status, npi_registry_status_reason
ORDER BY source, npi_registry_status, npi_registry_status_reason

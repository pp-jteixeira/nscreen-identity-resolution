WITH measured AS (/* EVALUATED_SQL */)
SELECT source, vendor_state_evidence, facility_reference_status,
       count(*) AS metric_rows, count(DISTINCT metric_row_id) AS unique_metric_rows,
       count(DISTINCT ROW(email, npi)) AS distinct_links
FROM measured GROUP BY source, vendor_state_evidence, facility_reference_status
ORDER BY source, vendor_state_evidence, facility_reference_status

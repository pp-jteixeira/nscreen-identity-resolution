WITH measured AS (/* EVALUATED_SQL */)
SELECT source, cookie_location_status, cookie_vendor_state_evidence, cookie_facility_state_evidence,
       count(*) AS metric_rows, count(DISTINCT metric_row_id) AS unique_metric_rows,
       count(DISTINCT ROW(email, npi)) AS distinct_links,
       count(DISTINCT email) AS distinct_emails
FROM measured GROUP BY source, cookie_location_status, cookie_vendor_state_evidence, cookie_facility_state_evidence
ORDER BY source, cookie_location_status, cookie_vendor_state_evidence, cookie_facility_state_evidence

SELECT source, count(*) AS failing_metric_rows
FROM {{ ref(var('metric_model')) }}
WHERE domain_evidence_version IS DISTINCT FROM 'domain_evidence_v1'
   OR (email_domain IS NULL) IS DISTINCT FROM (domain_npi_count IS NULL)
   OR domain_npi_count < 1 OR domain_email_count < 1
   OR domain_npis_with_state > domain_npi_count OR domain_npis_with_facility > domain_npi_count
   OR domain_state_count > domain_npis_with_state
   OR domain_top_state_share NOT BETWEEN 0 AND 1 OR domain_top_facility_share NOT BETWEEN 0 AND 1
   OR (email_domain_class IN ('free', 'unknown') AND (domain_npis_with_state IS NOT NULL OR domain_npis_with_facility IS NOT NULL))
GROUP BY source

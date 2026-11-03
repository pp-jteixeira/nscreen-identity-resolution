SELECT source, count(*) AS failing_metric_rows
FROM {{ ref(var('metric_model')) }}
WHERE facility_sources IS NULL OR facility_claims_definition_version IS DISTINCT FROM 'facility_claims_support_v1'
   OR (cardinality(facility_sources) > 0 AND facility_claims_backed IS DISTINCT FROM contains(facility_sources, 'Claims'))
   OR (cardinality(facility_sources) = 0 AND facility_claims_backed IS TRUE)
   OR (facility_claim_count IS NOT NULL AND (facility_claim_count < 0 OR facility_claims_backed IS DISTINCT FROM true))
GROUP BY source

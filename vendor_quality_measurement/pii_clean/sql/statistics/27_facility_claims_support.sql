-- Read-only statistics for 27_facility_claims_support, from the stored claims columns.
-- Denominators remain within each source. Links are not pooled across sources.
-- facility_claims_backed is null when the NPI has no rank-1 claims-association row. The median is approximate.
SELECT source, count(*) AS links,
count_if(facility_claims_backed IS NULL) AS no_rank1_row,
count_if(facility_claims_backed) AS claims_backed,
count_if(NOT facility_claims_backed) AS not_claims_backed,
count_if(facility_claims_backed IS NOT NULL AND facility_claim_count IS NULL) AS row_without_claim_count,
count_if(facility_claim_count BETWEEN 1 AND 9) AS claims_1_9,
count_if(facility_claim_count BETWEEN 10 AND 99) AS claims_10_99,
count_if(facility_claim_count >= 100) AS claims_100_plus,
approx_percentile(facility_claim_count, 0.5) AS claim_count_p50
FROM iceberg.jteixeira_ipa.pii_clean
GROUP BY source
ORDER BY source

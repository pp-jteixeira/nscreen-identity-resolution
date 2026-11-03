-- Read-only statistics for 27_facility_claims_support.
-- Denominators remain within each source. Links are not pooled across sources.
-- Claims-association support by source. The reference lookup is the rank-1 claims-association row of each NPI.
WITH claims AS (SELECT trim(provider_npi) AS npi,
       max(claim_count) AS facility_claim_count,
       array_sort(array_distinct(filter(
           flatten(array_agg(transform(split(coalesce(sources, ''), ','), s -> trim(s)))),
           s -> s <> ''))) AS facility_sources
FROM bq_bi.analytics_prod.npi_facility_association
WHERE _rank = 1 AND nullif(trim(provider_npi), '') IS NOT NULL
GROUP BY trim(provider_npi)), joined AS (
SELECT l.source, l.vendor_state_evidence, c.npi IS NOT NULL AS has_row, c.facility_claim_count, c.facility_sources
FROM iceberg.jteixeira_ipa.pii_clean l LEFT JOIN claims c ON trim(l.npi) = c.npi
)
SELECT source, count(*) AS links,
count_if(NOT has_row) AS no_rank1_row,
count_if(has_row AND contains(facility_sources, 'Claims')) AS claims_backed,
count_if(has_row AND NOT contains(facility_sources, 'Claims')) AS not_claims_backed,
count_if(has_row AND facility_claim_count IS NULL) AS row_without_claim_count,
count_if(facility_claim_count BETWEEN 1 AND 9) AS claims_1_9,
count_if(facility_claim_count BETWEEN 10 AND 99) AS claims_10_99,
count_if(facility_claim_count >= 100) AS claims_100_plus,
approx_percentile(facility_claim_count, 0.5) AS claim_count_p50
FROM joined GROUP BY source ORDER BY source

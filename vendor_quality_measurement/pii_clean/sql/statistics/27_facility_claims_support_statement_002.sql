-- Vendor-state evidence by claims support, among links with a usable facility state and a known vendor state.
WITH claims AS (SELECT trim(provider_npi) AS npi,
       max(claim_count) AS facility_claim_count,
       array_sort(array_distinct(filter(
           flatten(array_agg(transform(split(coalesce(sources, ''), ','), s -> trim(s)))),
           s -> s <> ''))) AS facility_sources
FROM bq_bi.analytics_prod.npi_facility_association
WHERE _rank = 1 AND nullif(trim(provider_npi), '') IS NOT NULL
GROUP BY trim(provider_npi)), joined AS (
SELECT l.source, l.vendor_state_evidence, c.npi IS NOT NULL AND contains(c.facility_sources, 'Claims') AS claims_backed
FROM iceberg.jteixeira_ipa.pii_clean l LEFT JOIN claims c ON trim(l.npi) = c.npi
WHERE l.vendor_state_evidence IN ('corroborated', 'not_corroborated')
)
SELECT source, claims_backed, count(*) AS links,
count_if(vendor_state_evidence = 'corroborated') AS corroborated
FROM joined GROUP BY source, claims_backed ORDER BY source, claims_backed

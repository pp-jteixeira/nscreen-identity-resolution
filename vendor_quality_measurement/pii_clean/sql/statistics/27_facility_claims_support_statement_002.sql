-- Vendor-state evidence by claims support, among links with a usable facility state and a known vendor state.
SELECT source, coalesce(facility_claims_backed, false) AS claims_backed, count(*) AS links,
count_if(vendor_state_evidence = 'corroborated') AS corroborated
FROM iceberg.jteixeira_ipa.pii_clean
WHERE vendor_state_evidence IN ('corroborated', 'not_corroborated')
GROUP BY source, coalesce(facility_claims_backed, false)
ORDER BY source, claims_backed

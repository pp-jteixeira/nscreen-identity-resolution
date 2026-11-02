-- Links whose any-version and latest-version vendor-state evidence differ. Latest is null without a single latest version.
SELECT source, vendor_state_evidence, vendor_state_evidence_latest, count(*) AS links
FROM iceberg.jteixeira_ipa.pii_clean
WHERE latest_record_id IS NOT NULL AND vendor_state_evidence IS DISTINCT FROM vendor_state_evidence_latest
GROUP BY source, vendor_state_evidence, vendor_state_evidence_latest
ORDER BY source, vendor_state_evidence, vendor_state_evidence_latest

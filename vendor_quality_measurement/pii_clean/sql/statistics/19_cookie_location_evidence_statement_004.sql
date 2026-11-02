-- Links whose any-version and latest-version cookie vendor-state evidence differ. Latest is null without a single latest version.
SELECT source, cookie_vendor_state_evidence, cookie_vendor_state_evidence_latest, count(*) AS links
FROM iceberg.jteixeira_ipa.pii_clean
WHERE latest_record_id IS NOT NULL AND cookie_vendor_state_evidence IS DISTINCT FROM cookie_vendor_state_evidence_latest
GROUP BY source, cookie_vendor_state_evidence, cookie_vendor_state_evidence_latest
ORDER BY source, cookie_vendor_state_evidence, cookie_vendor_state_evidence_latest

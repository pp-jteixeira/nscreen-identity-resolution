-- Read-only statistics for 18_vendor_facility_state.
-- Denominators remain within each source. no email-NPI deduplication.
-- Exact executed SQL exported from local location_evidence_facility.json. result rows are excluded. Original source relations are retained.
-- Exact vendor denominators
SELECT source, count(*) AS metric_rows,
count(DISTINCT ROW(email,npi)) AS distinct_links FROM iceberg.jteixeira_ipa.pii_clean FOR VERSION AS OF 8811920360682490090 GROUP BY source ORDER BY source

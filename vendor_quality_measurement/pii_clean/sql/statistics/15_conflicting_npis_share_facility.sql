-- Published coverage and conflict denominators, including zero-conflict vendors.
-- Arrays are stored evidence from the publication snapshot.
SELECT m.source, count(*) AS metric_rows, count(DISTINCT m.email) AS distinct_emails,
       count(DISTINCT ROW(m.email, m.npi)) AS distinct_links,
       count_if(cardinality(m.facility_npi_values) > 0) AS usable_facility_rows,
       count_if(m.has_conflict_linkage) AS conflict_rows,
       count_if(m.has_conflict_linkage = false) AS not_applicable_rows,
       count_if(m.has_conflict_linkage IS NULL) AS unknown_timing_rows,
       count(DISTINCT IF(m.has_conflict_linkage, m.email, NULL)) AS conflict_emails
FROM iceberg.jteixeira_ipa.pii_clean FOR VERSION AS OF 8811920360682490090 m
GROUP BY m.source ORDER BY m.source

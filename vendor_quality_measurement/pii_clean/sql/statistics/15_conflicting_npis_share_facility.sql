-- Read-only statistics for 15_conflicting_npis_share_facility.
-- Denominators remain within each source. no email-NPI deduplication.
-- Exact executed SQL exported from local conflicting_facilities_measure.json. result rows are excluded. Original source relations are retained.
-- All vendors and conflict-row denominators, including zero-conflict vendors
WITH facility_reference AS (SELECT trim(provider_npi) AS npi,
       array_sort(array_distinct(filter(
           transform(flatten(array_agg(coalesce(facility_npis, CAST(ARRAY[] AS array(varchar))))),
                     f -> trim(f)),
           f -> regexp_like(f, '^[0-9]{10}$') AND f <> '0000000000'
       ))) AS facility_npi_values
FROM bq_bi.analytics_prod.npi_facility_association
WHERE nullif(trim(provider_npi), '') IS NOT NULL
GROUP BY trim(provider_npi))
SELECT m.source, count(*) AS metric_rows, count(DISTINCT m.email) AS distinct_emails,
       count(DISTINCT ROW(m.email, m.npi)) AS distinct_links,
       count_if(cardinality(f.facility_npi_values) > 0) AS usable_facility_rows,
       count_if(m.has_conflict_linkage) AS conflict_rows,
       count_if(m.has_conflict_linkage = false) AS not_applicable_rows,
       count_if(m.has_conflict_linkage IS NULL) AS unknown_timing_rows,
       count(DISTINCT IF(m.has_conflict_linkage, m.email, NULL)) AS conflict_emails
FROM iceberg.jteixeira_ipa.pii_clean m LEFT JOIN facility_reference f ON m.npi = f.npi
GROUP BY m.source ORDER BY m.source

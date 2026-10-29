-- Outcomes apply to exact record/email-position rows, not deduplicated links.
WITH measured AS (/* EVALUATED_SQL */)
SELECT source, count(*) AS metric_rows,
       count(DISTINCT email) AS distinct_emails,
       count_if(cardinality(facility_npi_values) > 0) AS usable_facility_rows,
       count(DISTINCT ROW(email, npi)) AS distinct_links,
       count_if(has_conflict_linkage) AS conflict_rows,
       count(DISTINCT IF(has_conflict_linkage, email, NULL)) AS conflict_emails,
       count_if(conflicting_npis_share_facility) AS shared_facility_rows,
       count_if(conflicting_npis_share_facility = false) AS different_facility_rows,
       count_if(has_conflict_linkage AND conflicting_npis_share_facility IS NULL) AS unknown_facility_rows,
       count_if(has_conflict_linkage = false) AS not_applicable_rows,
       count_if(has_conflict_linkage IS NULL) AS unknown_timing_rows,
       100e0 * count_if(conflicting_npis_share_facility) / nullif(count_if(has_conflict_linkage), 0) AS shared_facility_pct,
       100e0 * count_if(conflicting_npis_share_facility = false) / nullif(count_if(has_conflict_linkage), 0) AS different_facility_pct,
       100e0 * count_if(has_conflict_linkage AND conflicting_npis_share_facility IS NULL) / nullif(count_if(has_conflict_linkage), 0) AS unknown_facility_pct
FROM measured GROUP BY source ORDER BY source

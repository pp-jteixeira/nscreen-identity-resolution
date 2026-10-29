-- Outcomes apply to exact record/email-position rows, not deduplicated links.
WITH measured AS (/* EVALUATED_SQL */)
SELECT source, count(*) AS metric_rows,
       count(DISTINCT email) AS distinct_emails,
       count(DISTINCT ROW(email, npi)) AS distinct_links,
       count_if(has_conflict_linkage) AS conflict_rows,
       count(DISTINCT IF(has_conflict_linkage, email, NULL)) AS conflict_emails,
       count_if(conflicting_npis_share_name) AS shared_name_rows,
       count_if(conflicting_npis_share_name = false) AS different_name_rows,
       count_if(has_conflict_linkage AND conflicting_npis_share_name IS NULL) AS unknown_name_rows,
       count_if(has_conflict_linkage = false) AS not_applicable_rows,
       count_if(has_conflict_linkage IS NULL) AS unknown_timing_rows,
       100e0 * count_if(conflicting_npis_share_name) / nullif(count_if(has_conflict_linkage), 0) AS shared_name_pct,
       100e0 * count_if(conflicting_npis_share_name = false) / nullif(count_if(has_conflict_linkage), 0) AS different_name_pct,
       100e0 * count_if(has_conflict_linkage AND conflicting_npis_share_name IS NULL) / nullif(count_if(has_conflict_linkage), 0) AS unknown_name_pct
FROM measured GROUP BY source ORDER BY source

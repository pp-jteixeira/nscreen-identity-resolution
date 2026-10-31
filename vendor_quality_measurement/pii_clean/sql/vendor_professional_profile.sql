-- Aggregate stored vendor-label metrics from the published population.
WITH measured AS (/* EVALUATED_SQL */), dimensions AS (
    SELECT m.source, m.email, m.npi, m.has_conflict_linkage, d.metric,
           CASE d.metric WHEN 'specialty' THEN cardinality(m.source_vendor_specialty_values) > 0
                ELSE cardinality(m.source_vendor_profession_values) > 0 END AS has_values,
           CASE d.metric WHEN 'specialty' THEN m.conflicting_npis_share_vendor_specialty
                ELSE m.conflicting_npis_share_vendor_profession END AS shares_values
    FROM measured m CROSS JOIN (VALUES ('specialty'), ('profession')) AS d(metric)
), grouped AS (
    SELECT source, metric, count(*) AS metric_rows,
           count(DISTINCT email) AS distinct_emails, count(DISTINCT ROW(email, npi)) AS distinct_links,
           count_if(has_values) AS rows_with_vendor_values,
           count_if(has_conflict_linkage) AS conflict_rows,
           count_if(has_conflict_linkage = false) AS not_applicable_rows,
           count_if(has_conflict_linkage IS NULL) AS unknown_timing_rows,
           count_if(shares_values) AS shared_rows,
           count_if(shares_values = false) AS disjoint_rows,
           count_if(has_conflict_linkage AND shares_values IS NULL) AS unknown_conflict_rows,
           count(DISTINCT IF(has_conflict_linkage, ROW(email, npi), NULL)) AS conflict_links,
           count(DISTINCT IF(shares_values, ROW(email, npi), NULL)) AS shared_links,
           count(DISTINCT IF(shares_values = false, ROW(email, npi), NULL)) AS disjoint_links,
           count(DISTINCT IF(has_conflict_linkage AND shares_values IS NULL, ROW(email, npi), NULL)) AS unknown_conflict_links
    FROM dimensions GROUP BY source, metric
)
SELECT *, 100e0 * rows_with_vendor_values / nullif(metric_rows, 0) AS vendor_value_coverage_pct,
       100e0 * shared_rows / nullif(conflict_rows, 0) AS shared_conflict_row_pct,
       100e0 * disjoint_rows / nullif(conflict_rows, 0) AS disjoint_conflict_row_pct,
       100e0 * unknown_conflict_rows / nullif(conflict_rows, 0) AS unknown_conflict_row_pct
FROM grouped ORDER BY source, metric

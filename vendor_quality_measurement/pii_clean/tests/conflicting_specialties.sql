-- Independent relational peer selection and null aggregation.
WITH records AS (
    SELECT source, email, npi, metric_row_id, conflict_days, has_conflict_linkage,
           specialty_code_values, conflicting_npis_share_nppes_specialty,
           conflicting_npi_specialty_comparisons
    FROM {{ ref(var('metric_model')) }}
), peers AS (
    SELECT a.source, a.metric_row_id,
           CASE WHEN cardinality(a.specialty_code_values) > 0 AND cardinality(b.specialty_code_values) > 0
                THEN arrays_overlap(a.specialty_code_values, b.specialty_code_values) END AS shares_specialty
    FROM records a JOIN records b
      ON a.source = b.source AND a.email = b.email AND a.npi <> b.npi
     AND a.has_conflict_linkage AND b.has_conflict_linkage
     AND (a.source IN ('endato', 'rocketreach', 'drdb') OR arrays_overlap(a.conflict_days, b.conflict_days))
), expected AS (
    SELECT source, metric_row_id,
           CASE WHEN count_if(shares_specialty) > 0 THEN true
                WHEN count_if(shares_specialty IS NULL) > 0 THEN CAST(NULL AS boolean)
                ELSE false END AS flag
    FROM peers GROUP BY source, metric_row_id
)
SELECT m.source, count(*) AS failing_metric_rows
FROM records m LEFT JOIN expected e ON m.source = e.source AND m.metric_row_id = e.metric_row_id
WHERE m.conflicting_npis_share_nppes_specialty IS DISTINCT FROM e.flag
   OR m.specialty_code_values IS NULL
   OR m.specialty_code_values IS DISTINCT FROM array_sort(array_distinct(m.specialty_code_values))
   OR any_match(m.specialty_code_values, f -> NOT regexp_like(f, '^[0-9A-Z]{10}$') OR f = '0000000000')
   OR m.conflicting_npi_specialty_comparisons IS NULL
   OR any_match(m.conflicting_npi_specialty_comparisons, p -> p.npi = m.npi
       OR p.shared_specialty_codes IS DISTINCT FROM array_sort(array_intersect(m.specialty_code_values, p.specialty_codes))
       OR p.shares_specialty IS DISTINCT FROM
          (CASE WHEN cardinality(m.specialty_code_values) > 0 AND cardinality(p.specialty_codes) > 0
                THEN cardinality(p.shared_specialty_codes) > 0 END)
       OR cardinality(array_intersect(p.conflict_days, m.conflict_days)) <> cardinality(p.conflict_days)
       OR (m.source NOT IN ('endato', 'rocketreach', 'drdb') AND cardinality(p.conflict_days) = 0))
GROUP BY m.source

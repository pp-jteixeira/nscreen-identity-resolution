-- Relational peer comparison, independent of the window implementation.
WITH records AS (
    SELECT source, email, npi, metric_row_id, conflict_days, has_conflict_linkage,
           source_state_values, conflicting_npis_share_state
    FROM {{ ref(var('metric_model')) }}
), peers AS (
    SELECT a.source, a.metric_row_id,
           CASE WHEN cardinality(a.source_state_values) > 0 AND cardinality(b.source_state_values) > 0
                THEN arrays_overlap(a.source_state_values, b.source_state_values) END AS shares_state
    FROM records a JOIN records b
      ON a.source = b.source AND a.email = b.email AND a.npi <> b.npi
     AND a.has_conflict_linkage AND b.has_conflict_linkage
     AND (a.source IN ('endato', 'rocketreach', 'drdb') OR arrays_overlap(a.conflict_days, b.conflict_days))
), expected AS (
    SELECT source, metric_row_id,
           CASE WHEN count_if(shares_state) > 0 THEN true
                WHEN count_if(shares_state IS NULL) > 0 THEN CAST(NULL AS boolean)
                ELSE false END AS flag
    FROM peers GROUP BY source, metric_row_id
)
SELECT m.source, count(*) AS failing_metric_rows
FROM records m LEFT JOIN expected e ON m.source = e.source AND m.metric_row_id = e.metric_row_id
WHERE m.conflicting_npis_share_state IS DISTINCT FROM e.flag
GROUP BY m.source

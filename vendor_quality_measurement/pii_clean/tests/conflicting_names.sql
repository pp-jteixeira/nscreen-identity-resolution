-- Independent relational check: retain dates and names on their original records.
WITH records AS (
    SELECT source, email, npi, metric_row_id, conflict_days, has_conflict_linkage,
           source_name_values, conflicting_npis_share_name
    FROM {{ ref(var('metric_model')) }}
), peer_pairs AS (
    SELECT a.source, a.metric_row_id, b.metric_row_id AS peer_id,
           a.source_name_values AS own_names, b.source_name_values AS peer_names
    FROM records a JOIN records b
      ON a.source = b.source AND a.email = b.email AND a.npi <> b.npi
     AND a.has_conflict_linkage AND b.has_conflict_linkage
     AND (a.source IN ('endato', 'rocketreach', 'drdb')
          OR arrays_overlap(a.conflict_days, b.conflict_days))
), names AS (
    SELECT source, metric_row_id,
           (element_at(source_name_values, i)).first_name AS first_name,
           (element_at(source_name_values, i)).last_name AS last_name,
           (element_at(source_name_values, i)).first_variants AS first_variants
    FROM records CROSS JOIN UNNEST(
        IF(cardinality(source_name_values) > 0, sequence(1, cardinality(source_name_values)), ARRAY[])
    ) AS positions(i)
), comparisons AS (
    SELECT p.source, p.metric_row_id, p.peer_id,
           bool_or(CASE WHEN a.first_name IS NOT NULL AND b.first_name IS NOT NULL
                        THEN NOT {{ names_disagree('a', 'b') }} END) AS shares_name
    FROM peer_pairs p
    LEFT JOIN names a ON p.source = a.source AND p.metric_row_id = a.metric_row_id
    LEFT JOIN names b ON p.source = b.source AND p.peer_id = b.metric_row_id
    GROUP BY p.source, p.metric_row_id, p.peer_id
), expected AS (
    SELECT source, metric_row_id,
           CASE WHEN count_if(shares_name) > 0 THEN true
                WHEN count_if(shares_name IS NULL) > 0 THEN CAST(NULL AS boolean)
                ELSE false END AS expected_flag
    FROM comparisons GROUP BY source, metric_row_id
)
SELECT m.source, count(*) AS failing_metric_rows
FROM records m LEFT JOIN expected e ON m.source = e.source AND m.metric_row_id = e.metric_row_id
WHERE m.conflicting_npis_share_name IS DISTINCT FROM e.expected_flag
GROUP BY m.source

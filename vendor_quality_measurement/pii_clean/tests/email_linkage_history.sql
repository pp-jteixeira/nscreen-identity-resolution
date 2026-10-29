-- Independently compare consecutive observed daily NPI sets. no inferred missing days.
WITH daily AS (
    SELECT source, email, observed_day, array_sort(array_agg(DISTINCT npi)) AS npis
    FROM {{ ref(var('metric_model')) }}
    CROSS JOIN UNNEST(observed_days) AS d(observed_day)
    GROUP BY source, email, observed_day
), successive AS (
    SELECT *, lag(npis) OVER (PARTITION BY source, email ORDER BY observed_day) AS previous_npis
    FROM daily
), dated AS (
    SELECT source, email,
           coalesce(array_sort(array_agg(observed_day) FILTER (WHERE cardinality(npis) > 1)), CAST(ARRAY[] AS array(date))) AS conflict_days,
           bool_or(previous_npis IS NOT NULL AND npis <> previous_npis) AS reassigned
    FROM successive GROUP BY source, email
), emails AS (
    SELECT source, email, count(DISTINCT npi) AS npi_count,
           count_if(undated_observation_count > 0) AS undated_rows
    FROM {{ ref(var('metric_model')) }}
    GROUP BY source, email
), expected AS (
    SELECT e.source, e.email, e.npi_count,
           coalesce(d.conflict_days, CAST(ARRAY[] AS array(date))) AS conflict_days,
           CASE WHEN coalesce(d.reassigned, false) THEN true
                WHEN e.npi_count = 1 THEN false
                WHEN e.undated_rows > 0 THEN CAST(NULL AS boolean)
                ELSE false END AS expected_reassigned
    FROM emails e LEFT JOIN dated d ON e.source = d.source AND e.email = d.email
), checked AS (
    SELECT m.source, m.has_conflict_linkage, m.has_been_reassigned, m.conflict_days,
           e.expected_reassigned,
           array_sort(array_intersect(m.observed_days, e.conflict_days)) AS expected_conflict_days,
           CASE WHEN m.source IN ('endato', 'rocketreach', 'drdb') THEN e.npi_count > 1
                WHEN arrays_overlap(m.observed_days, e.conflict_days) THEN true
                WHEN e.npi_count = 1 THEN false
                WHEN m.undated_observation_count > 0 THEN CAST(NULL AS boolean)
                ELSE false END AS expected_conflict
    FROM {{ ref(var('metric_model')) }} m
    JOIN expected e ON m.source = e.source AND m.email = e.email
)
SELECT source, count(*) AS failing_metric_rows
FROM checked
WHERE has_conflict_linkage IS DISTINCT FROM expected_conflict
   OR has_been_reassigned IS DISTINCT FROM expected_reassigned
   OR conflict_days IS DISTINCT FROM expected_conflict_days
GROUP BY source

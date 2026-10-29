-- Independently count name pairs and compare distinct names with a relational self-join.
WITH names AS (
    SELECT DISTINCT source, email, npi, n.first_name, n.last_name, n.first_variants
    FROM {{ ref(var('metric_model')) }}
    CROSS JOIN UNNEST(source_name_values) AS n(first_name, last_name, first_variants)
), email_counts AS (
    SELECT source, email, count(DISTINCT ROW(first_name, last_name)) AS expected_count
    FROM names GROUP BY source, email
), pair_counts AS (
    SELECT source, email, npi, count(*) AS usable_names
    FROM names GROUP BY source, email, npi
), conflicts AS (
    SELECT a.source, a.email, a.npi,
           bool_or({{ names_disagree('a', 'b') }}) AS conflict
    FROM names a JOIN names b
      ON a.source = b.source AND a.email = b.email AND a.npi = b.npi
     AND ROW(a.first_name, a.last_name) < ROW(b.first_name, b.last_name)
    GROUP BY a.source, a.email, a.npi
)
SELECT m.source, count(*) AS failing_metric_rows
FROM {{ ref(var('metric_model')) }} m
LEFT JOIN email_counts e ON m.source = e.source AND m.email = e.email
LEFT JOIN pair_counts p ON m.source = p.source AND m.email = p.email AND m.npi = p.npi
LEFT JOIN conflicts c ON m.source = c.source AND m.email = c.email AND m.npi = c.npi
WHERE m.email_name_count IS DISTINCT FROM coalesce(e.expected_count, 0)
   OR m.email_npi_has_name_conflict IS DISTINCT FROM
      CASE WHEN p.usable_names IS NULL THEN CAST(NULL AS boolean) ELSE coalesce(c.conflict, false) END
GROUP BY m.source

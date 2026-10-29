-- Staging must preserve every raw input row, including missing and invalid values.
WITH input_rows AS (
    SELECT count(*) AS n FROM {{ source(var('source_namespace'), var('source_table')) }}
), staged_rows AS (
    SELECT count(*) AS n FROM {{ ref(var('staging_model')) }}
)
SELECT 'staging_row_count_changed' AS reason, i.n AS input_rows, s.n AS staged_rows
FROM input_rows AS i CROSS JOIN staged_rows AS s
WHERE i.n <> s.n

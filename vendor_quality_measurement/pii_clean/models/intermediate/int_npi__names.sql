-- All readable registry names, deduplicated by NPI and normalized name pair.
-- No latest/as-of selection. historical vendor links use this current reference.
WITH names AS (
    SELECT DISTINCT npi_clean AS npi,
           {{ norm_name('cast(first_name AS varchar)') }} AS first_name,
           {{ norm_name('cast(last_name AS varchar)') }} AS last_name
    FROM {{ ref('stg_npi__reference') }}
    WHERE npi_clean IS NOT NULL
)
SELECT n.npi, n.first_name, n.last_name,
       array_distinct(filter(concat(ARRAY[n.first_name], coalesce(v.variants, CAST(ARRAY[] AS array(varchar)))), x -> x IS NOT NULL)) AS first_set
FROM names n
LEFT JOIN {{ ref('int_name__variants') }} v ON split_part(n.first_name, ' ', 1) = v.first_name

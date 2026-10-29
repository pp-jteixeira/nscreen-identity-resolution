-- Bidirectional, one-hop nickname expansion; exactly one row per lookup name.
WITH forward AS (
    SELECT nickname, canonical
    FROM {{ ref('nicknames') }}
    CROSS JOIN UNNEST(split(canonicals, '|')) AS c(canonical)
), edges AS (
    SELECT nickname AS first_name, canonical AS variant FROM forward
    UNION
    SELECT canonical AS first_name, nickname AS variant FROM forward
)
SELECT first_name, array_sort(array_agg(DISTINCT variant)) AS variants
FROM edges
GROUP BY first_name

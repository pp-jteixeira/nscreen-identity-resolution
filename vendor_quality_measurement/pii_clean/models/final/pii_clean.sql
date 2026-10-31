-- Publish complete, computed metrics from the downstream cookie intermediate.
SELECT * FROM {{ ref('int_cookie__metrics') }}

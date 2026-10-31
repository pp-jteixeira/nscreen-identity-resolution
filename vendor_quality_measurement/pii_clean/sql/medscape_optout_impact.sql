-- Read-only impact on the stored Medscape baseline, not a raw-source rebuild.
WITH dropped_npis AS (
    SELECT DISTINCT npi_clean AS npi FROM {{ ref('stg_medscape__optout') }} WHERE npi_clean IS NOT NULL
), measured AS (
    SELECT m.email, m.npi, d.npi IS NOT NULL AS excluded
    FROM {{ ref('pii_clean') }} m LEFT JOIN dropped_npis d ON m.npi = d.npi
    WHERE m.source = 'medscape'
)
SELECT count(*) AS baseline_metric_rows,
       count_if(excluded) AS excluded_metric_rows,
       count_if(NOT excluded) AS retained_metric_rows,
       count(DISTINCT IF(excluded, npi, NULL)) AS excluded_npis,
       count(DISTINCT IF(excluded, email, NULL)) AS excluded_emails,
       count(DISTINCT IF(excluded, ROW(email, npi), NULL)) AS excluded_links,
       100e0 * count_if(excluded) / nullif(count(*), 0) AS excluded_metric_row_pct
FROM measured

-- Cumulative NPI-level exclusion applies only to Medscape, before metric computation.
SELECT m.source, count(*) AS opted_out_metric_rows
FROM {{ ref(var('metric_model')) }} m
WHERE m.source = 'medscape' AND EXISTS (
    SELECT 1 FROM {{ ref('stg_medscape__optout') }} o WHERE o.npi_clean = m.npi
)
GROUP BY m.source

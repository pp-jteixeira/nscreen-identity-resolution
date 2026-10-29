-- Preserve all registry rows and raw fields. Name normalization happens in intermediate.
SELECT s.*,
       {{ clean_text('s.npi') }} AS npi_clean
FROM {{ source('iceberg__npi', 'npi_reference') }} AS s

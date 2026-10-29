-- Row-preserving staging: raw columns plus cleaned helpers. no filters or unnesting.
SELECT s.*,
       {{ clean_text('s.npi') }} AS npi_clean,
       try_cast(s.day AS date) AS vendor_day,
       s.day IS NOT NULL AND try_cast(s.day AS date) IS NULL AS invalid_vendor_day,
       {{ clean_text('s.profession') }} AS profession_clean,
       {{ clean_text('s.primary_specialty') }} AS primary_specialty_clean
FROM {{ source('iceberg__thirdparty', 'quantummedica_hcpmeta') }} AS s

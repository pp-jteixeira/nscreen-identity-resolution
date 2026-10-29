-- Row-preserving staging: raw columns plus cleaned helpers; no filters or unnesting.
SELECT s.*,
       {{ clean_text('s.npi') }} AS npi_clean,
       try_cast(s.day AS date) AS vendor_day,
       s.day IS NOT NULL AND try_cast(s.day AS date) IS NULL AS invalid_vendor_day,
       try_cast(s.optout_day AS date) AS optout_day_clean
FROM {{ source('iceberg__thirdparty', 'medscape_npi_optout') }} AS s

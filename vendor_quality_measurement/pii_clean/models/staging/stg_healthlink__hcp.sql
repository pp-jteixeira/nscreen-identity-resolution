-- Row-preserving staging: raw columns plus cleaned helpers; no filters or unnesting.
SELECT s.*,
       {{ clean_text('s.npi') }} AS npi_clean,
       try_cast(s.day AS date) AS vendor_day,
       s.day IS NOT NULL AND try_cast(s.day AS date) IS NULL AS invalid_vendor_day,
       {{ clean_text('s.firstname') }} AS first_name_clean,
       {{ clean_text('s.lastname') }} AS last_name_clean,
       upper({{ clean_text('s.state') }}) AS state_clean,
       {{ clean_text('s.phone') }} AS phone_clean
FROM {{ source('iceberg__thirdparty', 'healthlink_hcp') }} AS s

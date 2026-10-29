-- Row-preserving staging: raw columns plus cleaned helpers; no filters or unnesting.
SELECT s.*,
       {{ clean_text('s.npi') }} AS npi_clean,
       try_cast(s.day AS date) AS vendor_day,
       s.day IS NOT NULL AND try_cast(s.day AS date) IS NULL AS invalid_vendor_day,
       {{ clean_email('s.email') }} AS email_list_clean,
       {{ clean_text('s.first_name') }} AS first_name_clean,
       {{ clean_text('s.last_name') }} AS last_name_clean,
       upper({{ clean_text('s.state') }}) AS state_clean
FROM {{ source('iceberg__thirdparty', 'quantummedica_hcpdata') }} AS s

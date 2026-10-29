-- Row-preserving staging: raw columns plus cleaned helpers; no filters or unnesting.
SELECT s.*,
       {{ clean_text('s.npi') }} AS npi_clean,
       {{ clean_email('s.emailaddress') }} AS email_clean,
       CAST(NULL AS date) AS vendor_day,
       false AS invalid_vendor_day,
       {{ clean_text('s.firstname') }} AS first_name_clean,
       {{ clean_text('s.lastname') }} AS last_name_clean,
       upper({{ clean_text('s.state') }}) AS state_clean
FROM {{ source('iceberg__thirdparty', 'drdb_npi') }} AS s

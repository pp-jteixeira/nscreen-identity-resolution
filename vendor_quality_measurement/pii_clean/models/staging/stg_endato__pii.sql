-- Row-preserving staging: raw columns plus cleaned helpers. no filters or unnesting.
SELECT s.*,
       {{ clean_text('s.npi') }} AS npi_clean,
       CAST(NULL AS date) AS vendor_day,
       false AS invalid_vendor_day,
       {{ clean_email('s.email_1_address') }} AS email_1_clean,
       {{ clean_email('s.email_2_address') }} AS email_2_clean,
       {{ clean_email('s.email_3_address') }} AS email_3_clean,
       {{ clean_email('s.email_4_address') }} AS email_4_clean,
       {{ clean_email('s.email_5_address') }} AS email_5_clean,
       {{ clean_text('s.name_first') }} AS person_first_name_clean,
       {{ clean_text('s.name_last') }} AS person_last_name_clean,
       {{ clean_email('s.email') }} AS provider_email_clean
FROM {{ source('iceberg__thirdparty', 'endato_pii') }} AS s

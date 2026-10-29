-- Row-preserving staging: raw columns plus cleaned helpers; no filters or unnesting.
SELECT s.*,
       {{ clean_text('s.npi') }} AS npi_clean,
       CAST(NULL AS date) AS vendor_day,
       false AS invalid_vendor_day,
       {{ clean_email('s.recommended_email') }} AS recommended_email_clean,
       {{ clean_email('s.recommended_personal_email') }} AS recommended_personal_email_clean,
       {{ clean_email('s.recommended_professional_email') }} AS recommended_professional_email_clean,
       {{ clean_email('s.current_work_email') }} AS current_work_email_clean,
       {{ clean_email('s.current_personal_email') }} AS current_personal_email_clean,
       {{ clean_text('s.name') }} AS name_clean,
       upper({{ clean_text('s.region') }}) AS state_clean
FROM {{ source('iceberg__npi', 'rocket_reach_npi_lookup') }} AS s

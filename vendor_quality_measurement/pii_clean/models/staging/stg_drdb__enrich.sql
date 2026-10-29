-- Row-preserving staging: raw columns plus cleaned helpers; no filters or unnesting.
SELECT s.*,
       {{ clean_text('s.npi') }} AS npi_clean,
       {{ clean_email('s.email') }} AS email_clean,
       CAST(NULL AS date) AS vendor_day,
       false AS invalid_vendor_day,
       {{ clean_text('s.name') }} AS name_clean,
       upper({{ clean_text('s.state') }}) AS state_clean
FROM {{ source('iceberg__thirdparty', 'npi_enrich_emails_hashlower') }} AS s

-- Row-preserving staging: raw columns plus cleaned helpers; no filters or unnesting.
SELECT s.*,
       {{ clean_text('s.npi') }} AS npi_clean,
       try_cast(s.day AS date) AS vendor_day,
       s.day IS NOT NULL AND try_cast(s.day AS date) IS NULL AS invalid_vendor_day,
       {{ clean_text('s.guid') }} AS guid_clean,
       {{ clean_text('s.profession') }} AS profession_clean
FROM {{ source('iceberg__thirdparty', 'medscape_pii_meta_global') }} AS s

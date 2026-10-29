-- Row-preserving staging: raw columns plus cleaned helpers; no filters or unnesting.
SELECT s.*,
       {{ clean_text('s.npi') }} AS npi_clean,
       {{ clean_email('s.hld_email') }} AS email_clean,
       try_cast(s.day AS date) AS vendor_day,
       s.day IS NOT NULL AND try_cast(s.day AS date) IS NULL AS invalid_vendor_day,
       try_cast(s.emailrank AS integer) AS email_rank_clean,
       {{ clean_text('s.bestemail') }} = '1' AS is_best_email_clean
FROM {{ source('iceberg__thirdparty', 'healthlink_email') }} AS s

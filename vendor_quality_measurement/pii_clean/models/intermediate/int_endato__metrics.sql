-- One row per source/email/NPI link.
WITH pii_versions AS (
-- Exact raw source content, excluding only delivery day.
{{ record_versions('stg_endato__pii') }}
),
email_candidates AS (
SELECT CAST('endato' AS varchar) AS source, u.email AS email, v.npi_clean AS npi,
       v.record_id, v.record_payload,
       {{ email_candidate_origin('endato', 'v', 'u.email_ordinal') }} AS email_origin,
       v.first_seen_day, v.last_seen_day, v.observed_day_count, v.observed_days,
       v.observation_count, v.undated_observation_count, v.invalid_day_observation_count,
       CAST(ARRAY['iceberg.thirdparty.endato_pii'] AS array(varchar)) AS source_tables,
       filter(ARRAY[CAST(NULL AS varchar)], x -> x IS NOT NULL) AS source_feeds,
       {{ norm_name('v.person_first_name_clean') }} AS first_name, {{ norm_name('v.person_last_name_clean') }} AS last_name,
       {{ state_values_from_payload('endato', 'v.record_payload') }} AS state_values,
       CAST(NULL AS varchar) AS guid, CAST(ARRAY[] AS array(varchar)) AS specialty_values
FROM pii_versions v
LEFT JOIN UNNEST({{ email_candidates('endato', 'v') }}) WITH ORDINALITY AS u(email, email_ordinal) ON true
WHERE u.email IS NOT NULL AND u.email <> '' AND v.npi_clean IS NOT NULL AND v.npi_clean <> ''
),
{{ link_metrics('endato') }}

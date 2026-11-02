-- One row per source/email/NPI link.
WITH lookup_versions AS (
-- Exact raw source content, excluding only delivery day.
{{ record_versions('stg_rocketreach__lookup') }}
),
email_candidates AS (
SELECT CAST('rocketreach' AS varchar) AS source, u.email AS email, v.npi_clean AS npi,
       v.record_id, v.record_payload,
       {{ email_candidate_origin('rocketreach', 'v', 'u.email_ordinal') }} AS email_origin,
       v.first_seen_day, v.last_seen_day, v.observed_day_count, v.observed_days,
       v.observation_count, v.undated_observation_count, v.invalid_day_observation_count,
       CAST(ARRAY['iceberg.npi.rocket_reach_npi_lookup'] AS array(varchar)) AS source_tables,
       filter(ARRAY[CAST(NULL AS varchar)], x -> x IS NOT NULL) AS source_feeds,
       {{ full_name_first('v.name_clean') }} AS first_name, {{ full_name_last('v.name_clean') }} AS last_name,
       {{ state_values_from_payload('rocketreach', 'v.record_payload') }} AS state_values,
       CAST(NULL AS varchar) AS guid, CAST(ARRAY[] AS array(varchar)) AS specialty_values
FROM lookup_versions v
LEFT JOIN UNNEST({{ email_candidates('rocketreach', 'v') }}) WITH ORDINALITY AS u(email, email_ordinal) ON true
WHERE u.email IS NOT NULL AND u.email <> '' AND v.npi_clean IS NOT NULL AND v.npi_clean <> ''
),
{{ link_metrics('rocketreach') }}

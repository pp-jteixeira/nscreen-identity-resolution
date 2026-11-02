-- One row per source/email/NPI link.
WITH enrich_versions AS (
-- Exact raw source content, excluding only delivery day.
{{ record_versions('stg_drdb__enrich') }}
),
npi_versions AS (
-- Exact raw source content, excluding only delivery day.
{{ record_versions('stg_drdb__npi') }}
),
email_candidates AS (
SELECT CAST('drdb' AS varchar) AS source, v.email_clean AS email, v.npi_clean AS npi,
       v.record_id, v.record_payload,
       CAST('emailaddress' AS varchar) AS email_origin,
       v.first_seen_day, v.last_seen_day, v.observed_day_count, v.observed_days,
       v.observation_count, v.undated_observation_count, v.invalid_day_observation_count,
       CAST(ARRAY['iceberg.thirdparty.drdb_npi'] AS array(varchar)) AS source_tables,
       filter(ARRAY[CAST(NULL AS varchar)], x -> x IS NOT NULL) AS source_feeds,
       {{ norm_name('v.first_name_clean') }} AS first_name, {{ norm_name('v.last_name_clean') }} AS last_name,
       {{ state_values_from_payload('drdb', 'v.record_payload') }} AS state_values,
       CAST(NULL AS varchar) AS guid, filter(ARRAY[json_extract_scalar(v.record_payload, '$.specialty')], x -> x IS NOT NULL) AS specialty_values
FROM npi_versions v
WHERE v.email_clean IS NOT NULL AND v.email_clean <> '' AND v.npi_clean IS NOT NULL AND v.npi_clean <> ''
UNION ALL
SELECT CAST('drdb' AS varchar) AS source, v.email_clean AS email, v.npi_clean AS npi,
       v.record_id, v.record_payload,
       CAST('email' AS varchar) AS email_origin,
       v.first_seen_day, v.last_seen_day, v.observed_day_count, v.observed_days,
       v.observation_count, v.undated_observation_count, v.invalid_day_observation_count,
       CAST(ARRAY['iceberg.thirdparty.npi_enrich_emails_hashlower'] AS array(varchar)) AS source_tables,
       filter(ARRAY[CAST(NULL AS varchar)], x -> x IS NOT NULL) AS source_feeds,
       {{ full_name_first('v.name_clean') }} AS first_name, {{ full_name_last('v.name_clean') }} AS last_name,
       {{ state_values_from_payload('drdb', 'v.record_payload') }} AS state_values,
       CAST(NULL AS varchar) AS guid, filter(ARRAY[json_extract_scalar(v.record_payload, '$.specialty')], x -> x IS NOT NULL) AS specialty_values
FROM enrich_versions v
WHERE v.email_clean IS NOT NULL AND v.email_clean <> '' AND v.npi_clean IS NOT NULL AND v.npi_clean <> ''
),
{{ link_metrics('drdb') }}

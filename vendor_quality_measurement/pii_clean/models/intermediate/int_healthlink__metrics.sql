-- One row per source/email/NPI link.
WITH email_versions AS (
-- Exact raw source content, excluding only delivery day.
{{ record_versions('stg_healthlink__email') }}
),
email_candidates AS (
SELECT CAST('healthlink' AS varchar) AS source, v.email_clean AS email, v.npi_clean AS npi,
       v.record_id, v.record_payload,
       CAST('hld_email' AS varchar) AS email_origin,
       v.first_seen_day, v.last_seen_day, v.observed_day_count, v.observed_days,
       v.observation_count, v.undated_observation_count, v.invalid_day_observation_count,
       CAST(ARRAY['iceberg.thirdparty.healthlink_email'] AS array(varchar)) AS source_tables,
       filter(ARRAY[CAST(NULL AS varchar)], x -> x IS NOT NULL) AS source_feeds,
       CAST(NULL AS varchar) AS first_name, CAST(NULL AS varchar) AS last_name,
       CAST(ARRAY[] AS array(varchar)) AS state_values,
       CAST(NULL AS varchar) AS guid, CAST(ARRAY[] AS array(varchar)) AS specialty_values
FROM email_versions v
WHERE v.email_clean IS NOT NULL AND v.email_clean <> '' AND v.npi_clean IS NOT NULL AND v.npi_clean <> ''
),
{{ link_metrics('healthlink') }}

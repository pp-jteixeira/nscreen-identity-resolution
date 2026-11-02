-- One row per source/email/NPI link.
WITH global_versions AS (
-- Cumulative NPI opt-outs precede version grouping and every downstream metric.
{% if var('medscape_versioned_records', '') %}
SELECT * FROM {{ var('medscape_versioned_records') }}
{% else %}
{{ record_versions('stg_medscape__global', exclude_npis_model='stg_medscape__optout') }}
{% endif %}
),
email_candidates AS (
SELECT CAST('medscape' AS varchar) AS source, v.email_clean AS email, v.npi_clean AS npi,
       v.record_id, v.record_payload,
       CAST('email_address' AS varchar) AS email_origin,
       v.first_seen_day, v.last_seen_day, v.observed_day_count, v.observed_days,
       v.observation_count, v.undated_observation_count, v.invalid_day_observation_count,
       CAST(ARRAY['iceberg.thirdparty.medscape_pii_global'] AS array(varchar)) AS source_tables,
       v.source_values AS source_feeds,
       {{ norm_name('v.first_name_clean') }} AS first_name, {{ norm_name('v.last_name_clean') }} AS last_name,
       {{ state_values_from_payload('medscape', 'v.record_payload') }} AS state_values,
       v.guid_clean AS guid, CAST(ARRAY[] AS array(varchar)) AS specialty_values
FROM global_versions v
WHERE v.email_clean IS NOT NULL AND v.email_clean <> '' AND v.npi_clean IS NOT NULL AND v.npi_clean <> ''
),
{{ link_metrics('medscape') }}

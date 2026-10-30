-- One row per exact source record and email position. Link deduplication is deferred.
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
       v.record_id, v.record_payload, CAST(1 AS bigint) AS email_ordinal,
       CAST('emailaddress' AS varchar) AS email_origin,
       v.first_seen_day, v.last_seen_day, v.observed_day_count, v.observed_days,
       v.observation_count, v.undated_observation_count, v.invalid_day_observation_count,
       CAST(ARRAY['iceberg.thirdparty.drdb_npi'] AS array(varchar)) AS source_tables,
       filter(ARRAY[CAST(NULL AS varchar)], x -> x IS NOT NULL) AS source_feeds,
       {{ norm_name('v.first_name_clean') }} AS first_name, {{ norm_name('v.last_name_clean') }} AS last_name
FROM npi_versions v
WHERE v.email_clean IS NOT NULL AND v.email_clean <> '' AND v.npi_clean IS NOT NULL AND v.npi_clean <> ''
UNION ALL
SELECT CAST('drdb' AS varchar) AS source, v.email_clean AS email, v.npi_clean AS npi,
       v.record_id, v.record_payload, CAST(1 AS bigint) AS email_ordinal,
       CAST('email' AS varchar) AS email_origin,
       v.first_seen_day, v.last_seen_day, v.observed_day_count, v.observed_days,
       v.observation_count, v.undated_observation_count, v.invalid_day_observation_count,
       CAST(ARRAY['iceberg.thirdparty.npi_enrich_emails_hashlower'] AS array(varchar)) AS source_tables,
       filter(ARRAY[CAST(NULL AS varchar)], x -> x IS NOT NULL) AS source_feeds,
       {{ full_name_first('v.name_clean') }} AS first_name, {{ full_name_last('v.name_clean') }} AS last_name
FROM enrich_versions v
WHERE v.email_clean IS NOT NULL AND v.email_clean <> '' AND v.npi_clean IS NOT NULL AND v.npi_clean <> ''
),
metric_records AS (
SELECT *, to_hex(sha256(to_utf8(record_id || chr(0) || cast(email_ordinal AS varchar)))) AS metric_row_id
FROM email_candidates
),
email_npi_counts AS (
-- Count reported NPIs within this vendor, across all retained records.
SELECT source, email, count(DISTINCT npi) AS email_npi_count
FROM metric_records
GROUP BY source, email
),
email_linkage AS (
-- This source has no delivery days. Multiple NPIs cannot establish reassignment.
SELECT source, email, email_npi_count,
       CAST(ARRAY[] AS array(date)) AS conflict_days,
       CASE WHEN email_npi_count = 1 THEN false
            ELSE CAST(NULL AS boolean) END AS has_been_reassigned
FROM email_npi_counts
),
name_inputs AS (
-- Preserve each source record and email position before name comparisons.
SELECT metric_row_id, email, npi, first_name, last_name
FROM metric_records
),
name_metrics AS (
{{ link_name_metrics(none, record_grain=true, input_relation='name_inputs', include_source_names=true) }}
),
metric_base AS (
-- One output per exact source record and email position. link deduplication is deferred.
SELECT m.source, m.email, m.npi,
       m.first_seen_day, m.last_seen_day, m.observed_day_count,
       m.observation_count, m.undated_observation_count, m.invalid_day_observation_count,
       m.source_tables, m.source_feeds,
       cast(current_timestamp AS timestamp(6) with time zone) AS computed_at,
       'exact_records_v1' AS definition_version,
       {{ email_format_valid('m.email') }} AS email_format_valid,
       {{ email_role_account('m.email') }} AS email_role_account,
       {{ email_domain_class('m.email') }} AS email_domain_class,
       n.email_matches_source_name, n.email_matches_registry_name,
       n.vendor_name_matches_registry_name,
       n.source_name_usable, n.registry_name_usable, n.registry_npi_present,
       m.record_id, m.metric_row_id, m.email_ordinal, m.email_origin, m.record_payload,
       e.email_npi_count,
       e.email_npi_count > 1 AS email_has_multiple_npis,
       e.has_been_reassigned,
       -- Compare all current undated records within this vendor.
       e.email_npi_count > 1 AS has_conflict_linkage,
       m.observed_days, array_sort(array_intersect(m.observed_days, e.conflict_days)) AS conflict_days,
       n.source_name_values,
       {{ state_values_from_payload('drdb', 'm.record_payload') }} AS source_state_values
FROM metric_records m
LEFT JOIN name_metrics n ON m.metric_row_id = n.metric_row_id
LEFT JOIN email_linkage e ON m.source = e.source AND m.email = e.email
),
facility_enriched AS (
{{ facility_enriched_records('metric_base') }}
),
specialty_enriched AS (
{{ specialty_enriched_records('facility_enriched') }}
),
relationship_metrics AS (
{{ name_consistency_metrics('specialty_enriched', facility=true, specialty=true) }}
),
registry_metrics AS (
{{ registry_status_records('relationship_metrics') }}
),
location_metrics AS (
{{ vendor_facility_records('registry_metrics') }}
),
cookie_metrics AS (
{{ cookie_location_records('location_metrics') }}
),
freshness_metrics AS (
{{ link_freshness_records('cookie_metrics', 'metric_records') }}
),
stability_inputs AS (
SELECT m.source, m.email, m.npi, m.observed_days, m.undated_observation_count,
       array_intersect(m.observed_days, e.conflict_days) AS conflict_days
FROM metric_records m LEFT JOIN email_linkage e ON m.source = e.source AND m.email = e.email
),
metrics AS (
{{ link_stability_records('freshness_metrics', 'stability_inputs') }}
)
{% if var('debug', false) %}
, comparisons AS (
{{ link_name_metrics(none, detail=true, record_grain=true, input_relation='name_inputs', include_source_names=true) }}
)
{{ debug_name_rows('metrics', 'comparisons') }}
{% else %}
SELECT * FROM metrics
{% endif %}

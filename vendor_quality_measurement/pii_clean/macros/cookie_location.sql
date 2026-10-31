{# Descriptive UID evidence only: no scores, fractional votes or row eligibility rules. #}
{% macro cookie_window_days() -%}{{ var('cookie_window_days', 3) }}{%- endmacro %}
{% macro cookie_window_start() -%}cast(date_add('day', -{{ cookie_window_days() }}, {{ location_evaluation_day() }}) AS date){%- endmacro %}
{% macro cookie_window_end() -%}cast(date_add('day', -1, {{ location_evaluation_day() }}) AS date){%- endmacro %}
{% macro cookie_hash(email) -%}lower(to_hex(sha256(to_utf8(lower(trim({{ email }})))))){%- endmacro %}
{% macro cookie_available_days(relation) -%}
{% if var('location_metadata_from_rows', false) %}
SELECT DISTINCT try_cast(day AS date) AS day FROM {{ relation }}
WHERE day BETWEEN cast({{ cookie_window_start() }} AS varchar) AND cast({{ cookie_window_end() }} AS varchar)
{% else %}
{% set parts = relation.split('.') %}
SELECT DISTINCT try_cast(partition.day AS date) AS day FROM {{ parts[0] }}.{{ parts[1] }}."{{ parts[2] }}$partitions"
WHERE record_count > 0 AND partition.day BETWEEN cast({{ cookie_window_start() }} AS varchar) AND cast({{ cookie_window_end() }} AS varchar)
{% endif %}
{%- endmacro %}
{% macro cookie_source_coverage() -%}
WITH mapping_days AS ({{ cookie_available_days(source('iceberg__thirdparty', 'liveintent_idsync')) }}),
geo_days AS ({{ cookie_available_days(source('iceberg__crossscreen', 'nscreen_geo_daily_ua')) }}),
available AS (
    SELECT coalesce((SELECT array_sort(array_agg(day)) FROM mapping_days WHERE day IS NOT NULL), cast(ARRAY[] AS array(date))) AS md,
           coalesce((SELECT array_sort(array_agg(day)) FROM geo_days WHERE day IS NOT NULL), cast(ARRAY[] AS array(date))) AS gd,
           transform(sequence({{ cookie_window_start() }}, {{ cookie_window_end() }}, INTERVAL '1' DAY), d -> cast(d AS date)) AS expected
)
SELECT cast({{ cookie_window_days() }} AS bigint) AS cookie_location_window_days,
       cast(cardinality(md) AS bigint) AS cookie_mapping_available_days,
       cast(cardinality(gd) AS bigint) AS cookie_location_available_days,
       filter(expected, d -> NOT contains(md, d)) AS cookie_mapping_missing_days,
       filter(expected, d -> NOT contains(gd, d)) AS cookie_location_missing_days,
       CASE WHEN cardinality(md) = {{ cookie_window_days() }} AND cardinality(gd) = {{ cookie_window_days() }} THEN 'all_source_days_present' ELSE 'missing_source_days' END AS cookie_location_window_status
FROM available
{%- endmacro %}
{% macro cookie_location_email_evidence(input_relation) -%}
WITH population AS (
    SELECT DISTINCT {{ cookie_hash('email') }} AS email_hash FROM {{ input_relation }}
), tokens AS (
    SELECT lower(trim(s.hashedemail_sha256)) AS email_hash, try_cast(s.day AS date) AS mapping_day,
           split(trim(t.token), ':') AS parts
    FROM {{ source('iceberg__thirdparty', 'liveintent_idsync') }} s
    JOIN population p ON lower(trim(s.hashedemail_sha256)) = p.email_hash
    CROSS JOIN UNNEST(split(coalesce(s.uids, ''), '|')) AS t(token)
    WHERE s.day BETWEEN cast({{ cookie_window_start() }} AS varchar) AND cast({{ cookie_window_end() }} AS varchar)
), bridge AS (
    SELECT email_hash, mapping_day, trim(element_at(parts, 2)) AS uid,
           array_sort(array_agg(DISTINCT lower(trim(element_at(parts, 1))))) AS uid_types
    FROM tokens WHERE cardinality(parts) = 2 AND nullif(trim(element_at(parts, 1)), '') IS NOT NULL
         AND nullif(trim(element_at(parts, 2)), '') IS NOT NULL
    GROUP BY email_hash, mapping_day, trim(element_at(parts, 2))
), zip_states AS (
    -- Never let duplicate ZIP3 keys multiply UID-day observations.
    SELECT trim(zip3) AS zip3,
           CASE WHEN count(DISTINCT {{ normalized_state('state') }}) = 1
                       AND count_if({{ normalized_state('state') }} IS NULL) = 0
                THEN max({{ normalized_state('state') }}) END AS state
    FROM {{ source('iceberg__jteixeira_ipa', 'tmp_zip3_to_state') }} GROUP BY trim(zip3)
), states AS (
    SELECT DISTINCT try_cast(g.day AS date) AS observation_day, g.uid, z.state
    FROM {{ source('iceberg__crossscreen', 'nscreen_geo_daily_ua') }} g
    JOIN (SELECT DISTINCT uid FROM bridge) u ON g.uid = u.uid
    LEFT JOIN zip_states z ON regexp_like(trim(g.geo), '^[0-9]{1,3}$') AND lpad(trim(g.geo), 3, '0') = z.zip3
    WHERE g.day BETWEEN cast({{ cookie_window_start() }} AS varchar) AND cast({{ cookie_window_end() }} AS varchar)
), uid_states AS (
    SELECT uid, state, count(DISTINCT observation_day) AS state_days,
           array_sort(array_agg(DISTINCT observation_day)) AS days
    FROM states GROUP BY uid, state
), scored AS (
    SELECT *, max(CASE WHEN state IS NOT NULL THEN state_days ELSE 0 END) OVER (PARTITION BY uid) AS top_days,
           count_if(state IS NOT NULL) OVER (PARTITION BY uid) AS state_count,
           array_distinct(flatten(array_agg(days) OVER (PARTITION BY uid))) AS observation_days
    FROM uid_states
), ranked AS (
    SELECT *, row_number() OVER (PARTITION BY uid ORDER BY CASE WHEN state IS NULL THEN 1 ELSE 0 END, state_days DESC, state) AS rn,
           count_if(state IS NOT NULL AND state_days = top_days) OVER (PARTITION BY uid) AS top_count
    FROM scored
), primary_states AS (
    SELECT * FROM ranked WHERE rn = 1
), uid_days AS (
    SELECT b.*, s.state, coalesce(s.top_count > 1, false) AS tied,
           coalesce(s.state_count > 1, false) AS multistate,
           coalesce(contains(s.observation_days, b.mapping_day), false) AS observed,
           coalesce(s.state IS NOT NULL AND contains(s.days, b.mapping_day), false) AS located
    FROM bridge b LEFT JOIN primary_states s ON b.uid = s.uid
)
SELECT email_hash, count(DISTINCT uid) AS cookie_count,
       count(DISTINCT mapping_day) AS cookie_mapping_days,
       count(*) AS cookie_mapped_uid_days,
       count_if(observed) AS cookie_observed_uid_days,
       count_if(located) AS cookie_located_uid_days,
       count_if(located AND NOT tied) AS cookie_eligible_uid_days,
       count(DISTINCT IF(located, uid, NULL)) AS cookie_located_count,
       count(DISTINCT IF(tied, uid, NULL)) AS cookie_primary_state_tied_count,
       count(DISTINCT IF(multistate, uid, NULL)) AS cookie_primary_state_multistate_count,
       count(DISTINCT IF(located AND NOT tied, mapping_day, NULL)) AS cookie_eligible_observed_days,
       min(IF(located AND NOT tied, mapping_day, NULL)) AS cookie_location_first_day,
       max(IF(located AND NOT tied, mapping_day, NULL)) AS cookie_location_last_day,
       array_sort(array_distinct(flatten(array_agg(uid_types)))) AS cookie_uid_types,
       array_sort(array_distinct(filter(array_agg(IF(located AND NOT tied, state, NULL)), s -> s IS NOT NULL))) AS cookie_state_values
FROM uid_days GROUP BY email_hash
{%- endmacro %}
{% macro cookie_state_comparison(states, alias='') -%}
CASE WHEN {{ alias ~ '.' if alias else '' }}cookie_location_status <> 'observed' THEN 'unknown_cookie_location'
     WHEN cardinality({{ states }}) = 0 THEN 'unknown_reference_state'
     WHEN NOT arrays_overlap({{ states }}, {{ alias ~ '.' if alias else '' }}cookie_state_values) THEN 'not_observed'
     WHEN cardinality({{ states }}) = 1 AND cardinality({{ alias ~ '.' if alias else '' }}cookie_state_values) = 1 THEN 'corroborated'
     ELSE 'mixed_state_evidence' END
{%- endmacro %}
{% macro cookie_location_records(input_relation) -%}
WITH email_evidence AS ({{ cookie_location_email_evidence(input_relation) }}),
coverage AS ({{ cookie_source_coverage() }}), joined AS (
    SELECT m.*,
{% for c in ['cookie_count', 'cookie_mapping_days', 'cookie_mapped_uid_days', 'cookie_observed_uid_days', 'cookie_located_uid_days', 'cookie_eligible_uid_days', 'cookie_located_count', 'cookie_primary_state_tied_count', 'cookie_primary_state_multistate_count', 'cookie_eligible_observed_days'] %}
       coalesce(e.{{ c }}, cast(0 AS bigint)) AS {{ c }},{% endfor %}
       e.cookie_location_first_day, e.cookie_location_last_day,
       coalesce(e.cookie_uid_types, cast(ARRAY[] AS array(varchar))) AS cookie_uid_types,
       coalesce(e.cookie_state_values, cast(ARRAY[] AS array(varchar))) AS cookie_state_values,
       coverage.*
    FROM {{ input_relation }} m LEFT JOIN email_evidence e ON {{ cookie_hash('m.email') }} = e.email_hash
    CROSS JOIN coverage
), status AS (
    SELECT *, cast(cardinality(cookie_state_values) AS bigint) AS cookie_state_count,
       CASE WHEN cookie_count = 0 THEN 'no_mapping'
            WHEN cookie_eligible_uid_days > 0 THEN 'observed'
            WHEN cookie_located_uid_days > 0 THEN 'ambiguous_primary_state'
            WHEN cookie_observed_uid_days > 0 THEN 'unknown_state'
            ELSE 'no_state_observation' END AS cookie_location_status
    FROM joined
)
SELECT *, {{ cookie_state_comparison('source_state_values') }} AS cookie_vendor_state_evidence,
       {{ cookie_state_comparison("filter(ARRAY[facility_primary_state], s -> s IS NOT NULL)") }} AS cookie_facility_state_evidence,
       {{ cookie_window_start() }} AS cookie_location_window_start,
       {{ cookie_window_end() }} AS cookie_location_window_end,
       'iceberg.thirdparty.liveintent_idsync' AS cookie_mapping_table,
       'iceberg.crossscreen.nscreen_geo_daily_ua' AS cookie_location_geo_table,
       'iceberg.jteixeira_ipa.tmp_zip3_to_state' AS cookie_zip_mapping_table,
       'liveintent_primary_state_untied_v1' AS cookie_location_evidence_version
FROM status
{%- endmacro %}

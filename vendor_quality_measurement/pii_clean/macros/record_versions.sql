{% macro record_versions(stage_model, exclude_npis_model=none) -%}
{% set schema = record_schema(stage_model) %}
{% set volatile = schema.get('volatile', []) %}
{% set volatile_lists = schema.get('volatile_lists', []) %}
{% set group_helpers = schema.get('group_helpers', []) %}
{% set fields = schema.columns | rejectattr('name', 'equalto', 'day') | rejectattr('name', 'in', volatile) | list %}
{# Volatile fields never define a record. They are kept as sorted distinct arrays named <field>_values. #}
WITH grouped AS (
    SELECT
        {% for field in fields %}s."{{ field.name }}",{% endfor %}
        {% for helper in group_helpers %}s.{{ helper }},{% endfor %}
        {% for helper in schema.helpers if helper not in group_helpers %}arbitrary(s.{{ helper }}) AS {{ helper }},{% endfor %}
        {% for v in volatile %}
        {% if v in volatile_lists %}
        array_sort(array_distinct(flatten(array_agg(filter(transform(split(coalesce(CAST(s."{{ v }}" AS varchar), ''), ','), x -> nullif(trim(x), '')), x -> x IS NOT NULL))))) AS "{{ v }}_values",
        {% else %}
        coalesce(array_sort(array_agg(DISTINCT nullif(trim(CAST(s."{{ v }}" AS varchar)), '')) FILTER (WHERE nullif(trim(CAST(s."{{ v }}" AS varchar)), '') IS NOT NULL)), CAST(ARRAY[] AS array(varchar))) AS "{{ v }}_values",
        {% endif %}
        {% endfor %}
        coalesce(array_sort(array_agg(DISTINCT vendor_day) FILTER (WHERE vendor_day IS NOT NULL)), CAST(ARRAY[] AS array(date))) AS observed_days,
        min(vendor_day) AS first_seen_day,
        max(vendor_day) AS last_seen_day,
        nullif(count(DISTINCT vendor_day), 0) AS observed_day_count,
        count(*) AS observation_count,
        count_if(vendor_day IS NULL) AS undated_observation_count,
        count_if(invalid_vendor_day) AS invalid_day_observation_count
    FROM {{ ref(stage_model) }} s
    {% if exclude_npis_model is not none %}
    LEFT JOIN (SELECT npi_clean FROM {{ ref(exclude_npis_model) }}) excluded ON s.npi_clean = excluded.npi_clean
    WHERE excluded.npi_clean IS NULL
    {% endif %}
    {# npi_clean is deterministic from raw NPI. Including it preserves grain and permits NPI partition reuse. #}
    GROUP BY {% for field in fields %}s."{{ field.name }}"{% if not loop.last %}, {% endif %}{% endfor %}
             {% for helper in group_helpers %}, s.{{ helper }}{% endfor %}
             {% if exclude_npis_model is not none %}, s.npi_clean{% endif %}
), serialized AS (
    SELECT g.*, {{ record_payload(stage_model, 'g') }} AS identity_payload
    FROM grouped g
)
SELECT
    {% for field in fields %}s."{{ field.name }}",{% endfor %}
    {% for helper in schema.helpers %}s.{{ helper }},{% endfor %}
    {% for v in volatile %}s."{{ v }}_values",{% endfor %}
    s.observed_days, s.first_seen_day, s.last_seen_day, s.observed_day_count, s.observation_count,
    s.undated_observation_count, s.invalid_day_observation_count,
    {{ record_payload(stage_model, 's', true) }} AS record_payload,
    to_hex(sha256(to_utf8('{{ schema.table }}' || chr(0) || s.identity_payload{% for helper in group_helpers %} || chr(0) || coalesce(s.{{ helper }}, ''){% endfor %}))) AS record_id
FROM serialized s
{%- endmacro %}
{% macro email_candidates(vendor, alias) -%}
{% if vendor == 'quantummedica' %}
transform(split({{ alias }}.email_list_clean, '|'), e -> lower(trim(e)))
{% elif vendor == 'endato' %}
ARRAY[{{ alias }}.email_1_clean, {{ alias }}.email_2_clean, {{ alias }}.email_3_clean, {{ alias }}.email_4_clean, {{ alias }}.email_5_clean]
{% elif vendor == 'rocketreach' %}
concat(coalesce(transform({{ alias }}.emails, e -> lower(trim(e.email))), CAST(ARRAY[] AS array(varchar))), ARRAY[{{ alias }}.recommended_email_clean, {{ alias }}.recommended_personal_email_clean, {{ alias }}.recommended_professional_email_clean, {{ alias }}.current_work_email_clean, {{ alias }}.current_personal_email_clean])
{% endif %}
{%- endmacro %}
{% macro email_candidate_origin(vendor, alias, ordinal) -%}
{% if vendor == 'quantummedica' %}
'email_token_' || cast({{ ordinal }} AS varchar)
{% elif vendor == 'endato' %}
'email_' || cast({{ ordinal }} AS varchar) || '_address'
{% else %}
CASE WHEN {{ ordinal }} <= coalesce(cardinality({{ alias }}.emails), 0)
     THEN 'emails[' || cast({{ ordinal }} AS varchar) || ']'
     ELSE element_at(ARRAY['recommended_email', 'recommended_personal_email', 'recommended_professional_email', 'current_work_email', 'current_personal_email'], {{ ordinal }} - coalesce(cardinality({{ alias }}.emails), 0)) END
{% endif %}
{%- endmacro %}
{% macro full_name_first(value) -%}
CASE WHEN cardinality(split({{ norm_name(value) }}, ' ')) >= 2 THEN element_at(split({{ norm_name(value) }}, ' '), 1) END
{%- endmacro %}
{% macro full_name_last(value) -%}
CASE WHEN cardinality(split({{ norm_name(value) }}, ' ')) >= 2 THEN element_at(split({{ norm_name(value) }}, ' '), -1) END
{%- endmacro %}
{% macro attribute_version_type() -%}
array(row(record_id varchar, first_seen_day date, last_seen_day date, observed_day_count bigint, observation_count bigint, email_origins array(varchar), record_payload varchar))
{%- endmacro %}
{% macro source_name_pair_type() -%}
array(row(first_name varchar, last_name varchar))
{%- endmacro %}
{% macro guid_day_type() -%}
array(row(guid varchar, days array(date)))
{%- endmacro %}
{% macro link_records(input_relation) -%}
{# One row per source/email/NPI link. Input rows are versioned records by email position.
   The latest version is the one with the unique greatest last_seen_day, or the only version. #}
WITH link_versions AS (
    SELECT source, email, npi, record_id,
           arbitrary(record_payload) AS record_payload,
           arbitrary(first_seen_day) AS first_seen_day, arbitrary(last_seen_day) AS last_seen_day,
           arbitrary(observed_day_count) AS observed_day_count, arbitrary(observed_days) AS observed_days,
           arbitrary(observation_count) AS observation_count,
           arbitrary(undated_observation_count) AS undated_observation_count,
           arbitrary(invalid_day_observation_count) AS invalid_day_observation_count,
           arbitrary(source_tables) AS source_tables, arbitrary(source_feeds) AS source_feeds,
           array_sort(array_agg(DISTINCT email_origin)) AS email_origins,
           arbitrary(first_name) AS first_name, arbitrary(last_name) AS last_name,
           arbitrary(state_values) AS state_values, arbitrary(guid) AS guid,
           arbitrary(specialty_values) AS specialty_values
    FROM {{ input_relation }}
    GROUP BY source, email, npi, record_id
), ranked_versions AS (
    SELECT *, count(*) OVER (PARTITION BY source, email, npi) AS version_count,
           max(last_seen_day) OVER (PARTITION BY source, email, npi) AS link_last_day,
           count(*) OVER (PARTITION BY source, email, npi, last_seen_day) AS same_day_versions
    FROM link_versions
), flagged_versions AS (
    SELECT *, version_count = 1 OR (last_seen_day = link_last_day AND same_day_versions = 1) AS is_latest
    FROM ranked_versions
)
SELECT source, email, npi,
       to_hex(sha256(to_utf8(source || chr(0) || email || chr(0) || npi))) AS link_id,
       min(first_seen_day) AS first_seen_day, max(last_seen_day) AS last_seen_day,
       nullif(cardinality(array_distinct(flatten(array_agg(observed_days)))), 0) AS observed_day_count,
       array_sort(array_distinct(flatten(array_agg(observed_days)))) AS observed_days,
       sum(observation_count) AS observation_count,
       sum(undated_observation_count) AS undated_observation_count,
       sum(invalid_day_observation_count) AS invalid_day_observation_count,
       array_sort(array_distinct(flatten(array_agg(source_tables)))) AS source_tables,
       array_sort(array_distinct(flatten(array_agg(source_feeds)))) AS source_feeds,
       count(*) AS record_count,
       array_sort(array_agg(record_id)) AS record_ids,
       max(CASE WHEN is_latest THEN record_id END) AS latest_record_id,
       array_sort(array_distinct(flatten(array_agg(email_origins)))) AS email_origins,
       array_agg(CAST(ROW(record_id, first_seen_day, last_seen_day, observed_day_count, observation_count, email_origins, record_payload)
           AS row(record_id varchar, first_seen_day date, last_seen_day date, observed_day_count bigint, observation_count bigint, email_origins array(varchar), record_payload varchar))
           ORDER BY first_seen_day, last_seen_day, record_id) AS attribute_versions,
       coalesce(array_agg(DISTINCT CAST(ROW(first_name, last_name) AS row(first_name varchar, last_name varchar)))
           FILTER (WHERE first_name IS NOT NULL OR last_name IS NOT NULL), CAST(ARRAY[] AS {{ source_name_pair_type() }})) AS source_names,
       max(CASE WHEN is_latest THEN first_name END) AS latest_first_name,
       max(CASE WHEN is_latest THEN last_name END) AS latest_last_name,
       array_sort(array_distinct(flatten(array_agg(state_values)))) AS source_state_values,
       coalesce(max(CASE WHEN is_latest THEN state_values END), CAST(ARRAY[] AS array(varchar))) AS source_state_values_latest,
       -- Every version contributes one entry, including versions without a GUID.
       array_agg(CAST(ROW(guid, observed_days) AS row(guid varchar, days array(date)))) AS guid_days,
       max(CASE WHEN is_latest THEN guid END) AS latest_guid,
       array_sort(array_distinct(flatten(array_agg(specialty_values)))) AS specialty_values
FROM flagged_versions
GROUP BY source, email, npi
{%- endmacro %}

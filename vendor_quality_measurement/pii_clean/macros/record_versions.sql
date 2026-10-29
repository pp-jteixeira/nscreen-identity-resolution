{% macro record_versions(stage_model) -%}
{% set schema = record_schema(stage_model) %}
{% set fields = schema.columns | rejectattr('name', 'equalto', 'day') | list %}
WITH grouped AS (
    SELECT
        {% for field in fields %}s."{{ field.name }}",{% endfor %}
        {% for helper in schema.helpers %}arbitrary(s.{{ helper }}) AS {{ helper }},{% endfor %}
        coalesce(array_sort(array_agg(DISTINCT vendor_day) FILTER (WHERE vendor_day IS NOT NULL)), CAST(ARRAY[] AS array(date))) AS observed_days,
        min(vendor_day) AS first_seen_day,
        max(vendor_day) AS last_seen_day,
        nullif(count(DISTINCT vendor_day), 0) AS observed_day_count,
        count(*) AS observation_count,
        count_if(vendor_day IS NULL) AS undated_observation_count,
        count_if(invalid_vendor_day) AS invalid_day_observation_count
    FROM {{ ref(stage_model) }} s
    GROUP BY {% for field in fields %}s."{{ field.name }}"{% if not loop.last %}, {% endif %}{% endfor %}
), serialized AS (
    SELECT g.*, {{ record_payload(stage_model, 'g') }} AS record_payload
    FROM grouped g
)
SELECT *, to_hex(sha256(to_utf8('{{ schema.table }}' || chr(0) || record_payload))) AS record_id
FROM serialized
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

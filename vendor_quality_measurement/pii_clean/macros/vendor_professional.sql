{# Vendor labels are compared within source/email and exact conflict dates. #}
{% macro vendor_label(value) -%}
CASE WHEN upper(regexp_replace(trim(cast({{ value }} AS varchar)), '\s+', ' '))
          NOT IN ('', 'NULL', 'NONE', 'UNKNOWN', 'N/A', 'NA', '\N', '-', 'OTHER',
                  'UNSPECIFIED', 'NOT SPECIFIED', 'NOT AVAILABLE', 'OTHER SPECIALTY', 'PROFESSION',
                  'SPECIALTY', 'PRIMARY_SPECIALTY', 'SECONDARY_SPECIALTY', 'TERTIARY_SPECIALTY')
     THEN upper(regexp_replace(trim(cast({{ value }} AS varchar)), '\s+', ' ')) END
{%- endmacro %}
{% macro vendor_labels(values) -%}
array_sort(array_distinct(filter(transform({{ values }}, v -> {{ vendor_label('v') }}), v -> v IS NOT NULL)))
{%- endmacro %}
{% macro vendor_professional_evidence_type() -%}
array(row(evidence_day date, source_table varchar, raw_specialties array(varchar), raw_professions array(varchar), specialties array(varchar), professions array(varchar)))
{%- endmacro %}
{% macro vendor_professional_comparison_type(kind) -%}
array(row(npi varchar, link_id varchar, evidence_day date, own_values array(varchar), peer_values array(varchar), shared_values array(varchar), shares_{{ kind }} boolean))
{%- endmacro %}
{% macro vendor_professional_records(input_relation, vendor, record_relation='metric_base', derive_conflicts=false) -%}
{% set dated_metadata = vendor in ['healthlink', 'quantummedica', 'medscape'] %}
WITH
professional_sources AS (
    {% if vendor == 'medscape' %}
    -- Medscape metadata is keyed by registration GUID. Pair each GUID with its own days.
    SELECT r.source, r.email, r.npi, r.link_id, g.guid AS guid, g.days AS observed_days,
           r.undated_observation_count, r.source_tables, r.specialty_values{% if not derive_conflicts %}, r.conflict_days, r.has_conflict_linkage{% endif %}
    FROM {{ record_relation }} r
    CROSS JOIN UNNEST(r.guid_days) AS g(guid, days)
    {% else %}
    SELECT r.source, r.email, r.npi, r.link_id, CAST(NULL AS varchar) AS guid, r.observed_days,
           r.undated_observation_count, r.source_tables, r.specialty_values{% if not derive_conflicts %}, r.conflict_days, r.has_conflict_linkage{% endif %}
    FROM {{ record_relation }} r
    {% endif %}
),
{% if derive_conflicts %}
professional_key_contexts AS (
    SELECT r.*, array_distinct(array_agg(CAST(ROW(npi, observed_days)
        AS ROW(npi varchar, days array(date)))) OVER (PARTITION BY source, email)) AS key_history
    FROM professional_sources r
), professional_key_days AS (
    SELECT *, array_sort(array_distinct(flatten(transform(filter(key_history, p -> p.npi <> npi),
        p -> array_intersect(observed_days, p.days))))) AS conflict_days,
        cardinality(array_distinct(transform(key_history, p -> p.npi))) AS npi_count
    FROM professional_key_contexts
),
{% endif %}
professional_records AS (
    {% if derive_conflicts %}
    SELECT source, email, npi, link_id, guid, specialty_values, observed_days, conflict_days,
           {% if vendor in ['endato', 'rocketreach', 'drdb'] %}npi_count > 1
           {% else %}CASE WHEN cardinality(conflict_days) > 0 THEN true
                          WHEN npi_count = 1 THEN false
                          WHEN undated_observation_count > 0 THEN CAST(NULL AS boolean)
                          ELSE false END{% endif %} AS has_conflict_linkage
           {% if vendor == 'drdb' %}, source_tables{% endif %}
    FROM professional_key_days
    {% else %}
    SELECT source, email, npi, link_id, guid, specialty_values, observed_days, conflict_days, has_conflict_linkage
           {% if vendor == 'drdb' %}, source_tables{% endif %}
    FROM professional_sources
    {% endif %}
),
{% if dated_metadata %}
professional_metadata AS (
    {% if vendor == 'medscape' and var('medscape_professional_metadata', '') %}
    SELECT npi, evidence_day, guid, raw_specialties, raw_professions FROM {{ var('medscape_professional_metadata') }}
    {% else %}
    SELECT npi_clean AS npi, vendor_day AS evidence_day,
           {% if vendor == 'medscape' %}nullif(trim(guid), '') AS guid,{% endif %}
           array_sort(array_distinct(filter(flatten(array_agg(ARRAY[
               {% if vendor == 'healthlink' %}cast(specialty AS varchar)
               {% else %}cast(primary_specialty AS varchar), cast(secondary_specialty AS varchar), cast(tertiary_specialty AS varchar){% endif %}
           ])), v -> v IS NOT NULL))) AS raw_specialties,
           {% if vendor == 'healthlink' %}CAST(ARRAY[] AS array(varchar))
           {% else %}array_sort(array_distinct(filter(array_agg(cast(profession AS varchar)), v -> v IS NOT NULL))){% endif %} AS raw_professions
    FROM {{ ref('stg_healthlink__hcp' if vendor == 'healthlink' else ('stg_quantummedica__hcpmeta' if vendor == 'quantummedica' else 'stg_medscape__meta')) }}
    WHERE npi_clean IS NOT NULL AND vendor_day IS NOT NULL
    GROUP BY npi_clean, vendor_day{% if vendor == 'medscape' %}, nullif(trim(guid), ''){% endif %}
    {% endif %}
),
{% endif %}
professional_inputs AS (
    SELECT r.source, r.email, r.npi, r.link_id, r.conflict_days, r.has_conflict_linkage, d.evidence_day,
           {% if dated_metadata %}
           coalesce(v.raw_specialties, CAST(ARRAY[] AS array(varchar))) AS raw_specialties,
           coalesce(v.raw_professions, CAST(ARRAY[] AS array(varchar))) AS raw_professions,
           '{{ {'healthlink': 'iceberg.thirdparty.healthlink_hcp', 'quantummedica': 'iceberg.thirdparty.quantummedica_hcpmeta', 'medscape': 'iceberg.thirdparty.medscape_pii_meta_global'}[vendor] }}' AS source_table
           {% elif vendor == 'drdb' %}
           r.specialty_values AS raw_specialties,
           CAST(ARRAY[] AS array(varchar)) AS raw_professions,
           element_at(r.source_tables, 1) AS source_table
           {% else %}
           CAST(ARRAY[] AS array(varchar)) AS raw_specialties,
           CAST(ARRAY[] AS array(varchar)) AS raw_professions,
           CAST(NULL AS varchar) AS source_table
           {% endif %}
    FROM professional_records r
    LEFT JOIN UNNEST(r.observed_days) AS d(evidence_day) ON true
    {% if dated_metadata %}
    LEFT JOIN professional_metadata v ON r.npi = v.npi AND d.evidence_day = v.evidence_day
        {% if vendor == 'medscape' %}AND r.guid = v.guid{% endif %}
    {% endif %}
), professional_days AS (
    SELECT *, {{ vendor_labels('raw_specialties') }} AS specialties,
           {{ vendor_labels('raw_professions') }} AS professions
    FROM professional_inputs
), professional_contexts AS (
    SELECT *, filter(array_agg(CASE WHEN has_conflict_linkage
                       AND (source IN ('endato', 'rocketreach', 'drdb') OR contains(conflict_days, evidence_day))
                   THEN CAST(ROW(npi, link_id, evidence_day, specialties, professions)
                       AS ROW(npi varchar, link_id varchar, evidence_day date, specialties array(varchar), professions array(varchar))) END)
               OVER (PARTITION BY source, email), p -> p IS NOT NULL) AS professional_peers
    FROM professional_days
), professional_comparisons AS (
    SELECT *,
           {% for kind, field in [('specialty', 'specialties'), ('profession', 'professions')] %}
           transform(filter(professional_peers, p -> has_conflict_linkage AND p.npi <> npi
                       AND (source IN ('endato', 'rocketreach', 'drdb') OR p.evidence_day = evidence_day)),
               p -> CAST(ROW(p.npi, p.link_id, evidence_day, {{ field }}, p.{{ field }},
                       array_sort(array_intersect({{ field }}, p.{{ field }})),
                       CASE WHEN cardinality({{ field }}) > 0 AND cardinality(p.{{ field }}) > 0
                            THEN arrays_overlap({{ field }}, p.{{ field }}) END)
                   AS ROW(npi varchar, link_id varchar, evidence_day date, own_values array(varchar),
                          peer_values array(varchar), shared_values array(varchar), shares_{{ kind }} boolean)))
               AS {{ kind }}_comparisons{% if not loop.last %},{% endif %}
           {% endfor %}
    FROM professional_contexts
), professional_summaries AS (
    SELECT source, link_id,
           array_sort(array_distinct(flatten(array_agg(specialties)))) AS source_vendor_specialty_values,
           array_sort(array_distinct(flatten(array_agg(professions)))) AS source_vendor_profession_values,
           array_sort(array_distinct(array_agg(CAST(ROW(evidence_day, source_table, raw_specialties, raw_professions, specialties, professions)
               AS ROW(evidence_day date, source_table varchar, raw_specialties array(varchar), raw_professions array(varchar), specialties array(varchar), professions array(varchar)))))) AS vendor_professional_evidence,
           array_sort(array_distinct(flatten(array_agg(specialty_comparisons)))) AS conflicting_npi_vendor_specialty_comparisons,
           array_sort(array_distinct(flatten(array_agg(profession_comparisons)))) AS conflicting_npi_vendor_profession_comparisons
    FROM professional_comparisons GROUP BY source, link_id
)
SELECT m.*, s.source_vendor_specialty_values, s.source_vendor_profession_values,
       s.vendor_professional_evidence, 'vendor_labels_exact_same_day_v1' AS vendor_professional_definition_version,
       CASE WHEN cardinality(s.conflicting_npi_vendor_specialty_comparisons) > 0
            THEN any_match(s.conflicting_npi_vendor_specialty_comparisons, p -> p.shares_specialty) END
           AS conflicting_npis_share_vendor_specialty,
       s.conflicting_npi_vendor_specialty_comparisons,
       CASE WHEN cardinality(s.conflicting_npi_vendor_profession_comparisons) > 0
            THEN any_match(s.conflicting_npi_vendor_profession_comparisons, p -> p.shares_profession) END
           AS conflicting_npis_share_vendor_profession,
       s.conflicting_npi_vendor_profession_comparisons
FROM {{ input_relation }} m LEFT JOIN professional_summaries s
    ON m.source = s.source AND m.link_id = s.link_id
{%- endmacro %}

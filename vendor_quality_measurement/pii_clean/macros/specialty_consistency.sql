{# Exact recognized NPPES taxonomy-code overlap across all fifteen slots; no label matching. #}
{% macro specialty_npi_lookup() -%}
WITH dictionary AS (
    SELECT DISTINCT upper(trim(code)) AS code
    FROM {{ source('iceberg__npi', 'npi_taxonomy') }}
    WHERE regexp_like(upper(trim(code)), '^[0-9A-Z]{10}$')
), provider_codes AS (
    SELECT trim(cast(p.npi AS varchar)) AS npi, upper(trim(u.code)) AS code
    FROM {{ source('iceberg__npi', 'nppes_npidata_latest') }} p
    CROSS JOIN UNNEST(ARRAY[
    {% for i in range(1, 16) %}p.healthcare_provider_taxonomy_code_{{ i }}{% if not loop.last %}, {% endif %}{% endfor %}
    ]) AS u(code)
    WHERE nullif(trim(cast(p.npi AS varchar)), '') IS NOT NULL
)
SELECT p.npi, array_sort(array_agg(DISTINCT p.code)) AS specialty_code_values
FROM provider_codes p JOIN dictionary d ON p.code = d.code
GROUP BY p.npi
{%- endmacro %}

{% macro specialty_enriched_records(input_relation) -%}
WITH specialty_reference AS ({{ specialty_npi_lookup() }})
SELECT m.*, coalesce(f.specialty_code_values, CAST(ARRAY[] AS array(varchar))) AS specialty_code_values,
       CAST('iceberg.npi.nppes_npidata_latest' AS varchar) AS specialty_reference_table,
       CAST('recognized_exact_taxonomy_all_slots_v1' AS varchar) AS specialty_definition_version
FROM {{ input_relation }} m LEFT JOIN specialty_reference f ON m.npi = f.npi
{%- endmacro %}

{% macro specialty_conflict_contexts() -%}
array_sort(array_distinct(filter(array_agg(
        CASE WHEN has_conflict_linkage THEN
            CAST(ROW(npi, conflict_days, specialty_code_values)
                 AS ROW(npi varchar, days array(date), specialties array(varchar))) END
        ) OVER (PARTITION BY source, email), x -> x IS NOT NULL)))
{%- endmacro %}

{% macro specialty_peer_comparisons() -%}
transform(filter(specialty_conflict_records, peer ->
               has_conflict_linkage AND peer.npi <> npi
               AND (source IN ('endato', 'rocketreach', 'drdb') OR arrays_overlap(conflict_days, peer.days))),
               peer -> CAST(ROW(peer.npi, array_sort(array_intersect(conflict_days, peer.days)), peer.specialties,
                   array_sort(array_intersect(specialty_code_values, peer.specialties)),
                   CASE WHEN cardinality(specialty_code_values) > 0 AND cardinality(peer.specialties) > 0
                        THEN arrays_overlap(specialty_code_values, peer.specialties) END)
                   AS ROW(npi varchar, conflict_days array(date), specialty_codes array(varchar),
                          shared_specialty_codes array(varchar), shares_specialty boolean)))
{%- endmacro %}

{# Read-only enrichment of saved metrics; existing name-history results stay unchanged. #}
{% macro specialty_consistency_metrics(input_relation) -%}
WITH specialty_records AS ({{ specialty_enriched_records(input_relation) }}),
specialty_contexts AS (
    SELECT *, {{ specialty_conflict_contexts() }} AS specialty_conflict_records FROM specialty_records
), specialty_comparisons AS (
    SELECT *, {{ specialty_peer_comparisons() }} AS conflicting_npi_specialty_comparisons
    FROM specialty_contexts
)
SELECT {{ consistency_base_columns('m') }},
       m.email_name_count, m.email_npi_has_name_conflict,
       m.conflicting_npis_share_name, m.conflicting_npi_name_comparisons,
       m.conflicting_npis_share_state, m.conflicting_npi_state_comparisons,
       m.specialty_code_values, m.specialty_reference_table, m.specialty_definition_version,
       CASE WHEN m.has_conflict_linkage AND cardinality(m.conflicting_npi_specialty_comparisons) > 0
            THEN any_match(m.conflicting_npi_specialty_comparisons, p -> p.shares_specialty)
       END AS conflicting_npis_share_specialty,
       m.conflicting_npi_specialty_comparisons
FROM specialty_comparisons m
{%- endmacro %}

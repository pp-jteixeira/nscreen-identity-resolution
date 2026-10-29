{# Provider-scoped clusters are not facility IDs. Compare facility NPIs across all ranks. #}
{% macro facility_npi_lookup() -%}
SELECT trim(provider_npi) AS npi,
       array_sort(array_distinct(filter(
           transform(flatten(array_agg(coalesce(facility_npis, CAST(ARRAY[] AS array(varchar))))),
                     f -> trim(f)),
           f -> regexp_like(f, '^[0-9]{10}$') AND f <> '0000000000'
       ))) AS facility_npi_values
FROM {{ source('bq_bi__analytics_prod', 'npi_facility_association') }}
WHERE nullif(trim(provider_npi), '') IS NOT NULL
GROUP BY trim(provider_npi)
{%- endmacro %}
{% macro facility_enriched_records(input_relation) -%}
WITH facility_reference AS ({{ facility_npi_lookup() }})
SELECT m.*, coalesce(f.facility_npi_values, CAST(ARRAY[] AS array(varchar))) AS facility_npi_values,
       CAST('bq_bi.analytics_prod.npi_facility_association' AS varchar) AS facility_reference_table,
       CAST('all_ranked_facility_npis_v1' AS varchar) AS facility_definition_version
FROM {{ input_relation }} m LEFT JOIN facility_reference f ON m.npi = f.npi
{%- endmacro %}
{% macro facility_conflict_contexts() -%}
array_sort(array_distinct(filter(array_agg(
        CASE WHEN has_conflict_linkage THEN
            CAST(ROW(npi, conflict_days, facility_npi_values)
                 AS ROW(npi varchar, days array(date), facilities array(varchar))) END
        ) OVER (PARTITION BY source, email), x -> x IS NOT NULL)))
{%- endmacro %}
{% macro facility_peer_comparisons() -%}
transform(filter(facility_conflict_records, peer ->
               has_conflict_linkage AND peer.npi <> npi
               AND (source IN ('endato', 'rocketreach', 'drdb') OR arrays_overlap(conflict_days, peer.days))),
               peer -> CAST(ROW(peer.npi, array_sort(array_intersect(conflict_days, peer.days)), peer.facilities,
                   array_sort(array_intersect(facility_npi_values, peer.facilities)),
                   CASE WHEN cardinality(facility_npi_values) > 0 AND cardinality(peer.facilities) > 0
                        THEN arrays_overlap(facility_npi_values, peer.facilities) END)
                   AS ROW(npi varchar, conflict_days array(date), facility_npis array(varchar),
                          shared_facility_npis array(varchar), shares_facility boolean)))
{%- endmacro %}
{# Read-only enrichment of saved metrics. existing name-history results stay unchanged. #}
{% macro facility_consistency_metrics(input_relation) -%}
WITH facility_records AS ({{ facility_enriched_records(input_relation) }}),
facility_contexts AS (
    SELECT *, {{ facility_conflict_contexts() }} AS facility_conflict_records FROM facility_records
), facility_comparisons AS (
    SELECT *, {{ facility_peer_comparisons() }} AS conflicting_npi_facility_comparisons
    FROM facility_contexts
)
SELECT {{ consistency_base_columns('m') }},
       m.email_name_count, m.email_npi_has_name_conflict,
       m.conflicting_npis_share_name, m.conflicting_npi_name_comparisons,
       m.conflicting_npis_share_state, m.conflicting_npi_state_comparisons,
       m.facility_npi_values, m.facility_reference_table, m.facility_definition_version,
       CASE WHEN m.has_conflict_linkage AND cardinality(m.conflicting_npi_facility_comparisons) > 0
            THEN any_match(m.conflicting_npi_facility_comparisons, p -> p.shares_facility)
       END AS conflicting_npis_share_facility,
       m.conflicting_npi_facility_comparisons
FROM facility_comparisons m
{%- endmacro %}

{# Complete, usable vendor names only. Reference names never fill missing vendor names. #}
{% macro source_name_array_type() -%}
array(row(first_name varchar, last_name varchar, first_variants array(varchar)))
{%- endmacro %}

{% macro consistency_base_columns(alias='') -%}
{% for field in ['source', 'email', 'npi', 'first_seen_day', 'last_seen_day', 'observed_day_count', 'observation_count', 'undated_observation_count', 'invalid_day_observation_count', 'source_tables', 'source_feeds', 'computed_at', 'definition_version', 'email_format_valid', 'email_role_account', 'email_domain_class', 'email_matches_source_name', 'email_matches_registry_name', 'vendor_name_matches_registry_name', 'source_name_usable', 'registry_name_usable', 'registry_npi_present', 'record_id', 'metric_row_id', 'email_ordinal', 'email_origin', 'record_payload', 'email_npi_count', 'email_has_multiple_npis', 'has_been_reassigned', 'has_conflict_linkage', 'observed_days', 'conflict_days', 'source_name_values', 'source_state_values'] %}{{ alias ~ '.' if alias else '' }}{{ field }}{% if not loop.last %}, {% endif %}{% endfor %}
{%- endmacro %}

{% macro names_disagree(a, b) -%}
({{ last_kind(a ~ '.last_name', b ~ '.last_name') }} = 'none'
 OR {{ first_kind(a ~ '.first_variants', a ~ '.first_name', b ~ '.first_variants', b ~ '.first_name') }} = 'none')
{%- endmacro %}

{% macro name_consistency_metrics(input_relation, facility=false, specialty=false) -%}
WITH name_sets AS (
    SELECT {{ consistency_base_columns() }},
           {% if facility %}facility_npi_values, facility_reference_table, facility_definition_version,
           {{ facility_conflict_contexts() }} AS facility_conflict_records,{% endif %}
           {% if specialty %}specialty_code_values, specialty_reference_table, specialty_definition_version,
           {{ specialty_conflict_contexts() }} AS specialty_conflict_records,{% endif %}
           array_distinct(flatten(array_agg(source_name_values) OVER (PARTITION BY source, email))) AS email_names,
           array_distinct(flatten(array_agg(source_name_values) OVER (PARTITION BY source, email, npi))) AS pair_names,
           -- Collect only conflicting records; keep their dates and names paired.
           array_sort(array_distinct(filter(
               array_agg(CASE WHEN has_conflict_linkage THEN
                   CAST(ROW(npi, conflict_days, source_name_values) AS
                       ROW(npi varchar, days array(date), names {{ source_name_array_type() }}))
                   END) OVER (PARTITION BY source, email), x -> x IS NOT NULL
           ))) AS conflict_records,
           array_sort(array_distinct(filter(array_agg(
               CASE WHEN has_conflict_linkage THEN CAST(ROW(npi, conflict_days, source_state_values)
                   AS ROW(npi varchar, days array(date), states array(varchar))) END
               ) OVER (PARTITION BY source, email), x -> x IS NOT NULL))) AS conflict_state_records
    FROM {{ input_relation }}
), peer_comparisons AS (
    SELECT *, {% if facility %}{{ facility_peer_comparisons() }} AS conflicting_npi_facility_comparisons,{% endif %}
           {% if specialty %}{{ specialty_peer_comparisons() }} AS conflicting_npi_specialty_comparisons,{% endif %}
           transform(filter(conflict_records, peer ->
               has_conflict_linkage AND peer.npi <> npi
               AND (source IN ('endato', 'rocketreach', 'drdb')
                    OR arrays_overlap(conflict_days, peer.days))), peer ->
           CAST(ROW(peer.npi, array_sort(array_intersect(conflict_days, peer.days)), peer.names,
               CASE WHEN cardinality(source_name_values) > 0 AND cardinality(peer.names) > 0
                    THEN {{ any_in('source_name_values', 'own_name', any_in('peer.names', 'peer_name', 'NOT ' ~ names_disagree('own_name', 'peer_name'))) }}
               END) AS ROW(npi varchar, conflict_days array(date), names {{ source_name_array_type() }}, shares_name boolean)))
           AS conflicting_npi_name_comparisons,
           transform(filter(conflict_state_records, peer -> has_conflict_linkage AND peer.npi <> npi
               AND (source IN ('endato', 'rocketreach', 'drdb') OR arrays_overlap(conflict_days, peer.days))),
               peer -> CAST(ROW(peer.npi, array_sort(array_intersect(conflict_days, peer.days)), peer.states,
                   CASE WHEN cardinality(source_state_values) > 0 AND cardinality(peer.states) > 0
                        THEN arrays_overlap(source_state_values, peer.states) END)
                   AS ROW(npi varchar, conflict_days array(date), states array(varchar), shares_state boolean)))
               AS conflicting_npi_state_comparisons
    FROM name_sets
)
SELECT {{ consistency_base_columns('s') }},
       CAST(cardinality(array_distinct(transform(email_names, x -> ROW(x.first_name, x.last_name)))) AS bigint) AS email_name_count,
       CASE WHEN cardinality(pair_names) = 0 THEN CAST(NULL AS boolean)
            ELSE {{ any_in('pair_names', 'a', any_in('pair_names', 'b', names_disagree('a', 'b'))) }}
       END AS email_npi_has_name_conflict,
       -- any_match preserves unknown comparisons unless another peer matches.
       CASE WHEN has_conflict_linkage AND cardinality(conflicting_npi_name_comparisons) > 0
            THEN {{ any_in('conflicting_npi_name_comparisons', 'comparison', 'comparison.shares_name') }}
       END AS conflicting_npis_share_name,
       conflicting_npi_name_comparisons,
       CASE WHEN has_conflict_linkage AND cardinality(conflicting_npi_state_comparisons) > 0
            THEN any_match(conflicting_npi_state_comparisons, p -> p.shares_state)
       END AS conflicting_npis_share_state,
       conflicting_npi_state_comparisons
       {% if facility %}, facility_npi_values, facility_reference_table, facility_definition_version,
       CASE WHEN has_conflict_linkage AND cardinality(conflicting_npi_facility_comparisons) > 0
            THEN any_match(conflicting_npi_facility_comparisons, p -> p.shares_facility)
       END AS conflicting_npis_share_facility,
       conflicting_npi_facility_comparisons{% endif %}
       {% if specialty %}, specialty_code_values, specialty_reference_table, specialty_definition_version,
       CASE WHEN has_conflict_linkage AND cardinality(conflicting_npi_specialty_comparisons) > 0
            THEN any_match(conflicting_npi_specialty_comparisons, p -> p.shares_specialty)
       END AS conflicting_npis_share_specialty,
       conflicting_npi_specialty_comparisons{% endif %}
FROM peer_comparisons s
{%- endmacro %}

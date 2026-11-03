{# Cross-vendor agreement for each link, read from the stored core of every other source. A source agrees on the NPI when it reports this email with this NPI and disagrees when it reports this email but never this NPI. State and name are compared only with sources that agree on the NPI, since other NPIs legitimately differ. Sources that do not report the email, or whose values are unknown, appear in no array. #}
{% macro cross_source_evidence_records(input_relation, core_relation) -%}
WITH xsrc_base AS (
    SELECT * FROM {{ input_relation }}
), xsrc_pairs AS (
    SELECT b.source, b.link_id, o.source AS other_source,
           bool_or(o.npi = b.npi) AS same_npi,
           bool_or(o.npi = b.npi AND cardinality(b.source_state_values) > 0 AND cardinality(o.source_state_values) > 0
                   AND arrays_overlap(b.source_state_values, o.source_state_values)) AS state_agree,
           bool_or(o.npi = b.npi AND cardinality(b.source_state_values) > 0 AND cardinality(o.source_state_values) > 0
                   AND NOT arrays_overlap(b.source_state_values, o.source_state_values)) AS state_disagree,
           bool_or(o.npi = b.npi AND cardinality(b.source_name_values) > 0 AND cardinality(o.source_name_values) > 0
                   AND {{ any_in('b.source_name_values', 'own_name', any_in('o.source_name_values', 'other_name', 'NOT ' ~ names_disagree('own_name', 'other_name'))) }}) AS name_agree,
           bool_or(o.npi = b.npi AND cardinality(b.source_name_values) > 0 AND cardinality(o.source_name_values) > 0
                   AND NOT {{ any_in('b.source_name_values', 'own_name', any_in('o.source_name_values', 'other_name', 'NOT ' ~ names_disagree('own_name', 'other_name'))) }}) AS name_disagree
    FROM xsrc_base b
    JOIN {{ core_relation }} o ON o.email = b.email AND o.source <> b.source
    WHERE b.email IS NOT NULL AND b.email <> '' AND b.npi IS NOT NULL AND b.npi <> ''
      AND o.npi IS NOT NULL AND o.npi <> ''
    GROUP BY b.source, b.link_id, o.source
), xsrc_agg AS (
    SELECT source, link_id,
           array_sort(array_agg(other_source) FILTER (WHERE same_npi)) AS npi_agree,
           array_sort(array_agg(other_source) FILTER (WHERE NOT same_npi)) AS npi_disagree,
           array_sort(array_agg(other_source) FILTER (WHERE state_agree)) AS state_agree,
           array_sort(array_agg(other_source) FILTER (WHERE state_disagree)) AS state_disagree,
           array_sort(array_agg(other_source) FILTER (WHERE name_agree)) AS name_agree,
           array_sort(array_agg(other_source) FILTER (WHERE name_disagree)) AS name_disagree
    FROM xsrc_pairs GROUP BY source, link_id
), xsrc_arrays AS (
    SELECT b.*,
           coalesce(a.npi_agree, CAST(ARRAY[] AS array(varchar))) AS xsrc_npi_agree_sources,
           coalesce(a.npi_disagree, CAST(ARRAY[] AS array(varchar))) AS xsrc_npi_disagree_sources,
           coalesce(a.state_agree, CAST(ARRAY[] AS array(varchar))) AS xsrc_state_agree_sources,
           coalesce(a.state_disagree, CAST(ARRAY[] AS array(varchar))) AS xsrc_state_disagree_sources,
           coalesce(a.name_agree, CAST(ARRAY[] AS array(varchar))) AS xsrc_name_agree_sources,
           coalesce(a.name_disagree, CAST(ARRAY[] AS array(varchar))) AS xsrc_name_disagree_sources
    FROM xsrc_base b LEFT JOIN xsrc_agg a ON b.source = a.source AND b.link_id = a.link_id
)
SELECT x.*,
       CAST(cardinality(xsrc_npi_agree_sources) AS bigint) AS xsrc_npi_agree_count,
       CAST(cardinality(xsrc_npi_disagree_sources) AS bigint) AS xsrc_npi_disagree_count,
       CAST(cardinality(xsrc_state_agree_sources) AS bigint) AS xsrc_state_agree_count,
       CAST(cardinality(xsrc_state_disagree_sources) AS bigint) AS xsrc_state_disagree_count,
       CAST(cardinality(xsrc_name_agree_sources) AS bigint) AS xsrc_name_agree_count,
       CAST(cardinality(xsrc_name_disagree_sources) AS bigint) AS xsrc_name_disagree_count,
       CAST(cardinality(xsrc_npi_agree_sources) + cardinality(xsrc_npi_disagree_sources) AS bigint) AS xsrc_email_source_count,
       'cross_source_evidence_v1' AS cross_source_evidence_version
FROM xsrc_arrays x
{%- endmacro %}

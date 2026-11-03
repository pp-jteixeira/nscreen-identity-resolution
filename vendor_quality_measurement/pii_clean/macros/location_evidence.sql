{# Evaluation-window evidence is retrospective to historical vendor records. #}
{% macro location_evaluation_day() -%}
{% if var('location_evidence_day', '') %}DATE '{{ var('location_evidence_day') }}'
{% else %}cast(current_timestamp AT TIME ZONE 'America/New_York' AS date){% endif %}
{%- endmacro %}
{% macro facility_state_lookup() -%}
WITH normalized AS (
    SELECT trim(cast(npi_facility_provider_npi AS varchar)) AS npi,
           {{ normalized_state('state_code') }} AS state,
           nullif(trim(cast(location AS varchar)), '') AS location
    FROM {{ source('bq_bi__analytics_prod', 'npi_facility_locations_with_ids') }}
    WHERE npi_facility_rank = 1
), grouped AS (
    SELECT npi, count(*) AS facility_rank1_rows,
           count(DISTINCT state) AS facility_rank1_state_count,
           count_if(state IS NULL) AS facility_rank1_unknown_state_rows,
           count_if(location IS NULL) AS facility_rank1_missing_location_rows,
           max(state) AS candidate_state
    FROM normalized WHERE nullif(npi, '') IS NOT NULL GROUP BY npi
)
SELECT npi, facility_rank1_rows, facility_rank1_state_count,
       facility_rank1_unknown_state_rows, facility_rank1_missing_location_rows,
       CASE WHEN facility_rank1_state_count = 1 AND facility_rank1_unknown_state_rows = 0
                  AND facility_rank1_missing_location_rows = 0 THEN candidate_state END AS facility_primary_state,
       CASE WHEN facility_rank1_state_count > 1 THEN 'ambiguous_state'
            WHEN facility_rank1_missing_location_rows > 0 THEN 'missing_location'
            WHEN facility_rank1_unknown_state_rows > 0 THEN 'missing_state'
            ELSE 'usable' END AS facility_reference_status
FROM grouped
{%- endmacro %}
{# One rank-1 claims-association row exists per NPI. Aggregation guards against duplicate reference rows. #}
{% macro facility_claims_lookup() -%}
SELECT trim(provider_npi) AS npi,
       max(claim_count) AS facility_claim_count,
       array_sort(array_distinct(filter(
           flatten(array_agg(transform(split(coalesce(sources, ''), ','), s -> trim(s)))),
           s -> s <> ''))) AS facility_sources
FROM {{ source('bq_bi__analytics_prod', 'npi_facility_association') }}
WHERE _rank = 1 AND nullif(trim(provider_npi), '') IS NOT NULL
GROUP BY trim(provider_npi)
{%- endmacro %}
{% macro vendor_facility_comparison(states='source_state_values') -%}
CASE WHEN facility_reference_status <> 'usable' THEN 'unknown_facility'
     WHEN cardinality({{ states }}) = 0 THEN 'unknown_vendor_state'
     WHEN contains({{ states }}, facility_primary_state)
          THEN CASE WHEN cardinality({{ states }}) = 1 THEN 'corroborated' ELSE 'mixed_vendor_states' END
     ELSE 'not_corroborated' END
{%- endmacro %}
{% macro vendor_facility_records(input_relation) -%}
WITH facility_reference AS ({{ facility_state_lookup() }}),
claims_reference AS ({{ facility_claims_lookup() }}), enriched AS (
    SELECT m.*, r.facility_primary_state,
           coalesce(r.facility_reference_status, 'no_rank1_association') AS facility_reference_status,
           coalesce(r.facility_rank1_rows, cast(0 AS bigint)) AS facility_rank1_rows,
           coalesce(r.facility_rank1_state_count, cast(0 AS bigint)) AS facility_rank1_state_count,
           coalesce(r.facility_rank1_unknown_state_rows, cast(0 AS bigint)) AS facility_rank1_unknown_state_rows,
           coalesce(r.facility_rank1_missing_location_rows, cast(0 AS bigint)) AS facility_rank1_missing_location_rows,
           c.facility_claim_count,
           coalesce(c.facility_sources, CAST(ARRAY[] AS array(varchar))) AS facility_sources,
           CASE WHEN c.npi IS NOT NULL THEN contains(c.facility_sources, 'Claims') END AS facility_claims_backed
    FROM {{ input_relation }} m LEFT JOIN facility_reference r ON m.npi = r.npi
    LEFT JOIN claims_reference c ON m.npi = c.npi
), compared AS (
    SELECT *, {{ vendor_facility_comparison() }} AS vendor_state_evidence,
           -- Latest-version states are null when the link has no single latest version.
           CASE WHEN source_state_values_latest IS NOT NULL
                THEN {{ vendor_facility_comparison('source_state_values_latest') }} END AS vendor_state_evidence_latest
    FROM enriched
)
SELECT *, CASE vendor_state_evidence WHEN 'corroborated' THEN true WHEN 'not_corroborated' THEN false END
              AS vendor_state_corroborated,
       CASE vendor_state_evidence_latest WHEN 'corroborated' THEN true WHEN 'not_corroborated' THEN false END
              AS vendor_state_corroborated_latest,
       {{ location_evaluation_day() }} AS location_evaluation_day,
       'bq_bi.analytics_prod.npi_facility_locations_with_ids' AS location_reference_table,
       'link_vendor_facility_state_v1' AS location_evidence_version,
       'bq_bi.analytics_prod.npi_facility_association' AS facility_claims_reference_table,
       'facility_claims_support_v1' AS facility_claims_definition_version
FROM compared
{%- endmacro %}

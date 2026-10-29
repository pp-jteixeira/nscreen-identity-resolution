{# Evaluation-window evidence is retrospective to historical vendor records. #}
{% macro location_evaluation_day() -%}
{% if var('location_evidence_day', '') %}DATE '{{ var('location_evidence_day') }}'
{% else %}cast(current_timestamp AT TIME ZONE 'Europe/Paris' AS date){% endif %}
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
{% macro vendor_facility_comparison() -%}
CASE WHEN facility_reference_status <> 'usable' THEN 'unknown_facility'
     WHEN cardinality(source_state_values) = 0 THEN 'unknown_vendor_state'
     WHEN contains(source_state_values, facility_primary_state)
          THEN CASE WHEN cardinality(source_state_values) = 1 THEN 'corroborated' ELSE 'mixed_vendor_states' END
     ELSE 'not_corroborated' END
{%- endmacro %}
{% macro vendor_facility_records(input_relation) -%}
WITH facility_reference AS ({{ facility_state_lookup() }}), enriched AS (
    SELECT m.*, r.facility_primary_state,
           coalesce(r.facility_reference_status, 'no_rank1_association') AS facility_reference_status,
           coalesce(r.facility_rank1_rows, cast(0 AS bigint)) AS facility_rank1_rows,
           coalesce(r.facility_rank1_state_count, cast(0 AS bigint)) AS facility_rank1_state_count,
           coalesce(r.facility_rank1_unknown_state_rows, cast(0 AS bigint)) AS facility_rank1_unknown_state_rows,
           coalesce(r.facility_rank1_missing_location_rows, cast(0 AS bigint)) AS facility_rank1_missing_location_rows
    FROM {{ input_relation }} m LEFT JOIN facility_reference r ON m.npi = r.npi
), compared AS (
    SELECT *, {{ vendor_facility_comparison() }} AS vendor_state_evidence FROM enriched
)
SELECT *, CASE vendor_state_evidence WHEN 'corroborated' THEN true WHEN 'not_corroborated' THEN false END
              AS vendor_state_corroborated,
       {{ location_evaluation_day() }} AS location_evaluation_day,
       'bq_bi.analytics_prod.npi_facility_locations_with_ids' AS location_reference_table,
       'record_vendor_facility_state_v1' AS location_evidence_version
FROM compared
{%- endmacro %}

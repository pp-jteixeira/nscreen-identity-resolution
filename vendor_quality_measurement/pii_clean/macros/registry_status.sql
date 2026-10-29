{# Current readable NPPES lifecycle evidence. never reconstruct historical ownership. #}
{% macro registry_status_day() -%}
{% if var('registry_status_as_of_day', '') %}DATE '{{ var('registry_status_as_of_day') }}'
{% else %}cast(current_timestamp AT TIME ZONE 'Europe/Paris' AS date){% endif %}
{%- endmacro %}
{% macro registry_lifecycle_type() -%}
array(row(deactivation_date varchar, reactivation_date varchar, replacement_npi varchar, deactivation_reason varchar))
{%- endmacro %}
{% macro registry_status_lookup() -%}
WITH lifecycle_rows AS (
    SELECT trim(cast(npi AS varchar)) AS npi,
           cast(npi_deactivation_date AS varchar) AS d,
           cast(npi_reactivation_date AS varchar) AS r,
           cast(replacement_npi AS varchar) AS replacement,
           cast(npi_deactivation_reason_code AS varchar) AS reason
    FROM {{ source('iceberg__npi', 'nppes_npidata_latest') }}
    WHERE npi IS NOT NULL
), grouped AS (
    SELECT npi, count(*) AS reference_row_count,
           -- Sort by serialized text: Trino cannot order ROW values with null fields.
           array_distinct(array_agg(CAST(ROW(d, r, replacement, reason)
               AS row(deactivation_date varchar, reactivation_date varchar, replacement_npi varchar, deactivation_reason varchar))
               ORDER BY json_format(cast(ROW(d, r, replacement, reason) AS json)))) AS evidence,
           array_distinct(array_agg(CAST(ROW(nullif(trim(d), ''), nullif(trim(r), ''),
               nullif(trim(replacement), ''), nullif(trim(reason), ''))
               AS row(d varchar, r varchar, replacement varchar, reason varchar)))) AS variants
    FROM lifecycle_rows GROUP BY npi
), parsed AS (
    SELECT *, cardinality(variants) AS variant_count,
           element_at(variants, 1) AS v,
           try_cast(element_at(variants, 1).d AS date) AS deactivation_day,
           try_cast(element_at(variants, 1).r AS date) AS reactivation_day,
           {{ registry_status_day() }} AS status_day
    FROM grouped
), classified AS (
    SELECT *, CASE
        WHEN variant_count <> 1 THEN 'conflicting_reference_records'
        WHEN (v.d IS NOT NULL AND deactivation_day IS NULL)
          OR (v.r IS NOT NULL AND reactivation_day IS NULL) THEN 'invalid_lifecycle_date'
        WHEN deactivation_day > status_day OR reactivation_day > status_day THEN 'future_lifecycle_date'
        WHEN v.replacement = npi THEN 'self_replacement'
        WHEN v.replacement IS NOT NULL AND
             (NOT regexp_like(v.replacement, '^[0-9]{10}$') OR v.replacement = '0000000000') THEN 'invalid_replacement_npi'
        WHEN v.reason IS NOT NULL AND deactivation_day IS NULL THEN 'reason_without_deactivation'
        WHEN deactivation_day = reactivation_day THEN 'ambiguous_event_order'
        WHEN v.replacement IS NOT NULL AND reactivation_day IS NOT NULL
             AND (deactivation_day IS NULL OR reactivation_day > deactivation_day) THEN 'replacement_with_reactivation'
        WHEN v.replacement IS NOT NULL THEN 'replacement_reported'
        WHEN deactivation_day IS NOT NULL AND
             (reactivation_day IS NULL OR deactivation_day > reactivation_day) THEN 'latest_event_deactivation'
        WHEN reactivation_day IS NOT NULL THEN 'latest_event_reactivation'
        ELSE 'no_deactivation_reported' END AS status_reason
    FROM parsed
)
SELECT npi,
       CASE status_reason WHEN 'replacement_reported' THEN 'replaced'
           WHEN 'latest_event_deactivation' THEN 'deactivated'
           WHEN 'latest_event_reactivation' THEN 'reactivated'
           WHEN 'no_deactivation_reported' THEN 'active_as_reported'
           ELSE 'unknown' END AS npi_registry_status,
       status_reason AS npi_registry_status_reason,
       CASE WHEN variant_count = 1 AND regexp_like(v.replacement, '^[0-9]{10}$')
                 AND v.replacement <> '0000000000' AND v.replacement <> npi
            THEN v.replacement END AS npi_registry_replacement_npi,
       CASE WHEN variant_count = 1 THEN deactivation_day END AS npi_registry_deactivation_date,
       CASE WHEN variant_count = 1 THEN reactivation_day END AS npi_registry_reactivation_date,
       reference_row_count AS npi_registry_reference_row_count,
       cast(variant_count AS bigint) AS npi_registry_variant_count,
       evidence AS npi_registry_lifecycle_evidence
FROM classified
{%- endmacro %}
{% macro registry_status_records(input_relation) -%}
WITH lifecycle_reference AS ({{ registry_status_lookup() }})
SELECT m.*,
       coalesce(r.npi_registry_status, 'not_found') AS npi_registry_status,
       coalesce(r.npi_registry_status_reason, 'no_nppes_record') AS npi_registry_status_reason,
       r.npi_registry_replacement_npi, r.npi_registry_deactivation_date, r.npi_registry_reactivation_date,
       coalesce(r.npi_registry_reference_row_count, cast(0 AS bigint)) AS npi_registry_reference_row_count,
       coalesce(r.npi_registry_variant_count, cast(0 AS bigint)) AS npi_registry_variant_count,
       coalesce(r.npi_registry_lifecycle_evidence, cast(ARRAY[] AS {{ registry_lifecycle_type() }})) AS npi_registry_lifecycle_evidence,
       {{ registry_status_day() }} AS npi_registry_status_as_of_day,
       'iceberg.npi.nppes_npidata_latest' AS npi_registry_reference_table,
       'nppes_lifecycle_consensus_v1' AS npi_registry_definition_version
FROM {{ input_relation }} m LEFT JOIN lifecycle_reference r ON m.npi = r.npi
{%- endmacro %}

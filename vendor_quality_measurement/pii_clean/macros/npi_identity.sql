{% macro npi_checksum_valid(value) -%}
CASE WHEN length({{ value }}) = 10 AND regexp_like({{ value }}, '^[0-9]{10}$') THEN mod(24
{% for i in range(1, 11) %}
{% if i % 2 == 1 %}
    + CASE WHEN try_cast(substr({{ value }}, {{ i }}, 1) AS integer) > 4
           THEN 2 * try_cast(substr({{ value }}, {{ i }}, 1) AS integer) - 9
           ELSE 2 * try_cast(substr({{ value }}, {{ i }}, 1) AS integer) END
{% else %}
    + try_cast(substr({{ value }}, {{ i }}, 1) AS integer)
{% endif %}
{% endfor %}
    , 10) = 0 END
{%- endmacro %}
{% macro npi_identity_lookup() -%}
WITH raw_reference AS (
    SELECT trim(cast(npi AS varchar)) AS npi, cast(entity_type_code AS varchar) AS raw_code
    FROM {{ source('iceberg__npi', 'nppes_npidata_latest') }} WHERE npi IS NOT NULL
)
SELECT npi, count(*) AS reference_rows,
       array_distinct(array_agg(CAST(ROW(raw_code) AS row(entity_type_code varchar)) ORDER BY raw_code)) AS evidence,
       array_distinct(array_agg(CAST(ROW(nullif(trim(raw_code), '')) AS row(code varchar)))) AS variants
FROM raw_reference GROUP BY npi
{%- endmacro %}
{% macro npi_identity_records(input_relation, npi_relation=none) -%}
WITH identifiers AS (
    SELECT DISTINCT npi FROM {{ npi_relation or input_relation }}
), registry AS ({{ npi_identity_lookup() }}), evaluated AS (
    SELECT n.npi,
           CASE WHEN nullif(trim(n.npi), '') IS NOT NULL THEN length(n.npi) = 10 AND regexp_like(n.npi, '^[1-4][0-9]{9}$') END AS format_valid,
           {{ npi_checksum_valid('n.npi') }} AS checksum_valid,
           coalesce(r.reference_rows, cast(0 AS bigint)) AS reference_rows,
           coalesce(r.evidence, cast(ARRAY[] AS array(row(entity_type_code varchar)))) AS evidence,
           coalesce(cardinality(r.variants), 0) AS variant_count,
           CASE WHEN r.reference_rows IS NULL THEN 'not_found'
                WHEN cardinality(r.variants) <> 1 THEN 'conflicting_reference_records'
                WHEN element_at(r.variants, 1).code IS NULL THEN 'missing_entity_type'
                WHEN element_at(r.variants, 1).code NOT IN ('1', '2') THEN 'unrecognized_entity_type'
                ELSE 'registry_consensus' END AS entity_reason,
           element_at(r.variants, 1).code AS entity_code
    FROM identifiers n LEFT JOIN registry r ON n.npi = r.npi
), classified AS (
    SELECT *, CASE WHEN nullif(trim(npi), '') IS NULL THEN 'missing'
                   WHEN length(npi) <> 10 OR NOT regexp_like(npi, '^[0-9]{10}$') THEN 'malformed'
                   WHEN NOT format_valid THEN 'unsupported_prefix'
                   WHEN NOT checksum_valid THEN 'checksum_failure'
                   ELSE 'valid' END AS structure_reason
    FROM evaluated
)
SELECT m.*, c.format_valid AS npi_format_valid, c.checksum_valid AS npi_checksum_valid,
       c.format_valid AND c.checksum_valid AS npi_structure_valid,
       c.structure_reason AS npi_structure_reason,
       CASE WHEN c.entity_reason = 'registry_consensus' THEN
                 CASE c.entity_code WHEN '1' THEN 'individual' WHEN '2' THEN 'organization' END
            ELSE 'unknown' END AS npi_entity_type,
       c.entity_reason AS npi_entity_type_reason,
       c.evidence AS npi_entity_type_evidence,
       c.reference_rows AS npi_entity_type_reference_row_count,
       cast(c.variant_count AS bigint) AS npi_entity_type_variant_count,
       {% if var('npi_identity_as_of_day', '') %}DATE '{{ var('npi_identity_as_of_day') }}'{% else %}cast(current_timestamp AT TIME ZONE 'Europe/Paris' AS date){% endif %} AS npi_identity_as_of_day,
       'iceberg.npi.nppes_npidata_latest' AS npi_identity_reference_table,
       'npi_structure_entity_v1' AS npi_identity_definition_version
-- Equality keys enable a hash join while distinguishing null from empty identifiers.
FROM {{ input_relation }} m LEFT JOIN classified c ON coalesce(m.npi, '') = coalesce(c.npi, '') AND (m.npi IS NULL) = (c.npi IS NULL)
{%- endmacro %}

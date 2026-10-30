-- Recompute the check digit with a digit-position relation, independently of the unrolled macro.
WITH records AS (SELECT * FROM {{ ref(var('metric_model')) }}), identifiers AS (
    SELECT DISTINCT npi FROM records
), sums AS (
    SELECT npi, sum(CASE WHEN mod(pos, 2) = 1 THEN
               CASE WHEN digit * 2 > 9 THEN digit * 2 - 9 ELSE digit * 2 END ELSE digit END) AS digit_sum
    FROM (SELECT n.npi, p.pos, try_cast(substr(n.npi, p.pos, 1) AS integer) AS digit
          FROM identifiers n CROSS JOIN UNNEST(sequence(1, 9)) AS p(pos)) d
    GROUP BY npi
), expected AS (
    SELECT npi, CASE WHEN nullif(trim(npi), '') IS NOT NULL THEN length(npi) = 10 AND regexp_like(npi, '^[1-4][0-9]{9}$') END AS format_valid,
           CASE WHEN length(npi) = 10 AND regexp_like(npi, '^[0-9]{10}$')
                THEN try_cast(substr(npi, 10, 1) AS integer) = mod(10 - mod(24 + digit_sum, 10), 10) END AS checksum_valid
    FROM sums
), evidence AS (
    SELECT r.*, e.format_valid, e.checksum_valid,
           array_distinct(transform(npi_entity_type_evidence, x -> CAST(ROW(nullif(trim(x.entity_type_code), '')) AS row(code varchar)))) AS variants
    FROM records r JOIN expected e ON coalesce(r.npi, '') = coalesce(e.npi, '') AND (r.npi IS NULL) = (e.npi IS NULL)
), reasons AS (
    SELECT *, CASE WHEN nullif(trim(npi), '') IS NULL THEN 'missing'
                  WHEN length(npi) <> 10 OR NOT regexp_like(npi, '^[0-9]{10}$') THEN 'malformed'
                  WHEN NOT format_valid THEN 'unsupported_prefix'
                  WHEN NOT checksum_valid THEN 'checksum_failure' ELSE 'valid' END AS structure_reason,
           CASE WHEN npi_entity_type_reference_row_count = 0 THEN 'not_found'
                WHEN cardinality(variants) <> 1 THEN 'conflicting_reference_records'
                WHEN element_at(variants, 1).code IS NULL THEN 'missing_entity_type'
                WHEN element_at(variants, 1).code NOT IN ('1', '2') THEN 'unrecognized_entity_type'
                ELSE 'registry_consensus' END AS entity_reason
    FROM evidence
)
SELECT source, count(*) AS failing_metric_rows FROM reasons
WHERE npi_format_valid IS DISTINCT FROM format_valid
   OR npi_checksum_valid IS DISTINCT FROM checksum_valid
   OR npi_structure_valid IS DISTINCT FROM (format_valid AND checksum_valid)
   OR npi_structure_reason IS DISTINCT FROM structure_reason
   OR npi_entity_type_reason IS DISTINCT FROM entity_reason
   OR npi_entity_type IS DISTINCT FROM CASE WHEN entity_reason = 'registry_consensus'
        THEN CASE element_at(variants, 1).code WHEN '1' THEN 'individual' WHEN '2' THEN 'organization' END ELSE 'unknown' END
   OR npi_entity_type_variant_count IS DISTINCT FROM cast(cardinality(variants) AS bigint)
   OR npi_entity_type_evidence IS NULL OR npi_entity_type_reference_row_count IS NULL
   OR npi_entity_type_reference_row_count < cardinality(npi_entity_type_evidence)
   OR cardinality(npi_entity_type_evidence) <> cardinality(array_distinct(npi_entity_type_evidence))
   OR (npi_entity_type_reference_row_count > 0 AND cardinality(npi_entity_type_evidence) = 0)
   OR npi_identity_as_of_day IS NULL
   OR npi_identity_reference_table IS DISTINCT FROM 'iceberg.npi.nppes_npidata_latest'
   OR npi_identity_definition_version IS DISTINCT FROM 'npi_structure_entity_v1'
GROUP BY source

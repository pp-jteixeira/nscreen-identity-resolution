-- Read-only statistics for 16_conflicting_npis_share_specialty.
-- Denominators remain within each source. no email-NPI deduplication.
-- Exact executed SQL exported from local conflicting_specialties_measure.json. result rows are excluded. Original source relations are retained.
-- All vendors and conflict-row denominators, including zero-conflict vendors
WITH specialty_reference AS (WITH dictionary AS (
    SELECT DISTINCT upper(trim(code)) AS code
    FROM iceberg.npi.npi_taxonomy
    WHERE regexp_like(upper(trim(code)), '^[0-9A-Z]{10}$')
), provider_codes AS (
    SELECT trim(cast(p.npi AS varchar)) AS npi, upper(trim(u.code)) AS code
    FROM iceberg.npi.nppes_npidata_latest p
    CROSS JOIN UNNEST(ARRAY[
    p.healthcare_provider_taxonomy_code_1, p.healthcare_provider_taxonomy_code_2, p.healthcare_provider_taxonomy_code_3, p.healthcare_provider_taxonomy_code_4, p.healthcare_provider_taxonomy_code_5, p.healthcare_provider_taxonomy_code_6, p.healthcare_provider_taxonomy_code_7, p.healthcare_provider_taxonomy_code_8, p.healthcare_provider_taxonomy_code_9, p.healthcare_provider_taxonomy_code_10, p.healthcare_provider_taxonomy_code_11, p.healthcare_provider_taxonomy_code_12, p.healthcare_provider_taxonomy_code_13, p.healthcare_provider_taxonomy_code_14, p.healthcare_provider_taxonomy_code_15
    ]) AS u(code)
    WHERE nullif(trim(cast(p.npi AS varchar)), '') IS NOT NULL
)
SELECT p.npi, array_sort(array_agg(DISTINCT p.code)) AS specialty_code_values
FROM provider_codes p JOIN dictionary d ON p.code = d.code
GROUP BY p.npi)
SELECT m.source, count(*) AS metric_rows, count(DISTINCT m.email) AS distinct_emails,
       count(DISTINCT ROW(m.email, m.npi)) AS distinct_links,
       count_if(cardinality(f.specialty_code_values) > 0) AS usable_specialty_rows,
       count_if(m.has_conflict_linkage) AS conflict_rows,
       count_if(m.has_conflict_linkage = false) AS not_applicable_rows,
       count_if(m.has_conflict_linkage IS NULL) AS unknown_timing_rows,
       count(DISTINCT IF(m.has_conflict_linkage, m.email, NULL)) AS conflict_emails
FROM iceberg.jteixeira_ipa.pii_clean m LEFT JOIN specialty_reference f ON m.npi = f.npi
GROUP BY m.source ORDER BY m.source

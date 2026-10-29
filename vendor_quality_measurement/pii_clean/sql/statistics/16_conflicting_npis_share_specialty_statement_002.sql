-- Conflict-row outcomes. no rows emitted for zero-conflict vendors
WITH measured AS (WITH saved_records AS (
    SELECT * FROM iceberg.jteixeira_ipa.pii_clean WHERE has_conflict_linkage
), evaluated AS (WITH specialty_records AS (WITH specialty_reference AS (WITH dictionary AS (
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
SELECT m.*, coalesce(f.specialty_code_values, CAST(ARRAY[] AS array(varchar))) AS specialty_code_values,
       CAST('iceberg.npi.nppes_npidata_latest' AS varchar) AS specialty_reference_table,
       CAST('recognized_exact_taxonomy_all_slots_v1' AS varchar) AS specialty_definition_version
FROM saved_records m LEFT JOIN specialty_reference f ON m.npi = f.npi),
specialty_contexts AS (
    SELECT *, array_sort(array_distinct(filter(array_agg(
        CASE WHEN has_conflict_linkage THEN
            CAST(ROW(npi, conflict_days, specialty_code_values)
                 AS ROW(npi varchar, days array(date), specialties array(varchar))) END
        ) OVER (PARTITION BY source, email), x -> x IS NOT NULL))) AS specialty_conflict_records FROM specialty_records
), specialty_comparisons AS (
    SELECT *, transform(filter(specialty_conflict_records, peer ->
               has_conflict_linkage AND peer.npi <> npi
               AND (source IN ('endato', 'rocketreach', 'drdb') OR arrays_overlap(conflict_days, peer.days))),
               peer -> CAST(ROW(peer.npi, array_sort(array_intersect(conflict_days, peer.days)), peer.specialties,
                   array_sort(array_intersect(specialty_code_values, peer.specialties)),
                   CASE WHEN cardinality(specialty_code_values) > 0 AND cardinality(peer.specialties) > 0
                        THEN arrays_overlap(specialty_code_values, peer.specialties) END)
                   AS ROW(npi varchar, conflict_days array(date), specialty_codes array(varchar),
                          shared_specialty_codes array(varchar), shares_specialty boolean))) AS conflicting_npi_specialty_comparisons
    FROM specialty_contexts
)
SELECT m.source, m.email, m.npi, m.first_seen_day, m.last_seen_day, m.observed_day_count, m.observation_count, m.undated_observation_count, m.invalid_day_observation_count, m.source_tables, m.source_feeds, m.computed_at, m.definition_version, m.email_format_valid, m.email_role_account, m.email_domain_class, m.email_matches_source_name, m.email_matches_registry_name, m.vendor_name_matches_registry_name, m.source_name_usable, m.registry_name_usable, m.registry_npi_present, m.record_id, m.metric_row_id, m.email_ordinal, m.email_origin, m.record_payload, m.email_npi_count, m.email_has_multiple_npis, m.has_been_reassigned, m.has_conflict_linkage, m.observed_days, m.conflict_days, m.source_name_values, m.source_state_values,
       m.email_name_count, m.email_npi_has_name_conflict,
       m.conflicting_npis_share_name, m.conflicting_npi_name_comparisons,
       m.conflicting_npis_share_state, m.conflicting_npi_state_comparisons,
       m.specialty_code_values, m.specialty_reference_table, m.specialty_definition_version,
       CASE WHEN m.has_conflict_linkage AND cardinality(m.conflicting_npi_specialty_comparisons) > 0
            THEN any_match(m.conflicting_npi_specialty_comparisons, p -> p.shares_specialty)
       END AS conflicting_npis_share_specialty,
       m.conflicting_npi_specialty_comparisons
FROM specialty_comparisons m) SELECT * FROM evaluated)
SELECT source, count(*) AS conflict_rows, count(DISTINCT metric_row_id) AS distinct_record_keys,
       count_if(conflicting_npis_share_specialty) AS shared_specialty_rows,
       count_if(conflicting_npis_share_specialty = false) AS different_specialty_rows,
       count_if(conflicting_npis_share_specialty IS NULL) AS unknown_specialty_rows,
       count(DISTINCT ROW(email, npi)) AS conflict_links,
       count(DISTINCT IF(conflicting_npis_share_specialty, ROW(email, npi), NULL)) AS shared_specialty_links,
       count(DISTINCT IF(conflicting_npis_share_specialty = false, ROW(email, npi), NULL)) AS different_specialty_links,
       count(DISTINCT IF(conflicting_npis_share_specialty IS NULL, ROW(email, npi), NULL)) AS unknown_specialty_links
FROM measured GROUP BY source ORDER BY source

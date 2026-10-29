-- Conflict-row outcomes. no rows emitted for zero-conflict vendors
WITH measured AS (WITH saved_records AS (
    SELECT * FROM iceberg.jteixeira_ipa.pii_clean WHERE has_conflict_linkage
), evaluated AS (WITH facility_reference AS (
    SELECT trim(provider_npi) AS npi,
       array_sort(array_distinct(filter(
           transform(flatten(array_agg(coalesce(facility_npis, CAST(ARRAY[] AS array(varchar))))),
                     f -> trim(f)),
           f -> regexp_like(f, '^[0-9]{10}$') AND f <> '0000000000'
       ))) AS facility_npi_values
FROM bq_bi.analytics_prod.npi_facility_association
WHERE nullif(trim(provider_npi), '') IS NOT NULL
GROUP BY trim(provider_npi)
), facility_records AS (
    -- The reference is unique by NPI. this LEFT JOIN preserves exact-record grain.
    SELECT m.*, coalesce(f.facility_npi_values, CAST(ARRAY[] AS array(varchar))) AS facility_npi_values,
           CAST('bq_bi.analytics_prod.npi_facility_association' AS varchar) AS facility_reference_table,
           CAST('all_ranked_facility_npis_v1' AS varchar) AS facility_definition_version
    FROM saved_records m LEFT JOIN facility_reference f ON m.npi = f.npi
), facility_contexts AS (
    SELECT *, array_sort(array_distinct(filter(array_agg(
        CASE WHEN has_conflict_linkage THEN
            CAST(ROW(npi, conflict_days, facility_npi_values)
                 AS ROW(npi varchar, days array(date), facilities array(varchar))) END
        ) OVER (PARTITION BY source, email), x -> x IS NOT NULL))) AS facility_conflict_records
    FROM facility_records
), facility_comparisons AS (
    SELECT *,
           transform(filter(facility_conflict_records, peer ->
               has_conflict_linkage AND peer.npi <> npi
               AND (source IN ('endato', 'rocketreach', 'drdb') OR arrays_overlap(conflict_days, peer.days))),
               peer -> CAST(ROW(peer.npi, array_sort(array_intersect(conflict_days, peer.days)), peer.facilities,
                   array_sort(array_intersect(facility_npi_values, peer.facilities)),
                   CASE WHEN cardinality(facility_npi_values) > 0 AND cardinality(peer.facilities) > 0
                        THEN arrays_overlap(facility_npi_values, peer.facilities) END)
                   AS ROW(npi varchar, conflict_days array(date), facility_npis array(varchar),
                          shared_facility_npis array(varchar), shares_facility boolean)))
               AS conflicting_npi_facility_comparisons
    FROM facility_contexts
)
SELECT m.source, m.email, m.npi, m.first_seen_day, m.last_seen_day, m.observed_day_count, m.observation_count, m.undated_observation_count, m.invalid_day_observation_count, m.source_tables, m.source_feeds, m.computed_at, m.definition_version, m.email_format_valid, m.email_role_account, m.email_domain_class, m.email_matches_source_name, m.email_matches_registry_name, m.vendor_name_matches_registry_name, m.source_name_usable, m.registry_name_usable, m.registry_npi_present, m.record_id, m.metric_row_id, m.email_ordinal, m.email_origin, m.record_payload, m.email_npi_count, m.email_has_multiple_npis, m.has_been_reassigned, m.has_conflict_linkage, m.observed_days, m.conflict_days, m.source_name_values, m.source_state_values,
       m.email_name_count, m.email_npi_has_name_conflict,
       m.conflicting_npis_share_name, m.conflicting_npi_name_comparisons,
       m.conflicting_npis_share_state, m.conflicting_npi_state_comparisons,
       m.facility_npi_values, m.facility_reference_table, m.facility_definition_version,
       CASE WHEN m.has_conflict_linkage AND cardinality(m.conflicting_npi_facility_comparisons) > 0
            THEN any_match(m.conflicting_npi_facility_comparisons, p -> p.shares_facility)
       END AS conflicting_npis_share_facility,
       m.conflicting_npi_facility_comparisons
FROM facility_comparisons m) SELECT * FROM evaluated)
SELECT source, count(*) AS conflict_rows, count(DISTINCT metric_row_id) AS distinct_record_keys,
       count_if(conflicting_npis_share_facility) AS shared_facility_rows,
       count_if(conflicting_npis_share_facility = false) AS different_facility_rows,
       count_if(conflicting_npis_share_facility IS NULL) AS unknown_facility_rows,
       count(DISTINCT ROW(email, npi)) AS conflict_links,
       count(DISTINCT IF(conflicting_npis_share_facility, ROW(email, npi), NULL)) AS shared_facility_links,
       count(DISTINCT IF(conflicting_npis_share_facility = false, ROW(email, npi), NULL)) AS different_facility_links,
       count(DISTINCT IF(conflicting_npis_share_facility IS NULL, ROW(email, npi), NULL)) AS unknown_facility_links
FROM measured GROUP BY source ORDER BY source

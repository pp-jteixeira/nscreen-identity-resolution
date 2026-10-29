-- Published-table shortcut: intentionally excludes computed unpublished groups.
WITH params AS (
    SELECT lower(trim('person@example.com')) AS input_email
)
SELECT
    -- ----------------------------------
    -- Attributes
    t.email,
    t.source,
    t.npi,
    array_join(transform(t.source_name_values, n -> trim(concat_ws(' ', n.first_name, n.last_name))), concat(chr(59), ' ')) AS name,
    array_join(t.source_state_values, concat(chr(59), ' ')) AS state,
    t.first_seen_day,
    t.last_seen_day,
    -- ----------------------------------
    -- Observation metrics for this exact record
    t.observation_count,
    t.observed_day_count,
    t.undated_observation_count,
    -- ----------------------------------
    -- Email quality and name matching
    t.email_format_valid,
    t.email_role_account,
    t.email_domain_class,
    t.email_matches_source_name,
    t.email_matches_registry_name,
    t.vendor_name_matches_registry_name,
    t.source_name_usable,
    t.registry_name_usable,
    t.registry_npi_present,
    -- ----------------------------------
    -- Email/NPI history and conflicts
    t.email_npi_count,
    t.email_has_multiple_npis,
    t.has_been_reassigned,
    t.has_conflict_linkage,
    t.email_name_count,
    t.email_npi_has_name_conflict,
    t.conflicting_npis_share_name,
    t.conflicting_npis_share_state,
    -- ----------------------------------
    -- Name-comparison entry counts for this record
    coalesce(cardinality(t.conflicting_npi_name_comparisons), 0)
        AS name_comparison_count,
    coalesce(cardinality(filter(t.conflicting_npi_name_comparisons,
                               x -> x.shares_name = false)), 0)
        AS name_mismatch_count,
    coalesce(cardinality(filter(t.conflicting_npi_name_comparisons,
                               x -> x.shares_name = true)), 0)
        AS shared_name_count,
    coalesce(cardinality(filter(t.conflicting_npi_name_comparisons,
                               x -> x.shares_name IS NULL)), 0)
        AS unknown_name_match_count,
    -- ----------------------------------
    -- Record identifier for further inspection
    t.metric_row_id
FROM iceberg.jteixeira_ipa.pii_clean t
CROSS JOIN params p
WHERE lower(trim(t.email)) = p.input_email
ORDER BY t.source, t.npi, t.last_seen_day DESC NULLS LAST, t.metric_row_id

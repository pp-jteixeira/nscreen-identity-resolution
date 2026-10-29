SELECT
    flag,
    count(*) AS row_count,
    count(DISTINCT ROW(email, npi)) AS distinct_pairs,
    count(DISTINCT email) AS distinct_emails,
    count(DISTINCT npi) AS distinct_npis
FROM iceberg.jteixeira_ipa.pii_clean
CROSS JOIN UNNEST(ARRAY[
    ROW('invalid_email_format', NOT email_format_valid),
    ROW('role_account', email_role_account),
    ROW('email_multiple_npis', email_has_multiple_npis),
    ROW('reported_npi_set_changed', has_been_reassigned),
    ROW('reassignment_unknown', has_been_reassigned IS NULL),
    ROW('conflict_linkage', has_conflict_linkage),
    ROW('pair_name_conflict', email_npi_has_name_conflict),
    ROW('vendor_registry_name_mismatch', NOT vendor_name_matches_registry_name),
    ROW('source_name_unusable', NOT source_name_usable),
    ROW('conflict_different_name_and_state',
        has_conflict_linkage
        AND conflicting_npis_share_name = false
        AND conflicting_npis_share_state = false)
]) AS flags(flag, applies)
WHERE applies = true
GROUP BY flag
ORDER BY row_count DESC

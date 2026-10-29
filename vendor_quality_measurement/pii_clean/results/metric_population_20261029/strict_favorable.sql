SELECT
    count(*) AS row_count,
    count(DISTINCT ROW(email, npi)) AS distinct_pairs,
    count(DISTINCT email) AS distinct_emails,
    count(DISTINCT npi) AS distinct_npis
FROM iceberg.jteixeira_ipa.pii_clean
WHERE email_format_valid = true
      AND email_matches_source_name = true
      AND email_matches_registry_name = true
      AND vendor_name_matches_registry_name = true
      AND source_name_usable = true
      AND registry_name_usable = true
      AND registry_npi_present = true
      AND email_role_account = false
      AND email_has_multiple_npis = false
      AND has_been_reassigned = false
      AND has_conflict_linkage = false
      AND email_npi_has_name_conflict = false
      AND email_npi_count = 1
      AND email_name_count = 1
      AND conflicting_npis_share_name IS NULL
      AND conflicting_npis_share_state IS NULL

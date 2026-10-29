WITH totals AS (
    SELECT
        count(*) AS total_rows,
        count(DISTINCT ROW(email, npi)) AS total_pairs,
        count(DISTINCT email) AS total_emails,
        count(DISTINCT npi) AS total_npis
    FROM iceberg.jteixeira_ipa.pii_clean
), grouped AS (
    SELECT
        observed_day_count,
        observation_count,
        undated_observation_count,
        invalid_day_observation_count,
        email_format_valid,
        email_role_account,
        email_domain_class,
        email_matches_source_name,
        email_matches_registry_name,
        vendor_name_matches_registry_name,
        source_name_usable,
        registry_name_usable,
        registry_npi_present,
        email_npi_count,
        email_has_multiple_npis,
        has_been_reassigned,
        has_conflict_linkage,
        email_name_count,
        email_npi_has_name_conflict,
        conflicting_npis_share_name,
        conflicting_npis_share_state,
        count(*) AS row_count,
        count(DISTINCT ROW(email, npi)) AS distinct_pairs,
        count(DISTINCT email) AS distinct_emails,
        count(DISTINCT npi) AS distinct_npis
    FROM iceberg.jteixeira_ipa.pii_clean
    GROUP BY 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21
)
SELECT
    g.*,
    round(100e0 * g.row_count / nullif(t.total_rows, 0), 4) AS rows_pct_total,
    round(100e0 * g.distinct_pairs / nullif(t.total_pairs, 0), 4) AS pairs_pct_total,
    round(100e0 * g.distinct_emails / nullif(t.total_emails, 0), 4) AS emails_pct_total,
    round(100e0 * g.distinct_npis / nullif(t.total_npis, 0), 4) AS npis_pct_total
FROM grouped g
CROSS JOIN totals t
ORDER BY g.row_count DESC

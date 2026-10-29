-- Full manual-check rows from the published table. no sample or email-NPI deduplication.
-- Names remain paired with the conflicting peer's actual overlapping days.
SELECT source, metric_row_id, email, npi, source_name_values,
       observed_days, conflict_days, conflicting_npis_share_name,
       peer_npi, overlapping_days, peer_names, shares_name
FROM iceberg.jteixeira_ipa.pii_clean
CROSS JOIN UNNEST(conflicting_npi_name_comparisons)
    AS peer(peer_npi, overlapping_days, peer_names, shares_name)

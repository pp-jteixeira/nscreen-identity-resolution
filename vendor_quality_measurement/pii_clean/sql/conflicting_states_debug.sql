-- Full inspection; append a source filter when reviewing one vendor.
SELECT source, metric_row_id, email, npi, source_state_values,
       observed_days, conflict_days, conflicting_npis_share_state,
       peer_npi, overlapping_days, peer_states, shares_state
FROM iceberg.jteixeira_ipa.pii_clean
CROSS JOIN UNNEST(conflicting_npi_state_comparisons)
    AS peer(peer_npi, overlapping_days, peer_states, shares_state)

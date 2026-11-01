WITH classified AS (
    SELECT metric_row_id,
           CASE WHEN cookie_location_status = 'observed'
                THEN 'observed_' || cookie_vendor_state_evidence
                ELSE cookie_location_status END AS example_case
    FROM iceberg.jteixeira_ipa.pii_clean FOR VERSION AS OF 4233051104478921549
    WHERE source = 'endato'
), chosen AS (
    SELECT example_case, min(metric_row_id) AS metric_row_id
    FROM classified
    WHERE example_case IN ('observed_corroborated', 'observed_not_observed',
        'ambiguous_primary_state', 'no_state_observation', 'no_mapping', 'unknown_state')
    GROUP BY example_case
)
SELECT m.source, m.email, m.npi, m.cookie_location_status,
       m.cookie_count AS mapped_uids,
       m.cookie_eligible_uid_days AS eligible_uid_days,
       m.cookie_primary_state_tied_count AS tied_uids,
       m.cookie_state_values AS states,
       m.source_state_values AS vendor_states,
       m.cookie_vendor_state_evidence AS vendor_evidence
FROM iceberg.jteixeira_ipa.pii_clean FOR VERSION AS OF 4233051104478921549 m
JOIN chosen c ON c.metric_row_id = m.metric_row_id
WHERE m.source = 'endato'
ORDER BY c.example_case

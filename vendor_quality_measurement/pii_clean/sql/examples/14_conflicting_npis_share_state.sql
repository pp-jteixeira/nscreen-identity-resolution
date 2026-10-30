WITH selected AS (
    SELECT *
    FROM iceberg.jteixeira_ipa.pii_clean FOR VERSION AS OF 8096642935433856886
    WHERE (source = 'endato' AND metric_row_id IN (
        '5A4F2A12631E80536E669103B3F317D42F2765161DD8DB94B5E0529DDDC5D98F',
        '5FBC85C91EE6BCD4497632464719C42645215081E9552AEFC2644F672A8CCD9F',
        'D13284F7A914B72A2E7C30495579F5B20C45368C0F2ACD40BBE0A10DFADB3DE1'))
       OR (source = 'haymarket' AND metric_row_id IN (
        '9DF2E9F9E7A4ECB5EE6C33558A69F6F91B5222D322F1CDB70BE08D0EE1FB82DC'))
)
SELECT m.source,
       m.npi,
       (element_at(m.conflicting_npi_state_comparisons, 1)).npi AS peer_npi,
       m.source_state_values AS own_values,
       (element_at(m.conflicting_npi_state_comparisons, 1)).states AS peer_values,
       m.has_conflict_linkage AS conflict,
       m.conflicting_npis_share_state AS shares_state
FROM selected m
ORDER BY m.source, m.metric_row_id

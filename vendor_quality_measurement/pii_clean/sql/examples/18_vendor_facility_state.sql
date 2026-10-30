WITH selected AS (
    SELECT *
    FROM iceberg.jteixeira_ipa.pii_clean FOR VERSION AS OF 8096642935433856886
    WHERE (source = 'endato' AND metric_row_id IN (
        '076750B47BF9525013CF247B1F4586BD63C3441A7597799E7FAFC4E08EAA4CA6',
        '7351D2A2087155D1835DBA4399370CD760431B0DE69D8DCC5B498F7D43C83E2F',
        'E03D083EF1264A05321CD9135171184D07BDF075F462D30469C3DC270B61AF29'))
       OR (source = 'healthlink' AND metric_row_id IN (
        'A96287FCC45637781C73F3B0A4B8B7F31EE7E0B7458875252C20087B8D2B6A32'))
       OR (source = 'quantummedica' AND metric_row_id IN (
        '1845B939777C8B052D855CC8A1B24DB40280A23F0DC7FE3AFFB7EA1020DA522A'))
)
SELECT m.source,
       m.source_state_values AS vendor_states,
       m.facility_primary_state AS facility_state,
       m.facility_reference_status,
       m.vendor_state_evidence,
       m.vendor_state_corroborated
FROM selected m
ORDER BY m.source, m.metric_row_id

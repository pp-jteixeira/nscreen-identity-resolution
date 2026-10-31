WITH selected AS (
    SELECT *
    FROM iceberg.jteixeira_ipa.pii_clean FOR VERSION AS OF 8811920360682490090
    WHERE (source = 'endato' AND metric_row_id IN (
        '3AB5531256593B67A556B04342AE72261F03C9B3416FD46E7250A59C2C6AB8C4',
        '943C32434D8F3C31FB2CE056B12EAA4B99EC80176D39E205E3F44D254A4D8156'))
       OR (source = 'quantummedica' AND metric_row_id IN (
        'DDC68949352F656A5940211F39FA5D49EBDFA57F7AB2B41CCF7C1E1F7278BABA'))
)
SELECT m.source,
       m.email,
       m.npi,
       concat(r.first_name, ' ', r.last_name) AS registry_name,
       m.registry_npi_present,
       m.registry_name_usable,
       m.email_matches_source_name,
       m.email_matches_registry_name
FROM selected m
LEFT JOIN iceberg.jteixeira_ipa.pii__int_npi__names r ON m.npi = r.npi
ORDER BY m.source, m.metric_row_id

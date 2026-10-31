WITH selected AS (
    SELECT *
    FROM iceberg.jteixeira_ipa.pii_clean FOR VERSION AS OF 8811920360682490090
    WHERE (source = 'endato' AND metric_row_id IN (
        'AA0491CD7AC32FC75FFE7748AA65628DEF3A37C570A2B2BF2D7AF4AABD426BDE'))
       OR (source = 'medscape' AND metric_row_id IN (
        'AB540EC836F806841DCEAF1D2D7CA8466CC6C031BD90119941498B57FA3E5872'))
)
SELECT m.source,
       m.email,
       m.email_role_account,
       m.email_format_valid
FROM selected m
ORDER BY m.source, m.metric_row_id

WITH selected AS (
    SELECT *
    FROM iceberg.jteixeira_ipa.pii_clean FOR VERSION AS OF 8811920360682490090
    WHERE (source = 'endato' AND metric_row_id IN (
        'E2D7F6ECD9E1A822A2486BDE5556AAAC8D2BCA39374213AEE006E8C9B5AADE31'))
       OR (source = 'medscape' AND metric_row_id IN (
        '1DB726D2A317E497F5864411FDC282F4EA7A5D2125946A98BD145F6BDF457BF7',
        '75941F2B89381BA06B01E0E4ADE6298599723535231BA3603A1C420DEB763599'))
)
SELECT m.source,
       m.email,
       m.email_format_valid
FROM selected m
ORDER BY m.source, m.metric_row_id

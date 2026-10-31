WITH selected AS (
    SELECT *
    FROM iceberg.jteixeira_ipa.pii_clean FOR VERSION AS OF 8811920360682490090
    WHERE (source = 'endato' AND metric_row_id IN (
        '15A7CE1D623FCBA4AE051F8C51990D1C50F1E52AFB488C415FFCF1AA87D52B5C',
        '9982987297DF72C149474BB117CF1E80D17C1D9C0C505EE5C907B87830133454',
        'A74664CA2BA51AE5D7B13D02524BAFA5CFEE1368279C5337D1EC275D7A0051FA'))
       OR (source = 'medscape' AND metric_row_id IN (
        'DBA5C659BCB71479B83AC76050B928A4EC4FAAED4C6057C6C2814DBBB52BB12C'))
)
SELECT m.source,
       m.email,
       regexp_extract(m.email, '@(.*)$', 1) AS domain,
       m.email_domain_class,
       m.email_format_valid
FROM selected m
ORDER BY m.source, m.metric_row_id

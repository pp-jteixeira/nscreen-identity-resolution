WITH selected AS (
    SELECT *
    FROM iceberg.jteixeira_ipa.pii_clean FOR VERSION AS OF 8096642935433856886
    WHERE (source = 'endato' AND metric_row_id IN (
        '7043AC9E562F5F136D74A9F97D058212CFA121114A1774A885886A4191415F38',
        'FD13E1A91B10E0169EB0E2880202F0C7024D164C9230CC158C3ABC85C2A6101D'))
       OR (source = 'quantummedica' AND metric_row_id IN (
        'D678C06341C0CDE9EE0FE677515A39A66D167424179488066216A273376FC028'))
)
SELECT m.source,
       split_part(m.email, '@', 1) AS mailbox,
       transform(m.source_name_values, n -> concat(n.first_name, ' ', n.last_name)) AS vendor_names,
       m.source_name_usable,
       m.email_matches_source_name
FROM selected m
ORDER BY m.source, m.metric_row_id

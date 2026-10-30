WITH selected AS (
    SELECT *
    FROM iceberg.jteixeira_ipa.pii_clean FOR VERSION AS OF 8096642935433856886
    WHERE (source = 'endato' AND metric_row_id IN (
        '01C4523510AD571FF0100E5AD6390B33758FCA91EA1A98BB39A1A47C4E5E54F3'))
       OR (source = 'healthlink' AND metric_row_id IN (
        'A881C610E7DFEE6D6B325E7584BE5A93D111097E21DA9F9614EF5D9BDBBD997D'))
       OR (source = 'quantummedica' AND metric_row_id IN (
        '5084F30B68BF7BE6EF578F1E2035E1868F1AD45605EB2542687E9AB72B88437D'))
)
SELECT m.source,
       substr(to_hex(sha256(to_utf8(m.email))), 1, 12) AS email_key,
       m.email_npi_count,
       m.email_observed_day_count AS email_days,
       m.link_observed_day_count AS link_days,
       m.has_been_reassigned,
       m.has_conflict_linkage
FROM selected m
ORDER BY m.source, m.metric_row_id

WITH selected AS (
    SELECT *
    FROM iceberg.jteixeira_ipa.pii_clean FOR VERSION AS OF 8096642935433856886
    WHERE (source = 'endato' AND metric_row_id IN (
        '2BB0A675D0303E69146D4E78DA29BFA8FA827A7B4299222CF647CACE91D06D07'))
       OR (source = 'healthlink' AND metric_row_id IN (
        '459E67998FCF06BC27D79A7CFC02EB236B0D36FEE1DCE6BCAD713ACD5FE6CEF5',
        '8CE13EFACD6E7ACB950A70D33FF7C820166332BF9E41BB9972E0978C00F82D63'))
)
SELECT m.source,
       substr(to_hex(sha256(to_utf8(m.email))), 1, 12) AS email_key,
       m.email_npi_count,
       m.email_has_multiple_npis,
       m.has_been_reassigned,
       m.has_conflict_linkage
FROM selected m
ORDER BY m.source, m.metric_row_id

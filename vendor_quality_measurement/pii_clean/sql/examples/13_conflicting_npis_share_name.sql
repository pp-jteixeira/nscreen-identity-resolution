WITH selected AS (
    SELECT *
    FROM iceberg.jteixeira_ipa.pii_clean FOR VERSION AS OF 8096642935433856886
    WHERE (source = 'endato' AND metric_row_id IN (
        '730FB3822EC1EB3855BF21A4E1C10C1F2788A9DAA943ED02124432207C2B0194',
        '9E1C49D1B6D6366B653D9BBBA7FB85204BD28AEA2CAAD89533B14325A83E98F4',
        'E303163DBAEAE62D4A912EB2F410B50DEE23ADE4ECA621053834DE90C8C0EDFF'))
       OR (source = 'haymarket' AND metric_row_id IN (
        '1577CCE5C0DE4DA85CBD4D8D5897CC938ADF6B1EB6170CB69C2ED4C93F231E8F'))
)
SELECT m.source,
       m.npi,
       (element_at(m.conflicting_npi_name_comparisons, 1)).npi AS peer_npi,
       transform(m.source_name_values, n -> concat(n.first_name, ' ', n.last_name)) AS own_values,
       transform((element_at(m.conflicting_npi_name_comparisons, 1)).names, n -> concat(n.first_name, ' ', n.last_name)) AS peer_values,
       m.has_conflict_linkage AS conflict,
       m.conflicting_npis_share_name AS shares_name
FROM selected m
ORDER BY m.source, m.metric_row_id

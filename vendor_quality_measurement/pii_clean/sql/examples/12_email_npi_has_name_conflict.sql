WITH selected AS (
    SELECT *
    FROM iceberg.jteixeira_ipa.pii_clean FOR VERSION AS OF 8096642935433856886
    WHERE (source = 'drdb' AND metric_row_id IN (
        '76F42EB2F2C6093316B5CDEF2587E5A52525DDC28EA8CF1B437507091D8AF857',
        '79F6E827954FADE1457B94E8CB35408A2927D2280745D63CDC9CD2A33FD0696E'))
       OR (source = 'quantummedica' AND metric_row_id IN (
        '213F802895D91A49015A7538C13C00FF8712BFA5CFE8584EE9CD7E96622024D2'))
), context_names AS (
    SELECT t.source, t.email, t.npi,
           array_sort(array_distinct(flatten(array_agg(transform(t.source_name_values, n -> concat(n.first_name, ' ', n.last_name)))))) AS names
    FROM iceberg.jteixeira_ipa.pii_clean FOR VERSION AS OF 8096642935433856886 t
    JOIN (SELECT DISTINCT source, email, npi FROM selected) k
      ON t.source = k.source AND t.email = k.email AND t.npi = k.npi
    GROUP BY t.source, t.email, t.npi
)
SELECT m.source,
       substr(to_hex(sha256(to_utf8(m.email))), 1, 12) AS email_key,
       m.email_npi_count,
       c.names AS link_names,
       m.email_npi_has_name_conflict
FROM selected m
LEFT JOIN context_names c ON m.source = c.source AND m.email = c.email AND m.npi = c.npi
ORDER BY m.source, m.metric_row_id

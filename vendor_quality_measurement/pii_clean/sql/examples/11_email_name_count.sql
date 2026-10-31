WITH selected AS (
    SELECT *
    FROM iceberg.jteixeira_ipa.pii_clean FOR VERSION AS OF 8811920360682490090
    WHERE (source = 'drdb' AND metric_row_id IN (
        '76F42EB2F2C6093316B5CDEF2587E5A52525DDC28EA8CF1B437507091D8AF857'))
       OR (source = 'endato' AND metric_row_id IN (
        '730FB3822EC1EB3855BF21A4E1C10C1F2788A9DAA943ED02124432207C2B0194'))
       OR (source = 'quantummedica' AND metric_row_id IN (
        '3DD35EF677E8852E5BADCA2E63D87755D8184021D9CBC395E23F6BBD95E7E8DE'))
), context_names AS (
    SELECT t.source, t.email,
           array_sort(array_distinct(flatten(array_agg(transform(t.source_name_values, n -> concat(n.first_name, ' ', n.last_name)))))) AS names
    FROM iceberg.jteixeira_ipa.pii_clean FOR VERSION AS OF 8811920360682490090 t
    JOIN (SELECT DISTINCT source, email FROM selected) k
      ON t.source = k.source AND t.email = k.email
    GROUP BY t.source, t.email
)
SELECT m.source,
       m.email,
       m.email_npi_count,
       m.email_name_count,
       c.names AS email_names,
       m.email_npi_has_name_conflict
FROM selected m
LEFT JOIN context_names c ON m.source = c.source AND m.email = c.email
ORDER BY m.source, m.metric_row_id

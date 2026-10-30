WITH selected AS (
    SELECT *
    FROM iceberg.jteixeira_ipa.pii_clean FOR VERSION AS OF 8096642935433856886
    WHERE (source = 'endato' AND metric_row_id IN (
        '730FB3822EC1EB3855BF21A4E1C10C1F2788A9DAA943ED02124432207C2B0194',
        '81EEC062442BE87D989714B321418BF79E372D7467D15AC482DE2844E199216D',
        'A3299D24002D082B3C08421FE21B7E983C55D975FD46ECF9BC388D5C60E3052F'))
       OR (source = 'haymarket' AND metric_row_id IN (
        '207590C83205FF116C6350B5F9ED7FD684F8341BDD55BA5CA2FF0A38755319AF'))
)
SELECT m.source,
       m.email,
       m.npi,
       (element_at(m.conflicting_npi_specialty_comparisons, 1)).npi AS peer_npi,
       m.specialty_code_values AS own_values,
       (element_at(m.conflicting_npi_specialty_comparisons, 1)).specialty_codes AS peer_values,
       m.has_conflict_linkage AS conflict,
       m.conflicting_npis_share_specialty AS shares_specialty
FROM selected m
ORDER BY m.source, m.metric_row_id

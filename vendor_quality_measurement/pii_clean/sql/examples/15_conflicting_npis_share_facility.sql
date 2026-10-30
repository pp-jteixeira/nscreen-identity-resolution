WITH selected AS (
    SELECT *
    FROM iceberg.jteixeira_ipa.pii_clean FOR VERSION AS OF 8096642935433856886
    WHERE (source = 'endato' AND metric_row_id IN (
        '730FB3822EC1EB3855BF21A4E1C10C1F2788A9DAA943ED02124432207C2B0194',
        'BA2E681A099C6DCF48E741F31F4DA9744B7A4D4FBF656281D78517944D4F72C4',
        'CE8141B8077B2FE80852C9AF88CB99C0FF2B3C84EB6C6C4293F90E954E801367'))
       OR (source = 'haymarket' AND metric_row_id IN (
        '3BA64E63FD9A2721167D2B60E3B60D71164171D99D17697F44AA1A7D35751BEE'))
)
SELECT m.source,
       m.npi,
       (element_at(m.conflicting_npi_facility_comparisons, 1)).npi AS peer_npi,
       m.facility_npi_values AS own_values,
       (element_at(m.conflicting_npi_facility_comparisons, 1)).facility_npis AS peer_values,
       m.has_conflict_linkage AS conflict,
       m.conflicting_npis_share_facility AS shares_facility
FROM selected m
ORDER BY m.source, m.metric_row_id

-- Display one stored peer comparison consistent with each record's outcome.
WITH selected AS (
    SELECT * FROM iceberg.jteixeira_ipa.pii_clean FOR VERSION AS OF 8811920360682490090
    WHERE (source = 'medscape' AND metric_row_id = '0088DFD5D04310BAA974C6E5FC6193832698547B2CB1DCE2FD1706BDBC90D982')
       OR (source = 'medscape' AND metric_row_id = '1A825CFC0781883F8EE8CD56AEC97ED97B6B6D343985DE7BA61A5C722AA6938E')
       OR (source = 'quantummedica' AND metric_row_id = '000F87BE1EBCB93F92B83E7EF1749A01A14C2B045B4346609AB50B7330A5B5B7')
       OR (source = 'medscape' AND metric_row_id = '000000292E237796D17BEC9BB60DA00A81701AF9AE2B875BF008FEE8FE171D10')
), evidence AS (
    SELECT m.*, element_at(filter(conflicting_npi_vendor_profession_comparisons, x -> x.shares_profession IS NOT DISTINCT FROM conflicting_npis_share_vendor_profession), 1) AS peer
    FROM selected m
)
SELECT source,email,npi,peer.npi AS peer_npi,peer.evidence_day,
       coalesce(peer.own_values,source_vendor_profession_values) AS own_values,peer.peer_values,
       has_conflict_linkage AS conflict,conflicting_npis_share_vendor_profession AS shares_profession
FROM evidence
ORDER BY source,email,npi

-- Display one stored peer comparison consistent with each record's outcome.
WITH selected AS (
    SELECT * FROM iceberg.jteixeira_ipa.pii_clean FOR VERSION AS OF 8811920360682490090
    WHERE (source = 'medscape' AND metric_row_id = '0B30EEBFE013B2D090F8D9018874F7013FA03BA19601857CAA925008050B3DF2')
       OR (source = 'medscape' AND metric_row_id = '0088DFD5D04310BAA974C6E5FC6193832698547B2CB1DCE2FD1706BDBC90D982')
       OR (source = 'medscape' AND metric_row_id = '854C681B0D4745D53A0B633CE658FEC97BC323DB8EF45516A8AA30C0B3556099')
       OR (source = 'medscape' AND metric_row_id = '000000292E237796D17BEC9BB60DA00A81701AF9AE2B875BF008FEE8FE171D10')
       OR (source = 'drdb' AND metric_row_id = '0008D8852D81B2FD4A1FA38F8361BCC927C5550E747F3ECF86E7D823D9997911')
), evidence AS (
    SELECT m.*, element_at(filter(conflicting_npi_vendor_specialty_comparisons, x -> x.shares_specialty IS NOT DISTINCT FROM conflicting_npis_share_vendor_specialty), 1) AS peer
    FROM selected m
)
SELECT source,email,npi,peer.npi AS peer_npi,peer.evidence_day,
       coalesce(peer.own_values,source_vendor_specialty_values) AS own_values,peer.peer_values,
       has_conflict_linkage AS conflict,conflicting_npis_share_vendor_specialty AS shares_specialty
FROM evidence
ORDER BY source,email,npi

-- Read-only statistics for 29_cross_source_evidence, from the stored xsrc_ columns.
-- Denominators are the links of each source. State and name columns count links with at least one source in the array.
-- State and name comparisons exist only where another source agrees on the NPI, so the comparable counts use that subset.
SELECT source,
  count(*) AS links,
  count_if(xsrc_email_source_count > 0) AS email_in_other_source,
  count_if(xsrc_npi_agree_count > 0) AS npi_agree,
  count_if(xsrc_npi_agree_count = 0 AND xsrc_npi_disagree_count > 0) AS npi_disagree_only,
  count_if(xsrc_npi_agree_count > 0 AND xsrc_npi_disagree_count > 0) AS npi_agree_and_other_npis,
  count_if(xsrc_state_agree_count > 0 OR xsrc_state_disagree_count > 0) AS state_comparable,
  count_if(xsrc_state_agree_count > 0) AS state_agree,
  count_if(xsrc_state_disagree_count > 0) AS state_disagree,
  count_if(xsrc_name_agree_count > 0 OR xsrc_name_disagree_count > 0) AS name_comparable,
  count_if(xsrc_name_agree_count > 0) AS name_agree,
  count_if(xsrc_name_disagree_count > 0) AS name_disagree
FROM iceberg.jteixeira_ipa.pii_clean
GROUP BY source
ORDER BY source

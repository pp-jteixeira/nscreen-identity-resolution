-- Read-only statistics for 29_cross_source_evidence.
-- Denominators are the distinct source, email and NPI links of each source. Agreement counts other sources only.
-- Equivalent to xsrc_npi_agree_count and xsrc_email_source_count recomputed from published emails and NPIs.
WITH l AS (
  SELECT DISTINCT source, lower(trim(email)) AS email, trim(npi) AS npi
  FROM iceberg.jteixeira_ipa.pii_clean
  WHERE npi IS NOT NULL AND trim(npi) <> '' AND email IS NOT NULL
), en AS (
  SELECT email, npi, count(DISTINCT source) AS src_n FROM l GROUP BY 1, 2
), em AS (
  SELECT email, count(DISTINCT source) AS email_src_n FROM l GROUP BY 1
), x AS (
  SELECT l.source, l.email, l.npi, en.src_n, em.email_src_n,
    (SELECT count(DISTINCT l2.npi) FROM l l2 WHERE l2.email = l.email AND l2.source <> l.source) AS other_npi_n,
    (SELECT count(*) FROM l l2 WHERE l2.email = l.email AND l2.source <> l.source AND l2.npi = l.npi) AS other_same
  FROM l JOIN en ON en.email = l.email AND en.npi = l.npi JOIN em ON em.email = l.email
)
SELECT source, count(*) AS links,
  count_if(src_n > 1) AS npi_agree_links,
  count_if(email_src_n > 1) AS email_in_other_source_links,
  count_if(other_npi_n > 0 AND other_same = 0) AS npi_disagree_only_links,
  count_if(other_same > 0 AND other_npi_n > 1) AS npi_agree_and_other_npis_links
FROM x GROUP BY 1 ORDER BY 1

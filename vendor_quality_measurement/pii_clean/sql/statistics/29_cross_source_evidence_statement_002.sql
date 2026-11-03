-- Read-only statistics for 29_cross_source_evidence, source pairs.
-- For each source, the links on which each other source agrees on the NPI. Denominators are the links of the source.
SELECT t.source, o AS other_source, count(*) AS links_agreeing
FROM iceberg.jteixeira_ipa.pii_clean t
CROSS JOIN UNNEST(t.xsrc_npi_agree_sources) AS u(o)
GROUP BY t.source, o
ORDER BY t.source, o

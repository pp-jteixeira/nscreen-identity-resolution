-- Read-only statistics for 28_domain_evidence, from the stored domain columns.
-- Denominators remain within each source and domain class. Domains are never pooled across sources.
-- The median is approximate. Thresholds: 10 NPIs, share 0.5.
SELECT source, email_domain_class, count(*) AS links, count(DISTINCT email_domain) AS domains,
count_if(email_domain IS NULL) AS no_domain,
count_if(domain_npi_count = 1) AS single_npi_domain_links,
count_if(domain_npi_count >= 10) AS links_on_domains_with_10_plus_npis,
approx_percentile(domain_npi_count, 0.5) AS domain_npi_count_p50,
count_if(domain_top_state_share = 1) AS links_single_state_domain,
count_if(domain_top_facility_share IS NOT NULL) AS links_with_facility_share,
count_if(domain_top_facility_share >= 0.5) AS links_top_facility_share_half_or_more
FROM iceberg.jteixeira_ipa.pii_clean
GROUP BY source, email_domain_class
ORDER BY source, email_domain_class

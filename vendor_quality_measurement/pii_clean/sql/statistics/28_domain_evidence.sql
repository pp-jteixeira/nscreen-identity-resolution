-- Read-only statistics for 28_domain_evidence.
-- Denominators remain within each source. Domains are never pooled across sources.
-- Domain aggregates are recomputed from published links with the stored domain macro. Thresholds: 10 NPIs, share 0.5.
WITH d AS (WITH domain_base AS (
    SELECT m.*, CASE WHEN position('@' IN m.email) > 0
                     THEN nullif(lower(regexp_extract(m.email, '@(.*)$', 1)), '') END AS email_domain
    FROM (SELECT source, email, npi, email_domain_class, facility_primary_state, facility_npi_values FROM iceberg.jteixeira_ipa.pii_clean) m
), domain_counts AS (
    SELECT source, email_domain, count(DISTINCT email) AS domain_email_count, count(DISTINCT npi) AS domain_npi_count
    FROM domain_base WHERE email_domain IS NOT NULL GROUP BY source, email_domain
), domain_npis AS (
    SELECT source, email_domain, npi, arbitrary(facility_primary_state) AS state, arbitrary(facility_npi_values) AS facilities
    FROM domain_base WHERE email_domain IS NOT NULL AND email_domain_class NOT IN ('free', 'unknown')
    GROUP BY source, email_domain, npi
), state_counts AS (
    SELECT source, email_domain, state, count(*) AS npis
    FROM domain_npis WHERE state IS NOT NULL GROUP BY source, email_domain, state
), state_agg AS (
    SELECT source, email_domain, sum(npis) AS domain_npis_with_state, count(*) AS domain_state_count, max(npis) AS top_npis
    FROM state_counts GROUP BY source, email_domain
), facility_counts AS (
    SELECT d.source, d.email_domain, f AS facility_npi, count(*) AS npis
    FROM domain_npis d CROSS JOIN UNNEST(d.facilities) AS t(f) GROUP BY d.source, d.email_domain, f
), facility_agg AS (
    SELECT source, email_domain, max(npis) AS top_npis,
           max_by(facility_npi, CAST(ROW(npis, facility_npi) AS ROW(npis bigint, facility_npi varchar))) AS top_facility_npi
    FROM facility_counts GROUP BY source, email_domain
), facility_npis_with AS (
    SELECT source, email_domain, count(*) AS domain_npis_with_facility FROM domain_npis
    WHERE cardinality(facilities) > 0 GROUP BY source, email_domain
)
SELECT b.*,
       c.domain_email_count, c.domain_npi_count,
       s.domain_npis_with_state, s.domain_state_count,
       CAST(s.top_npis AS double) / s.domain_npis_with_state AS domain_top_state_share,
       w.domain_npis_with_facility,
       f.top_facility_npi AS domain_top_facility_npi,
       CAST(f.top_npis AS double) / w.domain_npis_with_facility AS domain_top_facility_share,
       'domain_evidence_v1' AS domain_evidence_version
FROM domain_base b
LEFT JOIN domain_counts c ON b.source = c.source AND b.email_domain = c.email_domain
LEFT JOIN state_agg s ON b.source = s.source AND b.email_domain = s.email_domain
LEFT JOIN facility_agg f ON b.source = f.source AND b.email_domain = f.email_domain
LEFT JOIN facility_npis_with w ON b.source = w.source AND b.email_domain = w.email_domain)
SELECT source, email_domain_class, count(*) AS links, count(DISTINCT email_domain) AS domains,
count_if(email_domain IS NULL) AS no_domain,
count_if(domain_npi_count = 1) AS single_npi_domain_links,
count_if(domain_npi_count >= 10) AS links_on_domains_with_10_plus_npis,
approx_percentile(domain_npi_count, 0.5) AS domain_npi_count_p50,
count_if(domain_top_state_share = 1) AS links_single_state_domain,
count_if(domain_top_facility_share IS NOT NULL) AS links_with_facility_share,
count_if(domain_top_facility_share >= 0.5) AS links_top_facility_share_half_or_more
FROM d GROUP BY source, email_domain_class ORDER BY source, email_domain_class

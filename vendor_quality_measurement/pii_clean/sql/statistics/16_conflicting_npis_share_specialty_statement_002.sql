-- NPPES taxonomy evidence uses the published conflicting_npis_share_nppes_specialty flag
-- Statistics over published evidence in iceberg.jteixeira_ipa.pii_clean.
-- Reference evidence and evaluation dates come from the stored table.
SELECT source, count(*) AS conflict_rows, count(DISTINCT link_id) AS distinct_link_keys,
       count_if(conflicting_npis_share_nppes_specialty) AS shared_specialty_rows,
       count_if(conflicting_npis_share_nppes_specialty = false) AS different_specialty_rows,
       count_if(conflicting_npis_share_nppes_specialty IS NULL) AS unknown_specialty_rows,
       count(DISTINCT ROW(email, npi)) AS conflict_links,
       count(DISTINCT IF(conflicting_npis_share_nppes_specialty, ROW(email, npi), NULL)) AS shared_specialty_links,
       count(DISTINCT IF(conflicting_npis_share_nppes_specialty = false, ROW(email, npi), NULL)) AS different_specialty_links,
       count(DISTINCT IF(conflicting_npis_share_nppes_specialty IS NULL, ROW(email, npi), NULL)) AS unknown_specialty_links
FROM iceberg.jteixeira_ipa.pii_clean
WHERE has_conflict_linkage
GROUP BY source ORDER BY source

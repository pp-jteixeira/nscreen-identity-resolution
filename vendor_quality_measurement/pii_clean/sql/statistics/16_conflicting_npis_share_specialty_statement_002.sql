-- Statistics over published evidence in iceberg.jteixeira_ipa.pii_clean.
-- Reference evidence and evaluation dates come from the stored publication.
SELECT source, count(*) AS conflict_rows, count(DISTINCT metric_row_id) AS distinct_record_keys,
       count_if(conflicting_npis_share_specialty) AS shared_specialty_rows,
       count_if(conflicting_npis_share_specialty = false) AS different_specialty_rows,
       count_if(conflicting_npis_share_specialty IS NULL) AS unknown_specialty_rows,
       count(DISTINCT ROW(email, npi)) AS conflict_links,
       count(DISTINCT IF(conflicting_npis_share_specialty, ROW(email, npi), NULL)) AS shared_specialty_links,
       count(DISTINCT IF(conflicting_npis_share_specialty = false, ROW(email, npi), NULL)) AS different_specialty_links,
       count(DISTINCT IF(conflicting_npis_share_specialty IS NULL, ROW(email, npi), NULL)) AS unknown_specialty_links
FROM iceberg.jteixeira_ipa.pii_clean
WHERE has_conflict_linkage
GROUP BY source ORDER BY source

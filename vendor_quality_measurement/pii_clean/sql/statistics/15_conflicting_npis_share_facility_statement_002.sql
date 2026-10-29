-- Statistics over published evidence in iceberg.jteixeira_ipa.pii_clean.
-- Reference evidence and evaluation dates come from the stored publication.
SELECT source, count(*) AS conflict_rows, count(DISTINCT metric_row_id) AS distinct_record_keys,
       count_if(conflicting_npis_share_facility) AS shared_facility_rows,
       count_if(conflicting_npis_share_facility = false) AS different_facility_rows,
       count_if(conflicting_npis_share_facility IS NULL) AS unknown_facility_rows,
       count(DISTINCT ROW(email, npi)) AS conflict_links,
       count(DISTINCT IF(conflicting_npis_share_facility, ROW(email, npi), NULL)) AS shared_facility_links,
       count(DISTINCT IF(conflicting_npis_share_facility = false, ROW(email, npi), NULL)) AS different_facility_links,
       count(DISTINCT IF(conflicting_npis_share_facility IS NULL, ROW(email, npi), NULL)) AS unknown_facility_links
FROM iceberg.jteixeira_ipa.pii_clean
WHERE has_conflict_linkage
GROUP BY source ORDER BY source

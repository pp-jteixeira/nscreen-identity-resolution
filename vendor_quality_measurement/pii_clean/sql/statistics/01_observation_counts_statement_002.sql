-- Versions merged into each link. Latest version is the unique greatest last_seen_day, or the only version.
SELECT source,
       count(*) AS links,
       sum(record_count) AS versions,
       count_if(record_count > 1) AS multi_version_links,
       100e0 * count_if(record_count > 1) / count(*) AS multi_version_link_pct,
       max(record_count) AS max_versions_per_link,
       count_if(latest_record_id IS NULL) AS links_without_latest,
       100e0 * count_if(latest_record_id IS NULL) / count(*) AS links_without_latest_pct
FROM iceberg.jteixeira_ipa.pii_clean
GROUP BY source ORDER BY source

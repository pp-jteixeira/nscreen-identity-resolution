-- Any-version versus latest-version email-to-vendor-name match. Latest is null without a single latest version.
SELECT source,
       count(*) AS links,
       count_if(latest_record_id IS NOT NULL) AS links_with_latest,
       count_if(record_count > 1) AS multi_version_links,
       count_if(email_matches_source_name IS DISTINCT FROM email_matches_source_name_latest AND latest_record_id IS NOT NULL) AS differing_links,
       count_if(email_matches_source_name AND email_matches_source_name_latest = false) AS match_any_not_latest_links,
       count_if(email_matches_source_name AND email_matches_source_name_latest IS NULL AND latest_record_id IS NOT NULL) AS match_any_unknown_latest_links
FROM iceberg.jteixeira_ipa.pii_clean
GROUP BY source ORDER BY source

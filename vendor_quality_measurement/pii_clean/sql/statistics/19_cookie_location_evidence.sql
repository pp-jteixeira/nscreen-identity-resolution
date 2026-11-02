-- Stored source-date coverage, with one row per distinct window and coverage combination.
-- Multiple rows expose differing publication windows or source coverage.
SELECT DISTINCT cookie_location_window_start, cookie_location_window_end,
       cookie_location_window_days, cookie_mapping_available_days,
       cookie_location_available_days, cookie_mapping_missing_days,
       cookie_location_missing_days, cookie_location_window_status
FROM iceberg.jteixeira_ipa.pii_clean
ORDER BY cookie_location_window_start, cookie_location_window_end,
         cookie_mapping_available_days, cookie_location_available_days

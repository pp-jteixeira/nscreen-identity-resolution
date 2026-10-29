-- Read-only statistics for 19_cookie_location_evidence.
-- Denominators remain within each source. no email-NPI deduplication.
-- Exact executed SQL exported from local location_evidence_cookie.json. result rows are excluded. Original source relations are retained.
-- Evaluation-window source-date availability
WITH mapping_days AS (
SELECT DISTINCT try_cast(partition.day AS date) AS day FROM iceberg.thirdparty."liveintent_idsync$partitions"
WHERE record_count > 0 AND partition.day BETWEEN cast(cast(date_add('day', -7, DATE '2026-10-29'
) AS date) AS varchar) AND cast(cast(date_add('day', -1, DATE '2026-10-29'
) AS date) AS varchar)
),
geo_days AS (
SELECT DISTINCT try_cast(partition.day AS date) AS day FROM iceberg.crossscreen."nscreen_geo_daily_ua$partitions"
WHERE record_count > 0 AND partition.day BETWEEN cast(cast(date_add('day', -7, DATE '2026-10-29'
) AS date) AS varchar) AND cast(cast(date_add('day', -1, DATE '2026-10-29'
) AS date) AS varchar)
),
available AS (
    SELECT coalesce((SELECT array_sort(array_agg(day)) FROM mapping_days WHERE day IS NOT NULL), cast(ARRAY[] AS array(date))) AS md,
           coalesce((SELECT array_sort(array_agg(day)) FROM geo_days WHERE day IS NOT NULL), cast(ARRAY[] AS array(date))) AS gd,
           transform(sequence(cast(date_add('day', -7, DATE '2026-10-29'
) AS date), cast(date_add('day', -1, DATE '2026-10-29'
) AS date), INTERVAL '1' DAY), d -> cast(d AS date)) AS expected
)
SELECT cast(7 AS bigint) AS cookie_location_window_days,
       cast(cardinality(md) AS bigint) AS cookie_mapping_available_days,
       cast(cardinality(gd) AS bigint) AS cookie_location_available_days,
       filter(expected, d -> NOT contains(md, d)) AS cookie_mapping_missing_days,
       filter(expected, d -> NOT contains(gd, d)) AS cookie_location_missing_days,
       CASE WHEN cardinality(md) = 7 AND cardinality(gd) = 7 THEN 'all_source_days_present' ELSE 'missing_source_days' END AS cookie_location_window_status
FROM available

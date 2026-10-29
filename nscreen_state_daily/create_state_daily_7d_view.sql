-- State lookup for every UID in the seven newest available source partitions.
-- Source: one selected ZIP3 per UID/day, based on the production 15-day window.
-- Mapping: provider-derived ZIP3 -> state; unavailable mappings remain NULL.
-- This is a live view: dates and results follow source/mapping updates.
CREATE VIEW iceberg.jteixeira_ipa.tmp_nscreen_state_daily_ua_7d
SECURITY INVOKER
AS
WITH recent_days AS (
    SELECT partition.day AS day
    FROM iceberg.crossscreen."nscreen_geo_daily_ua$partitions"
    ORDER BY partition.day DESC
    LIMIT 7
)
SELECT g.day, g.uid, m.state
FROM iceberg.crossscreen.nscreen_geo_daily_ua g
INNER JOIN recent_days d ON g.day = d.day
LEFT JOIN iceberg.jteixeira_ipa.tmp_zip3_to_state m
    ON regexp_like(g.geo, '^[0-9]{1,3}$')
   AND lpad(g.geo, 3, '0') = m.zip3

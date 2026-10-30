-- Independently rebuild daily NPI sets from observations rather than stored conflict flags.
WITH records AS (SELECT * FROM {{ ref(var('metric_model')) }}), daily_links AS (
    SELECT DISTINCT source, email, npi, observed_day
    FROM records CROSS JOIN UNNEST(observed_days) AS d(observed_day)
    WHERE observed_day IS NOT NULL
), daily AS (
    SELECT source, email, observed_day, count(*) AS npis
    FROM daily_links GROUP BY source, email, observed_day
), email_days AS (
    SELECT source, email, count(*) AS email_days FROM daily GROUP BY source, email
), link_days AS (
    SELECT l.source, l.email, l.npi, count(*) AS link_days, count_if(d.npis > 1) AS conflict_days
    FROM daily_links l JOIN daily d ON l.source = d.source AND l.email = d.email AND l.observed_day = d.observed_day
    GROUP BY l.source, l.email, l.npi
), undated AS (
    SELECT source, email, bool_or(undated_observation_count > 0) AS has_undated
    FROM records GROUP BY source, email
)
SELECT r.source, count(*) AS failing_metric_rows
FROM records r
LEFT JOIN email_days e ON r.source = e.source AND r.email = e.email
LEFT JOIN link_days l ON r.source = l.source AND r.email = l.email AND r.npi = l.npi
JOIN undated u ON r.source = u.source AND r.email = u.email
WHERE r.email_observed_day_count IS DISTINCT FROM coalesce(e.email_days, cast(0 AS bigint))
   OR r.link_observed_day_count IS DISTINCT FROM coalesce(l.link_days, cast(0 AS bigint))
   OR r.link_conflict_day_count IS DISTINCT FROM coalesce(l.conflict_days, cast(0 AS bigint))
   OR r.link_presence_share IS DISTINCT FROM cast(l.link_days AS double) / nullif(e.email_days, 0)
   OR r.link_overlap_share IS DISTINCT FROM cast(l.conflict_days AS double) / nullif(l.link_days, 0)
   OR r.link_stability_has_undated_observations IS DISTINCT FROM u.has_undated
GROUP BY r.source

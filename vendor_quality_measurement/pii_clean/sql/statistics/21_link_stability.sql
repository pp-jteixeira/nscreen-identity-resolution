-- Each source/email/NPI contributes once. Mean percentages give each dated link equal weight.
WITH measured AS (SELECT * FROM iceberg.jteixeira_ipa.pii_clean), links AS (
    SELECT source, email, npi, email_observed_day_count, link_observed_day_count,
           link_conflict_day_count, link_presence_share, link_overlap_share,
           link_stability_has_undated_observations, count(*) AS metric_rows
    FROM measured
    GROUP BY source, email, npi, email_observed_day_count, link_observed_day_count,
             link_conflict_day_count, link_presence_share, link_overlap_share,
             link_stability_has_undated_observations
)
SELECT source, sum(metric_rows) AS metric_rows, count(*) AS distinct_links,
       count(link_presence_share) AS dated_links,
       count_if(link_presence_share IS NULL) AS undated_links,
       100e0 * count_if(link_presence_share IS NULL) / count(*) AS undated_link_pct,
       count_if(link_stability_has_undated_observations) AS links_with_incomplete_email_dates,
       100e0 * count_if(link_stability_has_undated_observations) / count(*) AS incomplete_email_date_link_pct,
       count_if(email_observed_day_count = 1) AS single_email_day_links,
       count_if(link_observed_day_count = 1) AS single_link_day_links,
       count_if(link_presence_share = 1) AS full_presence_links,
       count_if(link_presence_share < 1) AS partial_presence_links,
       100e0 * count_if(link_presence_share = 1) / nullif(count(link_presence_share), 0) AS full_presence_pct_of_dated_links,
       100e0 * avg(link_presence_share) AS mean_presence_pct_of_dated_links,
       count_if(link_overlap_share = 0) AS no_known_overlap_links,
       count_if(link_overlap_share > 0) AS links_with_overlap,
       count_if(link_overlap_share = 1) AS links_overlapping_every_observed_day,
       100e0 * count_if(link_overlap_share > 0) / nullif(count(link_overlap_share), 0) AS overlap_pct_of_dated_links,
       100e0 * avg(link_overlap_share) AS mean_overlap_pct_of_dated_links,
       max(email_observed_day_count) AS maximum_email_observed_days,
       max(link_observed_day_count) AS maximum_link_observed_days
FROM links GROUP BY source ORDER BY source

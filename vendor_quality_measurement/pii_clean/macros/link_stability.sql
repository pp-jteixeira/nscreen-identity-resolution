{% macro link_stability_records(input_relation, observation_relation=none) -%}
-- Count each source/email/NPI/day once, retaining undated links through the left unnest.
WITH observations AS (
    SELECT m.source, m.email, m.npi, d.observed_day,
           bool_or(coalesce(contains(m.conflict_days, d.observed_day), false)) AS has_overlap,
           bool_or(m.undated_observation_count > 0) AS has_undated
    FROM {{ observation_relation or input_relation }} m
    LEFT JOIN UNNEST(m.observed_days) AS d(observed_day) ON true
    GROUP BY m.source, m.email, m.npi, d.observed_day
), ranked_days AS (
    SELECT *, row_number() OVER (PARTITION BY source, email, observed_day ORDER BY npi) AS day_position
    FROM observations
), email_coverage AS (
    SELECT *, sum(CASE WHEN observed_day IS NOT NULL AND day_position = 1 THEN 1 ELSE 0 END)
                   OVER (PARTITION BY source, email) AS email_days,
           bool_or(has_undated) OVER (PARTITION BY source, email) AS email_has_undated
    FROM ranked_days
), link_counts AS (
    SELECT source, email, npi, max(email_days) AS email_observed_day_count,
           count(observed_day) AS link_observed_day_count,
           count_if(observed_day IS NOT NULL AND has_overlap) AS link_conflict_day_count,
           bool_or(email_has_undated) AS link_stability_has_undated_observations
    FROM email_coverage GROUP BY source, email, npi
)
SELECT m.*, c.email_observed_day_count, c.link_observed_day_count, c.link_conflict_day_count,
       CASE WHEN c.link_observed_day_count > 0 THEN cast(c.link_observed_day_count AS double)
            / nullif(c.email_observed_day_count, 0) END AS link_presence_share,
       cast(c.link_conflict_day_count AS double) / nullif(c.link_observed_day_count, 0) AS link_overlap_share,
       c.link_stability_has_undated_observations
FROM {{ input_relation }} m
LEFT JOIN link_counts c ON m.source = c.source AND m.email = c.email AND m.npi = c.npi
{%- endmacro %}

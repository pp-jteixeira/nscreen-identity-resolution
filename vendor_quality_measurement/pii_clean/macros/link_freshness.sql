{% macro link_freshness_records(input_relation, observation_relation=none) -%}
-- Aggregate narrow observation columns before joining the complete evidence rows.
WITH link_observations AS (
    SELECT source, email, npi, max(last_seen_day) AS link_last_observed_day
    FROM {{ observation_relation or input_relation }}
    GROUP BY source, email, npi
), latest_observations AS (
    SELECT *, {% if var('source_latest_observed_day', '') %}DATE '{{ var('source_latest_observed_day') }}'{% else %}max(link_last_observed_day) OVER (PARTITION BY source){% endif %} AS source_latest_observed_day,
           {% if var('link_freshness_as_of_day', '') %}DATE '{{ var('link_freshness_as_of_day') }}'{% else %}cast(current_timestamp AT TIME ZONE 'Europe/Paris' AS date){% endif %} AS link_freshness_as_of_day
    FROM link_observations
)
SELECT m.*, d.link_freshness_as_of_day, d.source_latest_observed_day, d.link_last_observed_day,
       CASE WHEN d.source_latest_observed_day <= d.link_freshness_as_of_day
            THEN date_diff('day', d.source_latest_observed_day, d.link_freshness_as_of_day) END AS source_age_days,
       CASE WHEN d.source_latest_observed_day <= d.link_freshness_as_of_day
                 AND d.link_last_observed_day <= d.link_freshness_as_of_day
            THEN date_diff('day', d.link_last_observed_day, d.source_latest_observed_day) END AS link_lag_days
FROM {{ input_relation }} m
LEFT JOIN latest_observations d ON m.source = d.source AND m.email = d.email AND m.npi = d.npi
{%- endmacro %}

{% macro sequence_day() -%}
{% if var('sequence_as_of_day', '') %}DATE '{{ var('sequence_as_of_day') }}'{% else %}cast(current_timestamp AT TIME ZONE 'Europe/Paris' AS date){% endif %}
{%- endmacro %}
{% macro sequence_evidence_type() -%}
array(row(observed_day date, previous_observed_day date, npis array(varchar), added_npis array(varchar), removed_npis array(varchar), returned_npis array(varchar), versions_observed bigint, npis_observed bigint, changes bigint, swaps bigint, flipbacks bigint, history_sufficient boolean))
{%- endmacro %}
{% macro sequential_history_records(input_relation, observation_relation='metric_records', vendor=none, undated_flag=none) -%}
-- Use eligible vendor observations only. Reference enrichments cannot create history.
WITH sequence_observations AS (
    SELECT DISTINCT m.source, m.email, m.npi, d.observed_day
    FROM {{ observation_relation }} m
    CROSS JOIN UNNEST(m.observed_days) AS d(observed_day)
    WHERE d.observed_day <= {{ sequence_day() }}
),
{% if vendor is none or vendor in ['healthlink', 'quantummedica'] %}
sequence_deliveries AS (
    -- Order-independent fingerprint of the eligible delivery's distinct email/NPI set.
    SELECT source, observed_day, checksum(ROW(email, npi)) AS fingerprint
    FROM sequence_observations GROUP BY source, observed_day
), sequence_delivery_steps AS (
    SELECT *, lag(fingerprint) OVER (PARTITION BY source ORDER BY observed_day) AS previous_fingerprint
    FROM sequence_deliveries
), sequence_days AS (
    SELECT source, observed_day,
           CASE WHEN source IN ('healthlink', 'quantummedica')
                THEN previous_fingerprint IS NULL OR fingerprint <> previous_fingerprint ELSE true END AS new_version
    FROM sequence_delivery_steps
),
{% endif %}
sequence_email_days AS (
    SELECT source, email, observed_day, array_sort(array_agg(npi)) AS npis
    FROM sequence_observations GROUP BY source, email, observed_day
), sequence_previous AS (
    -- This engine requires scalar reduce_agg state, so encode the compact NPI set as JSON.
    SELECT e.*, {% if vendor is none or vendor in ['healthlink', 'quantummedica'] %}d.new_version{% else %}true AS new_version{% endif %},
           lag(e.observed_day) OVER (PARTITION BY e.source, e.email ORDER BY e.observed_day) AS previous_observed_day,
           coalesce(CAST(json_parse(reduce_agg(e.npis, CAST('[]' AS varchar), (accumulated, incoming) -> json_format(CAST(array_union(CAST(json_parse(accumulated) AS array(varchar)), incoming) AS json)), (left_state, right_state) -> json_format(CAST(array_union(CAST(json_parse(left_state) AS array(varchar)), CAST(json_parse(right_state) AS array(varchar))) AS json))) OVER (PARTITION BY e.source, e.email ORDER BY e.observed_day ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING)) AS array(varchar)), CAST(ARRAY[] AS array(varchar))) AS past_npis,
           lag(e.npis) OVER (PARTITION BY e.source, e.email ORDER BY e.observed_day) AS previous_npis
    FROM sequence_email_days e
    {% if vendor is none or vendor in ['healthlink', 'quantummedica'] %}JOIN sequence_days d ON e.source = d.source AND e.observed_day = d.observed_day{% endif %}
), sequence_differences AS (
    SELECT *, cardinality(filter(npis, x -> NOT contains(past_npis, x))) AS new_npis,
           array_intersect(npis, past_npis) AS seen_npis,
           CASE WHEN previous_observed_day IS NULL THEN CAST(ARRAY[] AS array(varchar))
                   ELSE filter(npis, x -> NOT contains(previous_npis, x)) END AS added_npis,
           coalesce(filter(previous_npis, x -> NOT contains(npis, x)), CAST(ARRAY[] AS array(varchar))) AS removed_npis
    FROM sequence_previous
), sequence_transitions AS (
    SELECT *, array_intersect(added_npis, seen_npis) AS returned_npis,
           cardinality(added_npis) > 0 AND cardinality(removed_npis) > 0 AS is_swap
    FROM sequence_differences
), sequence_cumulative AS (
    SELECT *, count_if(new_version) OVER w AS versions_observed,
           sum(new_npis) OVER w AS npis_observed,
           count_if(cardinality(added_npis) > 0 OR cardinality(removed_npis) > 0) OVER w AS changes,
           count_if(is_swap) OVER w AS swaps,
           count_if(is_swap AND cardinality(returned_npis) > 0) OVER w AS flipbacks
    FROM sequence_transitions
    WINDOW w AS (PARTITION BY source, email ORDER BY observed_day ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)
), sequence_summary AS (
    SELECT source, email, max(versions_observed) AS n_versions_observed, max(npis_observed) AS n_npis_window,
           max(changes) AS n_npi_changes, max(swaps) AS n_swaps, max(flipbacks) AS n_flipbacks,
           array_agg(CAST(ROW(observed_day, previous_observed_day, npis, added_npis, removed_npis, returned_npis,
               versions_observed, npis_observed, changes, swaps, flipbacks,
               versions_observed >= {{ var('stability_min_versions', 3) }}) AS
               ROW(observed_day date, previous_observed_day date, npis array(varchar), added_npis array(varchar), removed_npis array(varchar), returned_npis array(varchar), versions_observed bigint, npis_observed bigint, changes bigint, swaps bigint, flipbacks bigint, history_sufficient boolean)) ORDER BY observed_day) AS sequence_daily_evidence
    FROM sequence_cumulative GROUP BY source, email
)
SELECT m.*, {{ sequence_day() }} AS sequence_as_of_day, 'sequence_v1' AS sequence_definition_version,
       CASE WHEN s.n_versions_observed IS NULL THEN 'no_dated_history'
            WHEN {{ undated_flag or 'bool_or(m.undated_observation_count > 0) OVER (PARTITION BY m.source, m.email)' }} THEN 'incomplete_dates' ELSE 'dated_history' END AS sequence_history_status,
       {{ undated_flag or 'bool_or(m.undated_observation_count > 0) OVER (PARTITION BY m.source, m.email)' }} AS sequence_has_undated_observations,
       cast({{ var('stability_min_versions', 3) }} AS bigint) AS sequence_min_versions,
       s.n_versions_observed, s.n_npis_window, s.n_npi_changes, s.n_swaps, s.n_flipbacks,
       coalesce(s.n_versions_observed >= {{ var('stability_min_versions', 3) }}, false) AS stability_history_sufficient,
       coalesce(s.sequence_daily_evidence, CAST(ARRAY[] AS {{ sequence_evidence_type() }})) AS sequence_daily_evidence
FROM {{ input_relation }} m
LEFT JOIN sequence_summary s ON m.source = s.source AND m.email = s.email
{%- endmacro %}
{% macro registration_supersession_records(input_relation, vendor, observation_relation='metric_records', inline=false) -%}
{% if vendor == 'medscape' %}
WITH registration_records AS (
    SELECT {% if inline %}r.*{% else %}source, email, npi, metric_row_id, observed_days, undated_observation_count{% endif %},
           {{ clean_text("json_extract_scalar(record_payload, '$.guid')") }} AS guid
    FROM {{ input_relation if inline else observation_relation }} r
), registration_windows AS (
    -- One registration history window. Repeated record variants cannot create extra events.
    SELECT r.*, array_distinct(array_agg(CAST(ROW(npi, filter(observed_days, d -> d <= {{ sequence_day() }}))
               AS ROW(npi varchar, days array(date)))) OVER (PARTITION BY source, email, guid)) AS history,
           bool_or(undated_observation_count > 0) OVER (PARTITION BY source, email, guid) AS has_undated
    FROM registration_records r
), registration_dates AS (
    SELECT r.*, element_at(array_sort(flatten(transform(history, h -> h.days))), -1) AS latest_day,
           element_at(array_sort(flatten(transform(filter(history, h -> h.npi = r.npi), h -> h.days))), -1) AS link_last_day
    FROM registration_windows r
), registration_context AS (
    SELECT r.*, array_sort(array_distinct(transform(filter(history, h -> contains(h.days, r.latest_day)), h -> h.npi))) AS latest_npis,
           element_at(array_sort(filter(flatten(transform(history, h -> h.days)), d -> d > r.link_last_day)), 1) AS replaced_since
    FROM registration_dates r
)
SELECT {% if inline %}{% for field in metric_columns() if not field.startswith('registration_') %}r.{{ field }},{% endfor %}{% else %}m.*,{% endif %}
       r.guid AS registration_guid,
       CAST(CASE WHEN r.guid IS NULL OR r.latest_day IS NULL OR r.link_last_day IS NULL OR r.has_undated THEN 'unknown'
            WHEN cardinality(r.latest_npis) <> 1 THEN 'ambiguous_latest'
            WHEN contains(r.latest_npis, r.npi) THEN 'latest_observed' ELSE 'superseded' END AS varchar) AS registration_link_status,
       CASE WHEN r.guid IS NOT NULL THEN r.latest_day END AS registration_latest_observed_day,
       CASE WHEN r.guid IS NOT NULL THEN r.latest_npis ELSE CAST(ARRAY[] AS array(varchar)) END AS registration_latest_npis,
       CASE WHEN r.guid IS NOT NULL THEN r.link_last_day END AS registration_link_last_observed_day,
       CASE WHEN r.guid IS NOT NULL AND NOT r.has_undated AND cardinality(r.latest_npis) = 1
                 AND NOT contains(r.latest_npis, r.npi) AND r.link_last_day IS NOT NULL THEN r.replaced_since END AS registration_superseded_since_day,
       CASE WHEN r.guid IS NOT NULL AND NOT r.has_undated AND cardinality(r.latest_npis) = 1
                 AND NOT contains(r.latest_npis, r.npi) AND r.link_last_day IS NOT NULL THEN r.latest_npis
            ELSE CAST(ARRAY[] AS array(varchar)) END AS registration_superseded_by_npis,
       'registration_v1' AS registration_supersession_definition_version
{% if inline %}
FROM registration_context r
{% else %}
FROM {{ input_relation }} m
JOIN registration_context r ON m.source = r.source AND m.metric_row_id = r.metric_row_id
{% endif %}
{% else %}
SELECT m.*, CAST(NULL AS varchar) AS registration_guid, CAST('not_applicable' AS varchar) AS registration_link_status,
       CAST(NULL AS date) AS registration_latest_observed_day, CAST(ARRAY[] AS array(varchar)) AS registration_latest_npis,
       CAST(NULL AS date) AS registration_link_last_observed_day, CAST(NULL AS date) AS registration_superseded_since_day,
       CAST(ARRAY[] AS array(varchar)) AS registration_superseded_by_npis,
       'registration_v1' AS registration_supersession_definition_version
FROM {{ input_relation }} m
{% endif %}
{%- endmacro %}

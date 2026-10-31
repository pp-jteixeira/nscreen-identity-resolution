-- Validate stored daily causal evidence and summary bounds without reading vendor views.
WITH records AS (SELECT * FROM {{ ref(var('metric_model')) }}), checked AS (
    SELECT *, element_at(sequence_daily_evidence, -1) AS last_step
    FROM records
)
SELECT source, count(*) AS failing_metric_rows
FROM checked
WHERE sequence_min_versions < 1
   OR stability_history_sufficient IS DISTINCT FROM coalesce(n_versions_observed >= sequence_min_versions, false)
   OR n_swaps > n_npi_changes OR n_flipbacks > n_swaps
   OR n_npi_changes > greatest(n_versions_observed - 1, 0)
   OR n_versions_observed IS DISTINCT FROM last_step.versions_observed
   OR n_npis_window IS DISTINCT FROM last_step.npis_observed
   OR n_npi_changes IS DISTINCT FROM last_step.changes
   OR n_swaps IS DISTINCT FROM last_step.swaps
   OR n_flipbacks IS DISTINCT FROM last_step.flipbacks
   OR (n_versions_observed IS NULL AND (sequence_history_status <> 'no_dated_history' OR cardinality(sequence_daily_evidence) <> 0))
   OR any_match(sequence_daily_evidence, s -> s.observed_day > sequence_as_of_day
        OR s.previous_observed_day >= s.observed_day
        OR s.flipbacks > s.swaps OR s.swaps > s.changes
        OR s.history_sufficient IS DISTINCT FROM (s.versions_observed >= sequence_min_versions)
        OR cardinality(filter(s.returned_npis, n -> NOT contains(s.added_npis, n))) > 0)
   OR registration_latest_observed_day > sequence_as_of_day
   OR registration_link_last_observed_day > registration_latest_observed_day
   OR (registration_link_status = 'superseded' AND (source <> 'medscape' OR registration_guid IS NULL
       OR cardinality(registration_latest_npis) <> 1 OR contains(registration_latest_npis, npi)
       OR registration_link_last_observed_day IS NULL OR registration_superseded_since_day IS NULL
       OR registration_superseded_since_day <= registration_link_last_observed_day
       OR registration_superseded_since_day > registration_latest_observed_day
       OR registration_superseded_by_npis IS DISTINCT FROM registration_latest_npis))
   OR (registration_link_status <> 'superseded' AND (registration_superseded_since_day IS NOT NULL
       OR cardinality(registration_superseded_by_npis) <> 0))
   OR (registration_link_status = 'latest_observed' AND (cardinality(registration_latest_npis) <> 1
       OR NOT contains(registration_latest_npis, npi)))
   OR (registration_link_status = 'ambiguous_latest' AND cardinality(registration_latest_npis) < 2)
   OR (source <> 'medscape' AND registration_link_status <> 'not_applicable')
GROUP BY source

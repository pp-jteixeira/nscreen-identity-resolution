-- Complete read-only lookup. Edit the email in params once.
-- Stored metrics come from pii_clean; unpublished evidence is computed below.
WITH params AS (
    SELECT lower(trim('person@example.com')) AS input_email
), saved_records AS (
    SELECT t.source, t.email, t.npi, t.first_seen_day, t.last_seen_day, t.observed_day_count, t.observation_count, t.undated_observation_count, t.invalid_day_observation_count, t.source_tables, t.source_feeds, t.computed_at, t.definition_version, t.email_format_valid, t.email_role_account, t.email_domain_class, t.email_matches_source_name, t.email_matches_registry_name, t.vendor_name_matches_registry_name, t.source_name_usable, t.registry_name_usable, t.registry_npi_present, t.record_id, t.metric_row_id, t.email_ordinal, t.email_origin, t.record_payload, t.email_npi_count, t.email_has_multiple_npis, t.has_been_reassigned, t.has_conflict_linkage, t.observed_days, t.conflict_days, t.source_name_values, t.source_state_values, t.email_name_count, t.email_npi_has_name_conflict, t.conflicting_npis_share_name, t.conflicting_npi_name_comparisons, t.conflicting_npis_share_state, t.conflicting_npi_state_comparisons
    FROM iceberg.jteixeira_ipa.pii_clean t
    WHERE lower(trim(t.email)) = (SELECT input_email FROM params)
), facilities AS (
    WITH facility_reference AS (SELECT trim(provider_npi) AS npi,
       array_sort(array_distinct(filter(
           transform(flatten(array_agg(coalesce(facility_npis, CAST(ARRAY[] AS array(varchar))))),
                     f -> trim(f)),
           f -> regexp_like(f, '^[0-9]{10}$') AND f <> '0000000000'
       ))) AS facility_npi_values
FROM bq_bi.analytics_prod.npi_facility_association
WHERE nullif(trim(provider_npi), '') IS NOT NULL
GROUP BY trim(provider_npi))
SELECT m.*, coalesce(f.facility_npi_values, CAST(ARRAY[] AS array(varchar))) AS facility_npi_values,
       CAST('bq_bi.analytics_prod.npi_facility_association' AS varchar) AS facility_reference_table,
       CAST('all_ranked_facility_npis_v1' AS varchar) AS facility_definition_version
FROM saved_records m LEFT JOIN facility_reference f ON m.npi = f.npi
), specialties AS (
    WITH specialty_reference AS (WITH dictionary AS (
    SELECT DISTINCT upper(trim(code)) AS code
    FROM iceberg.npi.npi_taxonomy
    WHERE regexp_like(upper(trim(code)), '^[0-9A-Z]{10}$')
), provider_codes AS (
    SELECT trim(cast(p.npi AS varchar)) AS npi, upper(trim(u.code)) AS code
    FROM iceberg.npi.nppes_npidata_latest p
    CROSS JOIN UNNEST(ARRAY[
    p.healthcare_provider_taxonomy_code_1, p.healthcare_provider_taxonomy_code_2, p.healthcare_provider_taxonomy_code_3, p.healthcare_provider_taxonomy_code_4, p.healthcare_provider_taxonomy_code_5, p.healthcare_provider_taxonomy_code_6, p.healthcare_provider_taxonomy_code_7, p.healthcare_provider_taxonomy_code_8, p.healthcare_provider_taxonomy_code_9, p.healthcare_provider_taxonomy_code_10, p.healthcare_provider_taxonomy_code_11, p.healthcare_provider_taxonomy_code_12, p.healthcare_provider_taxonomy_code_13, p.healthcare_provider_taxonomy_code_14, p.healthcare_provider_taxonomy_code_15
    ]) AS u(code)
    WHERE nullif(trim(cast(p.npi AS varchar)), '') IS NOT NULL
)
SELECT p.npi, array_sort(array_agg(DISTINCT p.code)) AS specialty_code_values
FROM provider_codes p JOIN dictionary d ON p.code = d.code
GROUP BY p.npi)
SELECT m.*, coalesce(f.specialty_code_values, CAST(ARRAY[] AS array(varchar))) AS specialty_code_values,
       CAST('iceberg.npi.nppes_npidata_latest' AS varchar) AS specialty_reference_table,
       CAST('recognized_exact_taxonomy_all_slots_v1' AS varchar) AS specialty_definition_version
FROM facilities m LEFT JOIN specialty_reference f ON m.npi = f.npi
), relationships AS (
    -- Filtering retains every source/NPI/record for this email, so all peer
    -- contexts and within-email history remain available to the same rules.
    WITH name_sets AS (
    SELECT source, email, npi, first_seen_day, last_seen_day, observed_day_count, observation_count, undated_observation_count, invalid_day_observation_count, source_tables, source_feeds, computed_at, definition_version, email_format_valid, email_role_account, email_domain_class, email_matches_source_name, email_matches_registry_name, vendor_name_matches_registry_name, source_name_usable, registry_name_usable, registry_npi_present, record_id, metric_row_id, email_ordinal, email_origin, record_payload, email_npi_count, email_has_multiple_npis, has_been_reassigned, has_conflict_linkage, observed_days, conflict_days, source_name_values, source_state_values,
           facility_npi_values, facility_reference_table, facility_definition_version,
           array_sort(array_distinct(filter(array_agg(
        CASE WHEN has_conflict_linkage THEN
            CAST(ROW(npi, conflict_days, facility_npi_values)
                 AS ROW(npi varchar, days array(date), facilities array(varchar))) END
        ) OVER (PARTITION BY source, email), x -> x IS NOT NULL))) AS facility_conflict_records,
           specialty_code_values, specialty_reference_table, specialty_definition_version,
           array_sort(array_distinct(filter(array_agg(
        CASE WHEN has_conflict_linkage THEN
            CAST(ROW(npi, conflict_days, specialty_code_values)
                 AS ROW(npi varchar, days array(date), specialties array(varchar))) END
        ) OVER (PARTITION BY source, email), x -> x IS NOT NULL))) AS specialty_conflict_records,
           array_distinct(flatten(array_agg(source_name_values) OVER (PARTITION BY source, email))) AS email_names,
           array_distinct(flatten(array_agg(source_name_values) OVER (PARTITION BY source, email, npi))) AS pair_names,
           -- Collect only conflicting records; keep their dates and names paired.
           array_sort(array_distinct(filter(
               array_agg(CASE WHEN has_conflict_linkage THEN
                   CAST(ROW(npi, conflict_days, source_name_values) AS
                       ROW(npi varchar, days array(date), names array(row(first_name varchar, last_name varchar, first_variants array(varchar)))))
                   END) OVER (PARTITION BY source, email), x -> x IS NOT NULL
           ))) AS conflict_records,
           array_sort(array_distinct(filter(array_agg(
               CASE WHEN has_conflict_linkage THEN CAST(ROW(npi, conflict_days, source_state_values)
                   AS ROW(npi varchar, days array(date), states array(varchar))) END
               ) OVER (PARTITION BY source, email), x -> x IS NOT NULL))) AS conflict_state_records
    FROM specialties
), peer_comparisons AS (
    SELECT *, transform(filter(facility_conflict_records, peer ->
               has_conflict_linkage AND peer.npi <> npi
               AND (source IN ('endato', 'rocketreach', 'drdb') OR arrays_overlap(conflict_days, peer.days))),
               peer -> CAST(ROW(peer.npi, array_sort(array_intersect(conflict_days, peer.days)), peer.facilities,
                   array_sort(array_intersect(facility_npi_values, peer.facilities)),
                   CASE WHEN cardinality(facility_npi_values) > 0 AND cardinality(peer.facilities) > 0
                        THEN arrays_overlap(facility_npi_values, peer.facilities) END)
                   AS ROW(npi varchar, conflict_days array(date), facility_npis array(varchar),
                          shared_facility_npis array(varchar), shares_facility boolean))) AS conflicting_npi_facility_comparisons,
           transform(filter(specialty_conflict_records, peer ->
               has_conflict_linkage AND peer.npi <> npi
               AND (source IN ('endato', 'rocketreach', 'drdb') OR arrays_overlap(conflict_days, peer.days))),
               peer -> CAST(ROW(peer.npi, array_sort(array_intersect(conflict_days, peer.days)), peer.specialties,
                   array_sort(array_intersect(specialty_code_values, peer.specialties)),
                   CASE WHEN cardinality(specialty_code_values) > 0 AND cardinality(peer.specialties) > 0
                        THEN arrays_overlap(specialty_code_values, peer.specialties) END)
                   AS ROW(npi varchar, conflict_days array(date), specialty_codes array(varchar),
                          shared_specialty_codes array(varchar), shares_specialty boolean))) AS conflicting_npi_specialty_comparisons,
           transform(filter(conflict_records, peer ->
               has_conflict_linkage AND peer.npi <> npi
               AND (source IN ('endato', 'rocketreach', 'drdb')
                    OR arrays_overlap(conflict_days, peer.days))), peer ->
           CAST(ROW(peer.npi, array_sort(array_intersect(conflict_days, peer.days)), peer.names,
               CASE WHEN cardinality(source_name_values) > 0 AND cardinality(peer.names) > 0
                    THEN any_match(source_name_values, own_name -> any_match(peer.names, peer_name -> NOT (case
        when regexp_replace(own_name.last_name, '[^A-Z]', '') = regexp_replace(peer_name.last_name, '[^A-Z]', '') then 'exact'
        when arrays_overlap(split(regexp_replace(own_name.last_name, '[- ]+', ' '), ' '), split(regexp_replace(peer_name.last_name, '[- ]+', ' '), ' ')) then 'token'
        when (
        (least(length(regexp_replace(own_name.last_name, '[^A-Z]', '')), length(regexp_replace(peer_name.last_name, '[^A-Z]', ''))) >= 5 and levenshtein_distance(regexp_replace(own_name.last_name, '[^A-Z]', ''), regexp_replace(peer_name.last_name, '[^A-Z]', '')) <= 1)
        or (least(length(regexp_replace(own_name.last_name, '[^A-Z]', '')), length(regexp_replace(peer_name.last_name, '[^A-Z]', ''))) >= 8 and levenshtein_distance(regexp_replace(own_name.last_name, '[^A-Z]', ''), regexp_replace(peer_name.last_name, '[^A-Z]', '')) <= 2)
    ) then 'edit'
        else 'none'
    end = 'none'
 OR case
        when own_name.first_name = peer_name.first_name then 'exact'
        when split_part(own_name.first_name, ' ', 1) = split_part(peer_name.first_name, ' ', 1)
            or arrays_overlap(split(own_name.first_name, ' '), split(peer_name.first_name, ' '))
            or (
        least(length(split_part(own_name.first_name, ' ', 1)), length(split_part(peer_name.first_name, ' ', 1))) >= 3
        and (substr(split_part(own_name.first_name, ' ', 1), 1, length(split_part(peer_name.first_name, ' ', 1))) = split_part(peer_name.first_name, ' ', 1) or substr(split_part(peer_name.first_name, ' ', 1), 1, length(split_part(own_name.first_name, ' ', 1))) = split_part(own_name.first_name, ' ', 1))
    ) then 'token'
        when arrays_overlap(own_name.first_variants, peer_name.first_variants) then 'nickname'
        when (
        (least(length(regexp_replace(split_part(own_name.first_name, ' ', 1), '[^A-Z]', '')), length(regexp_replace(split_part(peer_name.first_name, ' ', 1), '[^A-Z]', ''))) >= 5 and levenshtein_distance(regexp_replace(split_part(own_name.first_name, ' ', 1), '[^A-Z]', ''), regexp_replace(split_part(peer_name.first_name, ' ', 1), '[^A-Z]', '')) <= 1)
        or (least(length(regexp_replace(split_part(own_name.first_name, ' ', 1), '[^A-Z]', '')), length(regexp_replace(split_part(peer_name.first_name, ' ', 1), '[^A-Z]', ''))) >= 8 and levenshtein_distance(regexp_replace(split_part(own_name.first_name, ' ', 1), '[^A-Z]', ''), regexp_replace(split_part(peer_name.first_name, ' ', 1), '[^A-Z]', '')) <= 2)
    ) then 'edit'
        else 'none'
    end = 'none')))
               END) AS ROW(npi varchar, conflict_days array(date), names array(row(first_name varchar, last_name varchar, first_variants array(varchar))), shares_name boolean)))
           AS conflicting_npi_name_comparisons,
           transform(filter(conflict_state_records, peer -> has_conflict_linkage AND peer.npi <> npi
               AND (source IN ('endato', 'rocketreach', 'drdb') OR arrays_overlap(conflict_days, peer.days))),
               peer -> CAST(ROW(peer.npi, array_sort(array_intersect(conflict_days, peer.days)), peer.states,
                   CASE WHEN cardinality(source_state_values) > 0 AND cardinality(peer.states) > 0
                        THEN arrays_overlap(source_state_values, peer.states) END)
                   AS ROW(npi varchar, conflict_days array(date), states array(varchar), shares_state boolean)))
               AS conflicting_npi_state_comparisons
    FROM name_sets
)
SELECT s.source, s.email, s.npi, s.first_seen_day, s.last_seen_day, s.observed_day_count, s.observation_count, s.undated_observation_count, s.invalid_day_observation_count, s.source_tables, s.source_feeds, s.computed_at, s.definition_version, s.email_format_valid, s.email_role_account, s.email_domain_class, s.email_matches_source_name, s.email_matches_registry_name, s.vendor_name_matches_registry_name, s.source_name_usable, s.registry_name_usable, s.registry_npi_present, s.record_id, s.metric_row_id, s.email_ordinal, s.email_origin, s.record_payload, s.email_npi_count, s.email_has_multiple_npis, s.has_been_reassigned, s.has_conflict_linkage, s.observed_days, s.conflict_days, s.source_name_values, s.source_state_values,
       CAST(cardinality(array_distinct(transform(email_names, x -> ROW(x.first_name, x.last_name)))) AS bigint) AS email_name_count,
       CASE WHEN cardinality(pair_names) = 0 THEN CAST(NULL AS boolean)
            ELSE any_match(pair_names, a -> any_match(pair_names, b -> (case
        when regexp_replace(a.last_name, '[^A-Z]', '') = regexp_replace(b.last_name, '[^A-Z]', '') then 'exact'
        when arrays_overlap(split(regexp_replace(a.last_name, '[- ]+', ' '), ' '), split(regexp_replace(b.last_name, '[- ]+', ' '), ' ')) then 'token'
        when (
        (least(length(regexp_replace(a.last_name, '[^A-Z]', '')), length(regexp_replace(b.last_name, '[^A-Z]', ''))) >= 5 and levenshtein_distance(regexp_replace(a.last_name, '[^A-Z]', ''), regexp_replace(b.last_name, '[^A-Z]', '')) <= 1)
        or (least(length(regexp_replace(a.last_name, '[^A-Z]', '')), length(regexp_replace(b.last_name, '[^A-Z]', ''))) >= 8 and levenshtein_distance(regexp_replace(a.last_name, '[^A-Z]', ''), regexp_replace(b.last_name, '[^A-Z]', '')) <= 2)
    ) then 'edit'
        else 'none'
    end = 'none'
 OR case
        when a.first_name = b.first_name then 'exact'
        when split_part(a.first_name, ' ', 1) = split_part(b.first_name, ' ', 1)
            or arrays_overlap(split(a.first_name, ' '), split(b.first_name, ' '))
            or (
        least(length(split_part(a.first_name, ' ', 1)), length(split_part(b.first_name, ' ', 1))) >= 3
        and (substr(split_part(a.first_name, ' ', 1), 1, length(split_part(b.first_name, ' ', 1))) = split_part(b.first_name, ' ', 1) or substr(split_part(b.first_name, ' ', 1), 1, length(split_part(a.first_name, ' ', 1))) = split_part(a.first_name, ' ', 1))
    ) then 'token'
        when arrays_overlap(a.first_variants, b.first_variants) then 'nickname'
        when (
        (least(length(regexp_replace(split_part(a.first_name, ' ', 1), '[^A-Z]', '')), length(regexp_replace(split_part(b.first_name, ' ', 1), '[^A-Z]', ''))) >= 5 and levenshtein_distance(regexp_replace(split_part(a.first_name, ' ', 1), '[^A-Z]', ''), regexp_replace(split_part(b.first_name, ' ', 1), '[^A-Z]', '')) <= 1)
        or (least(length(regexp_replace(split_part(a.first_name, ' ', 1), '[^A-Z]', '')), length(regexp_replace(split_part(b.first_name, ' ', 1), '[^A-Z]', ''))) >= 8 and levenshtein_distance(regexp_replace(split_part(a.first_name, ' ', 1), '[^A-Z]', ''), regexp_replace(split_part(b.first_name, ' ', 1), '[^A-Z]', '')) <= 2)
    ) then 'edit'
        else 'none'
    end = 'none')))
       END AS email_npi_has_name_conflict,
       -- any_match preserves unknown comparisons unless another peer matches.
       CASE WHEN has_conflict_linkage AND cardinality(conflicting_npi_name_comparisons) > 0
            THEN any_match(conflicting_npi_name_comparisons, comparison -> comparison.shares_name)
       END AS conflicting_npis_share_name,
       conflicting_npi_name_comparisons,
       CASE WHEN has_conflict_linkage AND cardinality(conflicting_npi_state_comparisons) > 0
            THEN any_match(conflicting_npi_state_comparisons, p -> p.shares_state)
       END AS conflicting_npis_share_state,
       conflicting_npi_state_comparisons
       , facility_npi_values, facility_reference_table, facility_definition_version,
       CASE WHEN has_conflict_linkage AND cardinality(conflicting_npi_facility_comparisons) > 0
            THEN any_match(conflicting_npi_facility_comparisons, p -> p.shares_facility)
       END AS conflicting_npis_share_facility,
       conflicting_npi_facility_comparisons
       , specialty_code_values, specialty_reference_table, specialty_definition_version,
       CASE WHEN has_conflict_linkage AND cardinality(conflicting_npi_specialty_comparisons) > 0
            THEN any_match(conflicting_npi_specialty_comparisons, p -> p.shares_specialty)
       END AS conflicting_npis_share_specialty,
       conflicting_npi_specialty_comparisons
FROM peer_comparisons s
), lifecycle AS (
    WITH lifecycle_reference AS (WITH lifecycle_rows AS (
    SELECT trim(cast(npi AS varchar)) AS npi,
           cast(npi_deactivation_date AS varchar) AS d,
           cast(npi_reactivation_date AS varchar) AS r,
           cast(replacement_npi AS varchar) AS replacement,
           cast(npi_deactivation_reason_code AS varchar) AS reason
    FROM iceberg.npi.nppes_npidata_latest
    WHERE npi IS NOT NULL
), grouped AS (
    SELECT npi, count(*) AS reference_row_count,
           -- Sort by serialized text: Trino cannot order ROW values with null fields.
           array_distinct(array_agg(CAST(ROW(d, r, replacement, reason)
               AS row(deactivation_date varchar, reactivation_date varchar, replacement_npi varchar, deactivation_reason varchar))
               ORDER BY json_format(cast(ROW(d, r, replacement, reason) AS json)))) AS evidence,
           array_distinct(array_agg(CAST(ROW(nullif(trim(d), ''), nullif(trim(r), ''),
               nullif(trim(replacement), ''), nullif(trim(reason), ''))
               AS row(d varchar, r varchar, replacement varchar, reason varchar)))) AS variants
    FROM lifecycle_rows GROUP BY npi
), parsed AS (
    SELECT *, cardinality(variants) AS variant_count,
           element_at(variants, 1) AS v,
           try_cast(element_at(variants, 1).d AS date) AS deactivation_day,
           try_cast(element_at(variants, 1).r AS date) AS reactivation_day,
           cast(current_timestamp AT TIME ZONE 'Europe/Paris' AS date) AS status_day
    FROM grouped
), classified AS (
    SELECT *, CASE
        WHEN variant_count <> 1 THEN 'conflicting_reference_records'
        WHEN (v.d IS NOT NULL AND deactivation_day IS NULL)
          OR (v.r IS NOT NULL AND reactivation_day IS NULL) THEN 'invalid_lifecycle_date'
        WHEN deactivation_day > status_day OR reactivation_day > status_day THEN 'future_lifecycle_date'
        WHEN v.replacement = npi THEN 'self_replacement'
        WHEN v.replacement IS NOT NULL AND
             (NOT regexp_like(v.replacement, '^[0-9]{10}$') OR v.replacement = '0000000000') THEN 'invalid_replacement_npi'
        WHEN v.reason IS NOT NULL AND deactivation_day IS NULL THEN 'reason_without_deactivation'
        WHEN deactivation_day = reactivation_day THEN 'ambiguous_event_order'
        WHEN v.replacement IS NOT NULL AND reactivation_day IS NOT NULL
             AND (deactivation_day IS NULL OR reactivation_day > deactivation_day) THEN 'replacement_with_reactivation'
        WHEN v.replacement IS NOT NULL THEN 'replacement_reported'
        WHEN deactivation_day IS NOT NULL AND
             (reactivation_day IS NULL OR deactivation_day > reactivation_day) THEN 'latest_event_deactivation'
        WHEN reactivation_day IS NOT NULL THEN 'latest_event_reactivation'
        ELSE 'no_deactivation_reported' END AS status_reason
    FROM parsed
)
SELECT npi,
       CASE status_reason WHEN 'replacement_reported' THEN 'replaced'
           WHEN 'latest_event_deactivation' THEN 'deactivated'
           WHEN 'latest_event_reactivation' THEN 'reactivated'
           WHEN 'no_deactivation_reported' THEN 'active_as_reported'
           ELSE 'unknown' END AS npi_registry_status,
       status_reason AS npi_registry_status_reason,
       CASE WHEN variant_count = 1 AND regexp_like(v.replacement, '^[0-9]{10}$')
                 AND v.replacement <> '0000000000' AND v.replacement <> npi
            THEN v.replacement END AS npi_registry_replacement_npi,
       CASE WHEN variant_count = 1 THEN deactivation_day END AS npi_registry_deactivation_date,
       CASE WHEN variant_count = 1 THEN reactivation_day END AS npi_registry_reactivation_date,
       reference_row_count AS npi_registry_reference_row_count,
       cast(variant_count AS bigint) AS npi_registry_variant_count,
       evidence AS npi_registry_lifecycle_evidence
FROM classified)
SELECT m.*,
       coalesce(r.npi_registry_status, 'not_found') AS npi_registry_status,
       coalesce(r.npi_registry_status_reason, 'no_nppes_record') AS npi_registry_status_reason,
       r.npi_registry_replacement_npi, r.npi_registry_deactivation_date, r.npi_registry_reactivation_date,
       coalesce(r.npi_registry_reference_row_count, cast(0 AS bigint)) AS npi_registry_reference_row_count,
       coalesce(r.npi_registry_variant_count, cast(0 AS bigint)) AS npi_registry_variant_count,
       coalesce(r.npi_registry_lifecycle_evidence, cast(ARRAY[] AS array(row(deactivation_date varchar, reactivation_date varchar, replacement_npi varchar, deactivation_reason varchar)))) AS npi_registry_lifecycle_evidence,
       cast(current_timestamp AT TIME ZONE 'Europe/Paris' AS date) AS npi_registry_status_as_of_day,
       'iceberg.npi.nppes_npidata_latest' AS npi_registry_reference_table,
       'nppes_lifecycle_consensus_v1' AS npi_registry_definition_version
FROM relationships m LEFT JOIN lifecycle_reference r ON m.npi = r.npi
), facility_states AS (
    WITH facility_reference AS (WITH normalized AS (
    SELECT trim(cast(npi_facility_provider_npi AS varchar)) AS npi,
           CASE upper(regexp_replace(trim(cast(state_code AS varchar)), '\s+', ' '))
    WHEN 'AL' THEN 'AL' WHEN 'ALABAMA' THEN 'AL'
    WHEN 'AK' THEN 'AK' WHEN 'ALASKA' THEN 'AK'
    WHEN 'AZ' THEN 'AZ' WHEN 'ARIZONA' THEN 'AZ'
    WHEN 'AR' THEN 'AR' WHEN 'ARKANSAS' THEN 'AR'
    WHEN 'CA' THEN 'CA' WHEN 'CALIFORNIA' THEN 'CA'
    WHEN 'CO' THEN 'CO' WHEN 'COLORADO' THEN 'CO'
    WHEN 'CT' THEN 'CT' WHEN 'CONNECTICUT' THEN 'CT'
    WHEN 'DE' THEN 'DE' WHEN 'DELAWARE' THEN 'DE'
    WHEN 'DC' THEN 'DC' WHEN 'DISTRICT OF COLUMBIA' THEN 'DC'
    WHEN 'FL' THEN 'FL' WHEN 'FLORIDA' THEN 'FL'
    WHEN 'GA' THEN 'GA' WHEN 'GEORGIA' THEN 'GA'
    WHEN 'HI' THEN 'HI' WHEN 'HAWAII' THEN 'HI'
    WHEN 'ID' THEN 'ID' WHEN 'IDAHO' THEN 'ID'
    WHEN 'IL' THEN 'IL' WHEN 'ILLINOIS' THEN 'IL'
    WHEN 'IN' THEN 'IN' WHEN 'INDIANA' THEN 'IN'
    WHEN 'IA' THEN 'IA' WHEN 'IOWA' THEN 'IA'
    WHEN 'KS' THEN 'KS' WHEN 'KANSAS' THEN 'KS'
    WHEN 'KY' THEN 'KY' WHEN 'KENTUCKY' THEN 'KY'
    WHEN 'LA' THEN 'LA' WHEN 'LOUISIANA' THEN 'LA'
    WHEN 'ME' THEN 'ME' WHEN 'MAINE' THEN 'ME'
    WHEN 'MD' THEN 'MD' WHEN 'MARYLAND' THEN 'MD'
    WHEN 'MA' THEN 'MA' WHEN 'MASSACHUSETTS' THEN 'MA'
    WHEN 'MI' THEN 'MI' WHEN 'MICHIGAN' THEN 'MI'
    WHEN 'MN' THEN 'MN' WHEN 'MINNESOTA' THEN 'MN'
    WHEN 'MS' THEN 'MS' WHEN 'MISSISSIPPI' THEN 'MS'
    WHEN 'MO' THEN 'MO' WHEN 'MISSOURI' THEN 'MO'
    WHEN 'MT' THEN 'MT' WHEN 'MONTANA' THEN 'MT'
    WHEN 'NE' THEN 'NE' WHEN 'NEBRASKA' THEN 'NE'
    WHEN 'NV' THEN 'NV' WHEN 'NEVADA' THEN 'NV'
    WHEN 'NH' THEN 'NH' WHEN 'NEW HAMPSHIRE' THEN 'NH'
    WHEN 'NJ' THEN 'NJ' WHEN 'NEW JERSEY' THEN 'NJ'
    WHEN 'NM' THEN 'NM' WHEN 'NEW MEXICO' THEN 'NM'
    WHEN 'NY' THEN 'NY' WHEN 'NEW YORK' THEN 'NY'
    WHEN 'NC' THEN 'NC' WHEN 'NORTH CAROLINA' THEN 'NC'
    WHEN 'ND' THEN 'ND' WHEN 'NORTH DAKOTA' THEN 'ND'
    WHEN 'OH' THEN 'OH' WHEN 'OHIO' THEN 'OH'
    WHEN 'OK' THEN 'OK' WHEN 'OKLAHOMA' THEN 'OK'
    WHEN 'OR' THEN 'OR' WHEN 'OREGON' THEN 'OR'
    WHEN 'PA' THEN 'PA' WHEN 'PENNSYLVANIA' THEN 'PA'
    WHEN 'RI' THEN 'RI' WHEN 'RHODE ISLAND' THEN 'RI'
    WHEN 'SC' THEN 'SC' WHEN 'SOUTH CAROLINA' THEN 'SC'
    WHEN 'SD' THEN 'SD' WHEN 'SOUTH DAKOTA' THEN 'SD'
    WHEN 'TN' THEN 'TN' WHEN 'TENNESSEE' THEN 'TN'
    WHEN 'TX' THEN 'TX' WHEN 'TEXAS' THEN 'TX'
    WHEN 'UT' THEN 'UT' WHEN 'UTAH' THEN 'UT'
    WHEN 'VT' THEN 'VT' WHEN 'VERMONT' THEN 'VT'
    WHEN 'VA' THEN 'VA' WHEN 'VIRGINIA' THEN 'VA'
    WHEN 'WA' THEN 'WA' WHEN 'WASHINGTON' THEN 'WA'
    WHEN 'WV' THEN 'WV' WHEN 'WEST VIRGINIA' THEN 'WV'
    WHEN 'WI' THEN 'WI' WHEN 'WISCONSIN' THEN 'WI'
    WHEN 'WY' THEN 'WY' WHEN 'WYOMING' THEN 'WY'
    WHEN 'AS' THEN 'AS' WHEN 'AMERICAN SAMOA' THEN 'AS'
    WHEN 'GU' THEN 'GU' WHEN 'GUAM' THEN 'GU'
    WHEN 'MP' THEN 'MP' WHEN 'NORTHERN MARIANA ISLANDS' THEN 'MP'
    WHEN 'PR' THEN 'PR' WHEN 'PUERTO RICO' THEN 'PR'
    WHEN 'VI' THEN 'VI' WHEN 'US VIRGIN ISLANDS' THEN 'VI'
    WHEN 'U.S. VIRGIN ISLANDS' THEN 'VI' WHEN 'VIRGIN ISLANDS' THEN 'VI'
END AS state,
           nullif(trim(cast(location AS varchar)), '') AS location
    FROM bq_bi.analytics_prod.npi_facility_locations_with_ids
    WHERE npi_facility_rank = 1
), grouped AS (
    SELECT npi, count(*) AS facility_rank1_rows,
           count(DISTINCT state) AS facility_rank1_state_count,
           count_if(state IS NULL) AS facility_rank1_unknown_state_rows,
           count_if(location IS NULL) AS facility_rank1_missing_location_rows,
           max(state) AS candidate_state
    FROM normalized WHERE nullif(npi, '') IS NOT NULL GROUP BY npi
)
SELECT npi, facility_rank1_rows, facility_rank1_state_count,
       facility_rank1_unknown_state_rows, facility_rank1_missing_location_rows,
       CASE WHEN facility_rank1_state_count = 1 AND facility_rank1_unknown_state_rows = 0
                  AND facility_rank1_missing_location_rows = 0 THEN candidate_state END AS facility_primary_state,
       CASE WHEN facility_rank1_state_count > 1 THEN 'ambiguous_state'
            WHEN facility_rank1_missing_location_rows > 0 THEN 'missing_location'
            WHEN facility_rank1_unknown_state_rows > 0 THEN 'missing_state'
            ELSE 'usable' END AS facility_reference_status
FROM grouped), enriched AS (
    SELECT m.*, r.facility_primary_state,
           coalesce(r.facility_reference_status, 'no_rank1_association') AS facility_reference_status,
           coalesce(r.facility_rank1_rows, cast(0 AS bigint)) AS facility_rank1_rows,
           coalesce(r.facility_rank1_state_count, cast(0 AS bigint)) AS facility_rank1_state_count,
           coalesce(r.facility_rank1_unknown_state_rows, cast(0 AS bigint)) AS facility_rank1_unknown_state_rows,
           coalesce(r.facility_rank1_missing_location_rows, cast(0 AS bigint)) AS facility_rank1_missing_location_rows
    FROM lifecycle m LEFT JOIN facility_reference r ON m.npi = r.npi
), compared AS (
    SELECT *, CASE WHEN facility_reference_status <> 'usable' THEN 'unknown_facility'
     WHEN cardinality(source_state_values) = 0 THEN 'unknown_vendor_state'
     WHEN contains(source_state_values, facility_primary_state)
          THEN CASE WHEN cardinality(source_state_values) = 1 THEN 'corroborated' ELSE 'mixed_vendor_states' END
     ELSE 'not_corroborated' END AS vendor_state_evidence FROM enriched
)
SELECT *, CASE vendor_state_evidence WHEN 'corroborated' THEN true WHEN 'not_corroborated' THEN false END
              AS vendor_state_corroborated,
       cast(current_timestamp AT TIME ZONE 'Europe/Paris' AS date) AS location_evaluation_day,
       'bq_bi.analytics_prod.npi_facility_locations_with_ids' AS location_reference_table,
       'record_vendor_facility_state_v1' AS location_evidence_version
FROM compared
), enriched AS (
    WITH email_evidence AS (WITH population AS (
    SELECT DISTINCT lower(to_hex(sha256(to_utf8(lower(trim(email)))))) AS email_hash FROM facility_states
), tokens AS (
    SELECT lower(trim(s.hashedemail_sha256)) AS email_hash, try_cast(s.day AS date) AS mapping_day,
           split(trim(t.token), ':') AS parts
    FROM iceberg.thirdparty.liveintent_idsync s
    JOIN population p ON lower(trim(s.hashedemail_sha256)) = p.email_hash
    CROSS JOIN UNNEST(split(coalesce(s.uids, ''), '|')) AS t(token)
    WHERE s.day BETWEEN cast(cast(date_add('day', -7, cast(current_timestamp AT TIME ZONE 'Europe/Paris' AS date)) AS date) AS varchar) AND cast(cast(date_add('day', -1, cast(current_timestamp AT TIME ZONE 'Europe/Paris' AS date)) AS date) AS varchar)
), bridge AS (
    SELECT email_hash, mapping_day, trim(element_at(parts, 2)) AS uid,
           array_sort(array_agg(DISTINCT lower(trim(element_at(parts, 1))))) AS uid_types
    FROM tokens WHERE cardinality(parts) = 2 AND nullif(trim(element_at(parts, 1)), '') IS NOT NULL
         AND nullif(trim(element_at(parts, 2)), '') IS NOT NULL
    GROUP BY email_hash, mapping_day, trim(element_at(parts, 2))
), zip_states AS (
    -- Never let duplicate ZIP3 keys multiply UID-day observations.
    SELECT trim(zip3) AS zip3,
           CASE WHEN count(DISTINCT CASE upper(regexp_replace(trim(cast(state AS varchar)), '\s+', ' '))
    WHEN 'AL' THEN 'AL' WHEN 'ALABAMA' THEN 'AL'
    WHEN 'AK' THEN 'AK' WHEN 'ALASKA' THEN 'AK'
    WHEN 'AZ' THEN 'AZ' WHEN 'ARIZONA' THEN 'AZ'
    WHEN 'AR' THEN 'AR' WHEN 'ARKANSAS' THEN 'AR'
    WHEN 'CA' THEN 'CA' WHEN 'CALIFORNIA' THEN 'CA'
    WHEN 'CO' THEN 'CO' WHEN 'COLORADO' THEN 'CO'
    WHEN 'CT' THEN 'CT' WHEN 'CONNECTICUT' THEN 'CT'
    WHEN 'DE' THEN 'DE' WHEN 'DELAWARE' THEN 'DE'
    WHEN 'DC' THEN 'DC' WHEN 'DISTRICT OF COLUMBIA' THEN 'DC'
    WHEN 'FL' THEN 'FL' WHEN 'FLORIDA' THEN 'FL'
    WHEN 'GA' THEN 'GA' WHEN 'GEORGIA' THEN 'GA'
    WHEN 'HI' THEN 'HI' WHEN 'HAWAII' THEN 'HI'
    WHEN 'ID' THEN 'ID' WHEN 'IDAHO' THEN 'ID'
    WHEN 'IL' THEN 'IL' WHEN 'ILLINOIS' THEN 'IL'
    WHEN 'IN' THEN 'IN' WHEN 'INDIANA' THEN 'IN'
    WHEN 'IA' THEN 'IA' WHEN 'IOWA' THEN 'IA'
    WHEN 'KS' THEN 'KS' WHEN 'KANSAS' THEN 'KS'
    WHEN 'KY' THEN 'KY' WHEN 'KENTUCKY' THEN 'KY'
    WHEN 'LA' THEN 'LA' WHEN 'LOUISIANA' THEN 'LA'
    WHEN 'ME' THEN 'ME' WHEN 'MAINE' THEN 'ME'
    WHEN 'MD' THEN 'MD' WHEN 'MARYLAND' THEN 'MD'
    WHEN 'MA' THEN 'MA' WHEN 'MASSACHUSETTS' THEN 'MA'
    WHEN 'MI' THEN 'MI' WHEN 'MICHIGAN' THEN 'MI'
    WHEN 'MN' THEN 'MN' WHEN 'MINNESOTA' THEN 'MN'
    WHEN 'MS' THEN 'MS' WHEN 'MISSISSIPPI' THEN 'MS'
    WHEN 'MO' THEN 'MO' WHEN 'MISSOURI' THEN 'MO'
    WHEN 'MT' THEN 'MT' WHEN 'MONTANA' THEN 'MT'
    WHEN 'NE' THEN 'NE' WHEN 'NEBRASKA' THEN 'NE'
    WHEN 'NV' THEN 'NV' WHEN 'NEVADA' THEN 'NV'
    WHEN 'NH' THEN 'NH' WHEN 'NEW HAMPSHIRE' THEN 'NH'
    WHEN 'NJ' THEN 'NJ' WHEN 'NEW JERSEY' THEN 'NJ'
    WHEN 'NM' THEN 'NM' WHEN 'NEW MEXICO' THEN 'NM'
    WHEN 'NY' THEN 'NY' WHEN 'NEW YORK' THEN 'NY'
    WHEN 'NC' THEN 'NC' WHEN 'NORTH CAROLINA' THEN 'NC'
    WHEN 'ND' THEN 'ND' WHEN 'NORTH DAKOTA' THEN 'ND'
    WHEN 'OH' THEN 'OH' WHEN 'OHIO' THEN 'OH'
    WHEN 'OK' THEN 'OK' WHEN 'OKLAHOMA' THEN 'OK'
    WHEN 'OR' THEN 'OR' WHEN 'OREGON' THEN 'OR'
    WHEN 'PA' THEN 'PA' WHEN 'PENNSYLVANIA' THEN 'PA'
    WHEN 'RI' THEN 'RI' WHEN 'RHODE ISLAND' THEN 'RI'
    WHEN 'SC' THEN 'SC' WHEN 'SOUTH CAROLINA' THEN 'SC'
    WHEN 'SD' THEN 'SD' WHEN 'SOUTH DAKOTA' THEN 'SD'
    WHEN 'TN' THEN 'TN' WHEN 'TENNESSEE' THEN 'TN'
    WHEN 'TX' THEN 'TX' WHEN 'TEXAS' THEN 'TX'
    WHEN 'UT' THEN 'UT' WHEN 'UTAH' THEN 'UT'
    WHEN 'VT' THEN 'VT' WHEN 'VERMONT' THEN 'VT'
    WHEN 'VA' THEN 'VA' WHEN 'VIRGINIA' THEN 'VA'
    WHEN 'WA' THEN 'WA' WHEN 'WASHINGTON' THEN 'WA'
    WHEN 'WV' THEN 'WV' WHEN 'WEST VIRGINIA' THEN 'WV'
    WHEN 'WI' THEN 'WI' WHEN 'WISCONSIN' THEN 'WI'
    WHEN 'WY' THEN 'WY' WHEN 'WYOMING' THEN 'WY'
    WHEN 'AS' THEN 'AS' WHEN 'AMERICAN SAMOA' THEN 'AS'
    WHEN 'GU' THEN 'GU' WHEN 'GUAM' THEN 'GU'
    WHEN 'MP' THEN 'MP' WHEN 'NORTHERN MARIANA ISLANDS' THEN 'MP'
    WHEN 'PR' THEN 'PR' WHEN 'PUERTO RICO' THEN 'PR'
    WHEN 'VI' THEN 'VI' WHEN 'US VIRGIN ISLANDS' THEN 'VI'
    WHEN 'U.S. VIRGIN ISLANDS' THEN 'VI' WHEN 'VIRGIN ISLANDS' THEN 'VI'
END) = 1
                       AND count_if(CASE upper(regexp_replace(trim(cast(state AS varchar)), '\s+', ' '))
    WHEN 'AL' THEN 'AL' WHEN 'ALABAMA' THEN 'AL'
    WHEN 'AK' THEN 'AK' WHEN 'ALASKA' THEN 'AK'
    WHEN 'AZ' THEN 'AZ' WHEN 'ARIZONA' THEN 'AZ'
    WHEN 'AR' THEN 'AR' WHEN 'ARKANSAS' THEN 'AR'
    WHEN 'CA' THEN 'CA' WHEN 'CALIFORNIA' THEN 'CA'
    WHEN 'CO' THEN 'CO' WHEN 'COLORADO' THEN 'CO'
    WHEN 'CT' THEN 'CT' WHEN 'CONNECTICUT' THEN 'CT'
    WHEN 'DE' THEN 'DE' WHEN 'DELAWARE' THEN 'DE'
    WHEN 'DC' THEN 'DC' WHEN 'DISTRICT OF COLUMBIA' THEN 'DC'
    WHEN 'FL' THEN 'FL' WHEN 'FLORIDA' THEN 'FL'
    WHEN 'GA' THEN 'GA' WHEN 'GEORGIA' THEN 'GA'
    WHEN 'HI' THEN 'HI' WHEN 'HAWAII' THEN 'HI'
    WHEN 'ID' THEN 'ID' WHEN 'IDAHO' THEN 'ID'
    WHEN 'IL' THEN 'IL' WHEN 'ILLINOIS' THEN 'IL'
    WHEN 'IN' THEN 'IN' WHEN 'INDIANA' THEN 'IN'
    WHEN 'IA' THEN 'IA' WHEN 'IOWA' THEN 'IA'
    WHEN 'KS' THEN 'KS' WHEN 'KANSAS' THEN 'KS'
    WHEN 'KY' THEN 'KY' WHEN 'KENTUCKY' THEN 'KY'
    WHEN 'LA' THEN 'LA' WHEN 'LOUISIANA' THEN 'LA'
    WHEN 'ME' THEN 'ME' WHEN 'MAINE' THEN 'ME'
    WHEN 'MD' THEN 'MD' WHEN 'MARYLAND' THEN 'MD'
    WHEN 'MA' THEN 'MA' WHEN 'MASSACHUSETTS' THEN 'MA'
    WHEN 'MI' THEN 'MI' WHEN 'MICHIGAN' THEN 'MI'
    WHEN 'MN' THEN 'MN' WHEN 'MINNESOTA' THEN 'MN'
    WHEN 'MS' THEN 'MS' WHEN 'MISSISSIPPI' THEN 'MS'
    WHEN 'MO' THEN 'MO' WHEN 'MISSOURI' THEN 'MO'
    WHEN 'MT' THEN 'MT' WHEN 'MONTANA' THEN 'MT'
    WHEN 'NE' THEN 'NE' WHEN 'NEBRASKA' THEN 'NE'
    WHEN 'NV' THEN 'NV' WHEN 'NEVADA' THEN 'NV'
    WHEN 'NH' THEN 'NH' WHEN 'NEW HAMPSHIRE' THEN 'NH'
    WHEN 'NJ' THEN 'NJ' WHEN 'NEW JERSEY' THEN 'NJ'
    WHEN 'NM' THEN 'NM' WHEN 'NEW MEXICO' THEN 'NM'
    WHEN 'NY' THEN 'NY' WHEN 'NEW YORK' THEN 'NY'
    WHEN 'NC' THEN 'NC' WHEN 'NORTH CAROLINA' THEN 'NC'
    WHEN 'ND' THEN 'ND' WHEN 'NORTH DAKOTA' THEN 'ND'
    WHEN 'OH' THEN 'OH' WHEN 'OHIO' THEN 'OH'
    WHEN 'OK' THEN 'OK' WHEN 'OKLAHOMA' THEN 'OK'
    WHEN 'OR' THEN 'OR' WHEN 'OREGON' THEN 'OR'
    WHEN 'PA' THEN 'PA' WHEN 'PENNSYLVANIA' THEN 'PA'
    WHEN 'RI' THEN 'RI' WHEN 'RHODE ISLAND' THEN 'RI'
    WHEN 'SC' THEN 'SC' WHEN 'SOUTH CAROLINA' THEN 'SC'
    WHEN 'SD' THEN 'SD' WHEN 'SOUTH DAKOTA' THEN 'SD'
    WHEN 'TN' THEN 'TN' WHEN 'TENNESSEE' THEN 'TN'
    WHEN 'TX' THEN 'TX' WHEN 'TEXAS' THEN 'TX'
    WHEN 'UT' THEN 'UT' WHEN 'UTAH' THEN 'UT'
    WHEN 'VT' THEN 'VT' WHEN 'VERMONT' THEN 'VT'
    WHEN 'VA' THEN 'VA' WHEN 'VIRGINIA' THEN 'VA'
    WHEN 'WA' THEN 'WA' WHEN 'WASHINGTON' THEN 'WA'
    WHEN 'WV' THEN 'WV' WHEN 'WEST VIRGINIA' THEN 'WV'
    WHEN 'WI' THEN 'WI' WHEN 'WISCONSIN' THEN 'WI'
    WHEN 'WY' THEN 'WY' WHEN 'WYOMING' THEN 'WY'
    WHEN 'AS' THEN 'AS' WHEN 'AMERICAN SAMOA' THEN 'AS'
    WHEN 'GU' THEN 'GU' WHEN 'GUAM' THEN 'GU'
    WHEN 'MP' THEN 'MP' WHEN 'NORTHERN MARIANA ISLANDS' THEN 'MP'
    WHEN 'PR' THEN 'PR' WHEN 'PUERTO RICO' THEN 'PR'
    WHEN 'VI' THEN 'VI' WHEN 'US VIRGIN ISLANDS' THEN 'VI'
    WHEN 'U.S. VIRGIN ISLANDS' THEN 'VI' WHEN 'VIRGIN ISLANDS' THEN 'VI'
END IS NULL) = 0
                THEN max(CASE upper(regexp_replace(trim(cast(state AS varchar)), '\s+', ' '))
    WHEN 'AL' THEN 'AL' WHEN 'ALABAMA' THEN 'AL'
    WHEN 'AK' THEN 'AK' WHEN 'ALASKA' THEN 'AK'
    WHEN 'AZ' THEN 'AZ' WHEN 'ARIZONA' THEN 'AZ'
    WHEN 'AR' THEN 'AR' WHEN 'ARKANSAS' THEN 'AR'
    WHEN 'CA' THEN 'CA' WHEN 'CALIFORNIA' THEN 'CA'
    WHEN 'CO' THEN 'CO' WHEN 'COLORADO' THEN 'CO'
    WHEN 'CT' THEN 'CT' WHEN 'CONNECTICUT' THEN 'CT'
    WHEN 'DE' THEN 'DE' WHEN 'DELAWARE' THEN 'DE'
    WHEN 'DC' THEN 'DC' WHEN 'DISTRICT OF COLUMBIA' THEN 'DC'
    WHEN 'FL' THEN 'FL' WHEN 'FLORIDA' THEN 'FL'
    WHEN 'GA' THEN 'GA' WHEN 'GEORGIA' THEN 'GA'
    WHEN 'HI' THEN 'HI' WHEN 'HAWAII' THEN 'HI'
    WHEN 'ID' THEN 'ID' WHEN 'IDAHO' THEN 'ID'
    WHEN 'IL' THEN 'IL' WHEN 'ILLINOIS' THEN 'IL'
    WHEN 'IN' THEN 'IN' WHEN 'INDIANA' THEN 'IN'
    WHEN 'IA' THEN 'IA' WHEN 'IOWA' THEN 'IA'
    WHEN 'KS' THEN 'KS' WHEN 'KANSAS' THEN 'KS'
    WHEN 'KY' THEN 'KY' WHEN 'KENTUCKY' THEN 'KY'
    WHEN 'LA' THEN 'LA' WHEN 'LOUISIANA' THEN 'LA'
    WHEN 'ME' THEN 'ME' WHEN 'MAINE' THEN 'ME'
    WHEN 'MD' THEN 'MD' WHEN 'MARYLAND' THEN 'MD'
    WHEN 'MA' THEN 'MA' WHEN 'MASSACHUSETTS' THEN 'MA'
    WHEN 'MI' THEN 'MI' WHEN 'MICHIGAN' THEN 'MI'
    WHEN 'MN' THEN 'MN' WHEN 'MINNESOTA' THEN 'MN'
    WHEN 'MS' THEN 'MS' WHEN 'MISSISSIPPI' THEN 'MS'
    WHEN 'MO' THEN 'MO' WHEN 'MISSOURI' THEN 'MO'
    WHEN 'MT' THEN 'MT' WHEN 'MONTANA' THEN 'MT'
    WHEN 'NE' THEN 'NE' WHEN 'NEBRASKA' THEN 'NE'
    WHEN 'NV' THEN 'NV' WHEN 'NEVADA' THEN 'NV'
    WHEN 'NH' THEN 'NH' WHEN 'NEW HAMPSHIRE' THEN 'NH'
    WHEN 'NJ' THEN 'NJ' WHEN 'NEW JERSEY' THEN 'NJ'
    WHEN 'NM' THEN 'NM' WHEN 'NEW MEXICO' THEN 'NM'
    WHEN 'NY' THEN 'NY' WHEN 'NEW YORK' THEN 'NY'
    WHEN 'NC' THEN 'NC' WHEN 'NORTH CAROLINA' THEN 'NC'
    WHEN 'ND' THEN 'ND' WHEN 'NORTH DAKOTA' THEN 'ND'
    WHEN 'OH' THEN 'OH' WHEN 'OHIO' THEN 'OH'
    WHEN 'OK' THEN 'OK' WHEN 'OKLAHOMA' THEN 'OK'
    WHEN 'OR' THEN 'OR' WHEN 'OREGON' THEN 'OR'
    WHEN 'PA' THEN 'PA' WHEN 'PENNSYLVANIA' THEN 'PA'
    WHEN 'RI' THEN 'RI' WHEN 'RHODE ISLAND' THEN 'RI'
    WHEN 'SC' THEN 'SC' WHEN 'SOUTH CAROLINA' THEN 'SC'
    WHEN 'SD' THEN 'SD' WHEN 'SOUTH DAKOTA' THEN 'SD'
    WHEN 'TN' THEN 'TN' WHEN 'TENNESSEE' THEN 'TN'
    WHEN 'TX' THEN 'TX' WHEN 'TEXAS' THEN 'TX'
    WHEN 'UT' THEN 'UT' WHEN 'UTAH' THEN 'UT'
    WHEN 'VT' THEN 'VT' WHEN 'VERMONT' THEN 'VT'
    WHEN 'VA' THEN 'VA' WHEN 'VIRGINIA' THEN 'VA'
    WHEN 'WA' THEN 'WA' WHEN 'WASHINGTON' THEN 'WA'
    WHEN 'WV' THEN 'WV' WHEN 'WEST VIRGINIA' THEN 'WV'
    WHEN 'WI' THEN 'WI' WHEN 'WISCONSIN' THEN 'WI'
    WHEN 'WY' THEN 'WY' WHEN 'WYOMING' THEN 'WY'
    WHEN 'AS' THEN 'AS' WHEN 'AMERICAN SAMOA' THEN 'AS'
    WHEN 'GU' THEN 'GU' WHEN 'GUAM' THEN 'GU'
    WHEN 'MP' THEN 'MP' WHEN 'NORTHERN MARIANA ISLANDS' THEN 'MP'
    WHEN 'PR' THEN 'PR' WHEN 'PUERTO RICO' THEN 'PR'
    WHEN 'VI' THEN 'VI' WHEN 'US VIRGIN ISLANDS' THEN 'VI'
    WHEN 'U.S. VIRGIN ISLANDS' THEN 'VI' WHEN 'VIRGIN ISLANDS' THEN 'VI'
END) END AS state
    FROM iceberg.jteixeira_ipa.tmp_zip3_to_state GROUP BY trim(zip3)
), states AS (
    SELECT DISTINCT try_cast(g.day AS date) AS observation_day, g.uid, z.state
    FROM iceberg.crossscreen.nscreen_geo_daily_ua g
    JOIN (SELECT DISTINCT uid FROM bridge) u ON g.uid = u.uid
    LEFT JOIN zip_states z ON regexp_like(trim(g.geo), '^[0-9]{1,3}$') AND lpad(trim(g.geo), 3, '0') = z.zip3
    WHERE g.day BETWEEN cast(cast(date_add('day', -7, cast(current_timestamp AT TIME ZONE 'Europe/Paris' AS date)) AS date) AS varchar) AND cast(cast(date_add('day', -1, cast(current_timestamp AT TIME ZONE 'Europe/Paris' AS date)) AS date) AS varchar)
), uid_states AS (
    SELECT uid, state, count(DISTINCT observation_day) AS state_days,
           array_sort(array_agg(DISTINCT observation_day)) AS days
    FROM states GROUP BY uid, state
), scored AS (
    SELECT *, max(CASE WHEN state IS NOT NULL THEN state_days ELSE 0 END) OVER (PARTITION BY uid) AS top_days,
           count_if(state IS NOT NULL) OVER (PARTITION BY uid) AS state_count,
           array_distinct(flatten(array_agg(days) OVER (PARTITION BY uid))) AS observation_days
    FROM uid_states
), ranked AS (
    SELECT *, row_number() OVER (PARTITION BY uid ORDER BY CASE WHEN state IS NULL THEN 1 ELSE 0 END, state_days DESC, state) AS rn,
           count_if(state IS NOT NULL AND state_days = top_days) OVER (PARTITION BY uid) AS top_count
    FROM scored
), primary_states AS (
    SELECT * FROM ranked WHERE rn = 1
), uid_days AS (
    SELECT b.*, s.state, coalesce(s.top_count > 1, false) AS tied,
           coalesce(s.state_count > 1, false) AS multistate,
           coalesce(contains(s.observation_days, b.mapping_day), false) AS observed,
           coalesce(s.state IS NOT NULL AND contains(s.days, b.mapping_day), false) AS located
    FROM bridge b LEFT JOIN primary_states s ON b.uid = s.uid
)
SELECT email_hash, count(DISTINCT uid) AS cookie_count,
       count(DISTINCT mapping_day) AS cookie_mapping_days,
       count(*) AS cookie_mapped_uid_days,
       count_if(observed) AS cookie_observed_uid_days,
       count_if(located) AS cookie_located_uid_days,
       count_if(located AND NOT tied) AS cookie_eligible_uid_days,
       count(DISTINCT IF(located, uid, NULL)) AS cookie_located_count,
       count(DISTINCT IF(tied, uid, NULL)) AS cookie_primary_state_tied_count,
       count(DISTINCT IF(multistate, uid, NULL)) AS cookie_primary_state_multistate_count,
       count(DISTINCT IF(located AND NOT tied, mapping_day, NULL)) AS cookie_eligible_observed_days,
       min(IF(located AND NOT tied, mapping_day, NULL)) AS cookie_location_first_day,
       max(IF(located AND NOT tied, mapping_day, NULL)) AS cookie_location_last_day,
       array_sort(array_distinct(flatten(array_agg(uid_types)))) AS cookie_uid_types,
       array_sort(array_distinct(filter(array_agg(IF(located AND NOT tied, state, NULL)), s -> s IS NOT NULL))) AS cookie_state_values
FROM uid_days GROUP BY email_hash),
coverage AS (WITH mapping_days AS (

SELECT DISTINCT try_cast(partition.day AS date) AS day FROM iceberg.thirdparty."liveintent_idsync$partitions"
WHERE record_count > 0 AND partition.day BETWEEN cast(cast(date_add('day', -7, cast(current_timestamp AT TIME ZONE 'Europe/Paris' AS date)) AS date) AS varchar) AND cast(cast(date_add('day', -1, cast(current_timestamp AT TIME ZONE 'Europe/Paris' AS date)) AS date) AS varchar)
),
geo_days AS (

SELECT DISTINCT try_cast(partition.day AS date) AS day FROM iceberg.crossscreen."nscreen_geo_daily_ua$partitions"
WHERE record_count > 0 AND partition.day BETWEEN cast(cast(date_add('day', -7, cast(current_timestamp AT TIME ZONE 'Europe/Paris' AS date)) AS date) AS varchar) AND cast(cast(date_add('day', -1, cast(current_timestamp AT TIME ZONE 'Europe/Paris' AS date)) AS date) AS varchar)
),
available AS (
    SELECT coalesce((SELECT array_sort(array_agg(day)) FROM mapping_days WHERE day IS NOT NULL), cast(ARRAY[] AS array(date))) AS md,
           coalesce((SELECT array_sort(array_agg(day)) FROM geo_days WHERE day IS NOT NULL), cast(ARRAY[] AS array(date))) AS gd,
           transform(sequence(cast(date_add('day', -7, cast(current_timestamp AT TIME ZONE 'Europe/Paris' AS date)) AS date), cast(date_add('day', -1, cast(current_timestamp AT TIME ZONE 'Europe/Paris' AS date)) AS date), INTERVAL '1' DAY), d -> cast(d AS date)) AS expected
)
SELECT cast(7 AS bigint) AS cookie_location_window_days,
       cast(cardinality(md) AS bigint) AS cookie_mapping_available_days,
       cast(cardinality(gd) AS bigint) AS cookie_location_available_days,
       filter(expected, d -> NOT contains(md, d)) AS cookie_mapping_missing_days,
       filter(expected, d -> NOT contains(gd, d)) AS cookie_location_missing_days,
       CASE WHEN cardinality(md) = 7 AND cardinality(gd) = 7 THEN 'all_source_days_present' ELSE 'missing_source_days' END AS cookie_location_window_status
FROM available), joined AS (
    SELECT m.*,

       coalesce(e.cookie_count, cast(0 AS bigint)) AS cookie_count,
       coalesce(e.cookie_mapping_days, cast(0 AS bigint)) AS cookie_mapping_days,
       coalesce(e.cookie_mapped_uid_days, cast(0 AS bigint)) AS cookie_mapped_uid_days,
       coalesce(e.cookie_observed_uid_days, cast(0 AS bigint)) AS cookie_observed_uid_days,
       coalesce(e.cookie_located_uid_days, cast(0 AS bigint)) AS cookie_located_uid_days,
       coalesce(e.cookie_eligible_uid_days, cast(0 AS bigint)) AS cookie_eligible_uid_days,
       coalesce(e.cookie_located_count, cast(0 AS bigint)) AS cookie_located_count,
       coalesce(e.cookie_primary_state_tied_count, cast(0 AS bigint)) AS cookie_primary_state_tied_count,
       coalesce(e.cookie_primary_state_multistate_count, cast(0 AS bigint)) AS cookie_primary_state_multistate_count,
       coalesce(e.cookie_eligible_observed_days, cast(0 AS bigint)) AS cookie_eligible_observed_days,
       e.cookie_location_first_day, e.cookie_location_last_day,
       coalesce(e.cookie_uid_types, cast(ARRAY[] AS array(varchar))) AS cookie_uid_types,
       coalesce(e.cookie_state_values, cast(ARRAY[] AS array(varchar))) AS cookie_state_values,
       coverage.*
    FROM facility_states m LEFT JOIN email_evidence e ON lower(to_hex(sha256(to_utf8(lower(trim(m.email)))))) = e.email_hash
    CROSS JOIN coverage
), status AS (
    SELECT *, cast(cardinality(cookie_state_values) AS bigint) AS cookie_state_count,
       CASE WHEN cookie_count = 0 THEN 'no_mapping'
            WHEN cookie_eligible_uid_days > 0 THEN 'observed'
            WHEN cookie_located_uid_days > 0 THEN 'ambiguous_primary_state'
            WHEN cookie_observed_uid_days > 0 THEN 'unknown_state'
            ELSE 'no_state_observation' END AS cookie_location_status
    FROM joined
)
SELECT *, CASE WHEN cookie_location_status <> 'observed' THEN 'unknown_cookie_location'
     WHEN cardinality(source_state_values) = 0 THEN 'unknown_reference_state'
     WHEN NOT arrays_overlap(source_state_values, cookie_state_values) THEN 'not_observed'
     WHEN cardinality(source_state_values) = 1 AND cardinality(cookie_state_values) = 1 THEN 'corroborated'
     ELSE 'mixed_state_evidence' END AS cookie_vendor_state_evidence,
       CASE WHEN cookie_location_status <> 'observed' THEN 'unknown_cookie_location'
     WHEN cardinality(filter(ARRAY[facility_primary_state], s -> s IS NOT NULL)) = 0 THEN 'unknown_reference_state'
     WHEN NOT arrays_overlap(filter(ARRAY[facility_primary_state], s -> s IS NOT NULL), cookie_state_values) THEN 'not_observed'
     WHEN cardinality(filter(ARRAY[facility_primary_state], s -> s IS NOT NULL)) = 1 AND cardinality(cookie_state_values) = 1 THEN 'corroborated'
     ELSE 'mixed_state_evidence' END AS cookie_facility_state_evidence,
       cast(date_add('day', -7, cast(current_timestamp AT TIME ZONE 'Europe/Paris' AS date)) AS date) AS cookie_location_window_start,
       cast(date_add('day', -1, cast(current_timestamp AT TIME ZONE 'Europe/Paris' AS date)) AS date) AS cookie_location_window_end,
       'iceberg.thirdparty.liveintent_idsync' AS cookie_mapping_table,
       'iceberg.crossscreen.nscreen_geo_daily_ua' AS cookie_location_geo_table,
       'iceberg.jteixeira_ipa.tmp_zip3_to_state' AS cookie_zip_mapping_table,
       'liveintent_primary_state_untied_v1' AS cookie_location_evidence_version
FROM status
)
SELECT
    r.email,
    r.source,
    r.npi,
    array_join(transform(r.source_name_values, n -> trim(concat_ws(' ', n.first_name, n.last_name))), '; ') AS name,
    array_join(r.source_state_values, '; ') AS state,
    r.first_seen_day,
    r.last_seen_day,
    r.observed_day_count,
    r.observation_count,
    r.undated_observation_count,
    r.invalid_day_observation_count,
    r.source_tables,
    r.source_feeds,
    r.computed_at,
    r.definition_version,
    r.email_format_valid,
    r.email_role_account,
    r.email_domain_class,
    r.email_matches_source_name,
    r.email_matches_registry_name,
    r.vendor_name_matches_registry_name,
    r.source_name_usable,
    r.registry_name_usable,
    r.registry_npi_present,
    r.record_id,
    r.metric_row_id,
    r.email_ordinal,
    r.email_origin,
    r.record_payload,
    r.email_npi_count,
    r.email_has_multiple_npis,
    r.has_been_reassigned,
    r.has_conflict_linkage,
    r.observed_days,
    r.conflict_days,
    r.source_name_values,
    r.source_state_values,
    r.email_name_count,
    r.email_npi_has_name_conflict,
    r.conflicting_npis_share_name,
    r.conflicting_npi_name_comparisons,
    r.conflicting_npis_share_state,
    r.conflicting_npi_state_comparisons,
    r.facility_npi_values,
    r.facility_reference_table,
    r.facility_definition_version,
    r.conflicting_npis_share_facility,
    r.conflicting_npi_facility_comparisons,
    r.specialty_code_values,
    r.specialty_reference_table,
    r.specialty_definition_version,
    r.conflicting_npis_share_specialty,
    r.conflicting_npi_specialty_comparisons,
    r.npi_registry_status,
    r.npi_registry_status_reason,
    r.npi_registry_replacement_npi,
    r.npi_registry_deactivation_date,
    r.npi_registry_reactivation_date,
    r.npi_registry_reference_row_count,
    r.npi_registry_variant_count,
    r.npi_registry_lifecycle_evidence,
    r.npi_registry_status_as_of_day,
    r.npi_registry_reference_table,
    r.npi_registry_definition_version,
    r.facility_primary_state,
    r.facility_reference_status,
    r.facility_rank1_rows,
    r.facility_rank1_state_count,
    r.facility_rank1_unknown_state_rows,
    r.facility_rank1_missing_location_rows,
    r.vendor_state_evidence,
    r.vendor_state_corroborated,
    r.location_evaluation_day,
    r.location_reference_table,
    r.location_evidence_version,
    r.cookie_count,
    r.cookie_mapping_days,
    r.cookie_mapped_uid_days,
    r.cookie_observed_uid_days,
    r.cookie_located_uid_days,
    r.cookie_eligible_uid_days,
    r.cookie_located_count,
    r.cookie_primary_state_tied_count,
    r.cookie_primary_state_multistate_count,
    r.cookie_eligible_observed_days,
    r.cookie_location_first_day,
    r.cookie_location_last_day,
    r.cookie_uid_types,
    r.cookie_state_values,
    r.cookie_location_window_days,
    r.cookie_mapping_available_days,
    r.cookie_location_available_days,
    r.cookie_mapping_missing_days,
    r.cookie_location_missing_days,
    r.cookie_location_window_status,
    r.cookie_state_count,
    r.cookie_location_status,
    r.cookie_vendor_state_evidence,
    r.cookie_facility_state_evidence,
    r.cookie_location_window_start,
    r.cookie_location_window_end,
    r.cookie_mapping_table,
    r.cookie_location_geo_table,
    r.cookie_zip_mapping_table,
    r.cookie_location_evidence_version,
    cardinality(r.conflicting_npi_name_comparisons) AS name_comparison_count,
    cardinality(filter(r.conflicting_npi_name_comparisons, x -> x.shares_name = false)) AS name_mismatch_count,
    cardinality(filter(r.conflicting_npi_name_comparisons, x -> x.shares_name = true)) AS shared_name_count,
    cardinality(filter(r.conflicting_npi_name_comparisons, x -> x.shares_name IS NULL)) AS unknown_name_match_count
FROM enriched r
ORDER BY r.source, r.npi, r.last_seen_day DESC NULLS LAST, r.metric_row_id;

-- Read-only statistics for 19_cookie_location_evidence.
-- Denominators remain within each source; no email-NPI deduplication.
-- Exact executed SQL exported from local location_evidence_cookie.json; result rows are excluded. Original source relations are retained.

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
FROM available;

-- Exact vendor denominators
SELECT source, count(*) AS metric_rows,
count(DISTINCT ROW(email,npi)) AS distinct_links FROM iceberg.jteixeira_ipa.pii_clean GROUP BY source ORDER BY source;

-- Grouping-set sections: totals, cookie status, vendor-state comparison, facility-state comparison
WITH measured AS (WITH saved_records AS (SELECT * FROM iceberg.jteixeira_ipa.pii_clean),
facility_records AS (WITH facility_reference AS (WITH normalized AS (
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
    FROM saved_records m LEFT JOIN facility_reference r ON m.npi = r.npi
), compared AS (
    SELECT *, CASE WHEN facility_reference_status <> 'usable' THEN 'unknown_facility'
     WHEN cardinality(source_state_values) = 0 THEN 'unknown_vendor_state'
     WHEN contains(source_state_values, facility_primary_state)
          THEN CASE WHEN cardinality(source_state_values) = 1 THEN 'corroborated' ELSE 'mixed_vendor_states' END
     ELSE 'not_corroborated' END AS vendor_state_evidence FROM enriched
)
SELECT *, CASE vendor_state_evidence WHEN 'corroborated' THEN true WHEN 'not_corroborated' THEN false END
              AS vendor_state_corroborated,
       DATE '2026-10-29'
 AS location_evaluation_day,
       'bq_bi.analytics_prod.npi_facility_locations_with_ids' AS location_reference_table,
       'record_vendor_facility_state_v1' AS location_evidence_version
FROM compared), evaluated AS (WITH email_evidence AS (WITH population AS (
    SELECT DISTINCT lower(to_hex(sha256(to_utf8(lower(trim(email)))))) AS email_hash FROM facility_records
), tokens AS (
    SELECT lower(trim(s.hashedemail_sha256)) AS email_hash, try_cast(s.day AS date) AS mapping_day,
           split(trim(t.token), ':') AS parts
    FROM iceberg.thirdparty.liveintent_idsync s
    JOIN population p ON lower(trim(s.hashedemail_sha256)) = p.email_hash
    CROSS JOIN UNNEST(split(coalesce(s.uids, ''), '|')) AS t(token)
    WHERE s.day BETWEEN cast(cast(date_add('day', -7, DATE '2026-10-29'
) AS date) AS varchar) AND cast(cast(date_add('day', -1, DATE '2026-10-29'
) AS date) AS varchar)
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
    WHERE g.day BETWEEN cast(cast(date_add('day', -7, DATE '2026-10-29'
) AS date) AS varchar) AND cast(cast(date_add('day', -1, DATE '2026-10-29'
) AS date) AS varchar)
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
    FROM facility_records m LEFT JOIN email_evidence e ON lower(to_hex(sha256(to_utf8(lower(trim(m.email)))))) = e.email_hash
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
       cast(date_add('day', -7, DATE '2026-10-29'
) AS date) AS cookie_location_window_start,
       cast(date_add('day', -1, DATE '2026-10-29'
) AS date) AS cookie_location_window_end,
       'iceberg.thirdparty.liveintent_idsync' AS cookie_mapping_table,
       'iceberg.crossscreen.nscreen_geo_daily_ua' AS cookie_location_geo_table,
       'iceberg.jteixeira_ipa.tmp_zip3_to_state' AS cookie_zip_mapping_table,
       'liveintent_primary_state_untied_v1' AS cookie_location_evidence_version
FROM status) SELECT * FROM evaluated)
SELECT source,
       CASE WHEN grouping(cookie_location_status) = 0 THEN 'location_status'
            WHEN grouping(cookie_vendor_state_evidence) = 0 THEN 'vendor_state'
            WHEN grouping(cookie_facility_state_evidence) = 0 THEN 'facility_state'
            ELSE 'totals' END AS section,
       cookie_location_status, cookie_vendor_state_evidence, cookie_facility_state_evidence,
       count(*) AS metric_rows, count(DISTINCT metric_row_id) AS unique_metric_rows,
       count(DISTINCT ROW(email, npi)) AS distinct_links, count(DISTINCT email) AS distinct_emails,
       count_if(cookie_count IS NULL OR cookie_count < 0
   OR cookie_mapped_uid_days < cookie_count
   OR cookie_observed_uid_days > cookie_mapped_uid_days
   OR cookie_located_uid_days > cookie_observed_uid_days
   OR cookie_eligible_uid_days > cookie_located_uid_days
   OR cookie_located_count > cookie_count
   OR cookie_primary_state_tied_count > cookie_count
   OR cookie_primary_state_multistate_count > cookie_count
   OR cookie_mapping_days > 7 OR cookie_eligible_observed_days > cookie_mapping_days
   OR cookie_state_values IS NULL OR cookie_uid_types IS NULL
   OR cookie_state_values IS DISTINCT FROM array_sort(array_distinct(cookie_state_values))
   OR cookie_state_count <> cardinality(cookie_state_values)
   OR (cookie_eligible_uid_days > 0) IS DISTINCT FROM (cookie_location_status = 'observed')
   OR (cookie_eligible_uid_days = 0) IS DISTINCT FROM (cookie_location_first_day IS NULL)
   OR (cookie_eligible_uid_days = 0) IS DISTINCT FROM (cookie_location_last_day IS NULL)
   OR cookie_location_first_day < cookie_location_window_start
   OR cookie_location_last_day > cookie_location_window_end
   OR cookie_location_first_day > cookie_location_last_day
   OR cookie_mapping_available_days + cardinality(cookie_mapping_missing_days) <> 7
   OR cookie_location_available_days + cardinality(cookie_location_missing_days) <> 7
   OR cookie_location_window_status IS DISTINCT FROM
      CASE WHEN cookie_mapping_available_days = 7 AND cookie_location_available_days = 7
           THEN 'all_source_days_present' ELSE 'missing_source_days' END
   OR (cookie_count = 0 AND (cookie_location_status <> 'no_mapping' OR cardinality(cookie_state_values) <> 0))
   OR cookie_vendor_state_evidence IS DISTINCT FROM
      CASE WHEN cookie_location_status <> 'observed' THEN 'unknown_cookie_location'
           WHEN cardinality(source_state_values) = 0 THEN 'unknown_reference_state'
           WHEN cardinality(array_intersect(source_state_values, cookie_state_values)) = 0 THEN 'not_observed'
           WHEN cardinality(source_state_values) = 1 AND cookie_state_count = 1 THEN 'corroborated'
           ELSE 'mixed_state_evidence' END) AS invariant_failures,
       count(DISTINCT IF(cookie_primary_state_tied_count > 0, email, NULL)) AS emails_with_tied_uids,
       count(DISTINCT IF(cookie_primary_state_multistate_count > 0, email, NULL)) AS emails_with_multistate_uids
FROM measured GROUP BY GROUPING SETS ((source), (source,cookie_location_status),
    (source,cookie_vendor_state_evidence), (source,cookie_facility_state_evidence))
ORDER BY source, section, cookie_location_status, cookie_vendor_state_evidence, cookie_facility_state_evidence;

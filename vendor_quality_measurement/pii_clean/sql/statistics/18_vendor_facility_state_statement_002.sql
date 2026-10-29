-- Record and distinct-link outcomes by facility-reference quality
WITH measured AS (WITH saved_records AS (SELECT * FROM iceberg.jteixeira_ipa.pii_clean), evaluated AS (WITH facility_reference AS (WITH normalized AS (
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
FROM compared) SELECT * FROM evaluated)
SELECT source, vendor_state_evidence, facility_reference_status,
       count(*) AS metric_rows, count(DISTINCT metric_row_id) AS unique_metric_rows,
       count(DISTINCT ROW(email, npi)) AS distinct_links,
       count_if(vendor_state_evidence IS NULL OR facility_reference_status IS NULL
   OR (facility_reference_status = 'usable') IS DISTINCT FROM (facility_primary_state IS NOT NULL)
   OR (facility_reference_status = 'usable' AND (facility_rank1_state_count <> 1
       OR facility_rank1_unknown_state_rows <> 0 OR facility_rank1_missing_location_rows <> 0))
   OR vendor_state_evidence IS DISTINCT FROM
      CASE WHEN facility_reference_status <> 'usable' THEN 'unknown_facility'
           WHEN cardinality(source_state_values) = 0 THEN 'unknown_vendor_state'
           WHEN cardinality(array_intersect(source_state_values, ARRAY[facility_primary_state])) = 0 THEN 'not_corroborated'
           WHEN cardinality(source_state_values) = 1 THEN 'corroborated' ELSE 'mixed_vendor_states' END
   OR vendor_state_corroborated IS DISTINCT FROM
      CASE vendor_state_evidence WHEN 'corroborated' THEN true WHEN 'not_corroborated' THEN false END
   OR facility_rank1_rows < facility_rank1_state_count) AS invariant_failures
FROM measured GROUP BY source, vendor_state_evidence, facility_reference_status ORDER BY 1, 2, 3

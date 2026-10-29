-- Statistics over published evidence in iceberg.jteixeira_ipa.pii_clean.
-- Reference evidence and evaluation dates come from the stored publication.
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
FROM iceberg.jteixeira_ipa.pii_clean
GROUP BY source, vendor_state_evidence, facility_reference_status ORDER BY 1, 2, 3

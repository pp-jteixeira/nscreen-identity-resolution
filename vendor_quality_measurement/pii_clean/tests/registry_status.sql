-- Invariants check status/reason, presence, chronology and retained evidence independently.
SELECT source, count(*) AS failing_metric_rows
FROM {{ ref(var('metric_model')) }}
WHERE npi_registry_status IS NULL OR npi_registry_status_reason IS NULL
   OR npi_registry_reference_row_count < npi_registry_variant_count
   OR npi_registry_variant_count < 0
   OR npi_registry_lifecycle_evidence IS NULL
   OR (npi_registry_status = 'not_found') IS DISTINCT FROM (npi_registry_reference_row_count = 0)
   OR (npi_registry_status = 'not_found' AND (npi_registry_status_reason <> 'no_nppes_record'
       OR cardinality(npi_registry_lifecycle_evidence) <> 0))
   OR npi_registry_status IS DISTINCT FROM
       CASE npi_registry_status_reason WHEN 'no_nppes_record' THEN 'not_found'
         WHEN 'replacement_reported' THEN 'replaced'
         WHEN 'latest_event_deactivation' THEN 'deactivated'
         WHEN 'latest_event_reactivation' THEN 'reactivated'
         WHEN 'no_deactivation_reported' THEN 'active_as_reported' ELSE 'unknown' END
   OR (npi_registry_status <> 'unknown' AND npi_registry_status <> 'not_found' AND npi_registry_variant_count <> 1)
   OR (npi_registry_status = 'deactivated' AND (npi_registry_deactivation_date IS NULL
       OR npi_registry_deactivation_date > npi_registry_status_as_of_day
       OR npi_registry_reactivation_date >= npi_registry_deactivation_date))
   OR (npi_registry_status = 'reactivated' AND (npi_registry_reactivation_date IS NULL
       OR npi_registry_reactivation_date > npi_registry_status_as_of_day
       OR npi_registry_deactivation_date >= npi_registry_reactivation_date))
   OR (npi_registry_status = 'replaced' AND npi_registry_replacement_npi IS NULL)
   OR (npi_registry_status = 'active_as_reported' AND (npi_registry_deactivation_date IS NOT NULL
       OR npi_registry_reactivation_date IS NOT NULL OR npi_registry_replacement_npi IS NOT NULL))
   OR (npi_registry_replacement_npi IS NOT NULL AND
       (NOT regexp_like(npi_registry_replacement_npi, '^[0-9]{10}$')
        OR npi_registry_replacement_npi = '0000000000' OR npi_registry_replacement_npi = npi))
GROUP BY source

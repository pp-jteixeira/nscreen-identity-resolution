-- Read-only statistics for 17_npi_registry_status.
-- Denominators remain within each source. no email-NPI deduplication.
-- Exact executed SQL exported from local registry_status_measure.json. result rows are excluded. Original source relations are retained.
-- Raw NPPES lifecycle field availability
SELECT count(*) AS reference_rows, count(DISTINCT npi) AS distinct_npis,
    count_if(npi_deactivation_date IS NOT NULL) AS deactivation_values,
    count_if(npi_reactivation_date IS NOT NULL) AS reactivation_values,
    count_if(replacement_npi IS NOT NULL) AS replacement_values,
    count_if(npi_deactivation_reason_code IS NOT NULL) AS reason_values,
    count_if(nullif(trim(npi_deactivation_date), '') IS NOT NULL AND try_cast(npi_deactivation_date AS date) IS NULL) AS invalid_deactivation_dates,
    count_if(nullif(trim(npi_reactivation_date), '') IS NOT NULL AND try_cast(npi_reactivation_date AS date) IS NULL) AS invalid_reactivation_dates
FROM iceberg.npi.nppes_npidata_latest

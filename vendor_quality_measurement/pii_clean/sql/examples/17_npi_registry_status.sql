SELECT DISTINCT
    source,
    npi,
    npi_registry_status AS status,
    npi_registry_deactivation_date AS deactivated_on,
    npi_registry_reactivation_date AS reactivated_on,
    array_distinct(transform(npi_registry_lifecycle_evidence,
        evidence -> evidence.replacement_npi)) AS raw_replacements,
    npi_registry_status_reason AS reason,
    npi_registry_status_as_of_day AS evaluated_on
FROM iceberg.jteixeira_ipa.pii_clean
WHERE source = 'endato'
  AND npi IN ('1215977517', '1295334530', '1376022061',
              '1588945042', '1871599357', '1962620666')
ORDER BY npi

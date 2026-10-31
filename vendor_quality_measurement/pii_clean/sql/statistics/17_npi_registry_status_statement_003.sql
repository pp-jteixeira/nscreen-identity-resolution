-- Statistics over published evidence in iceberg.jteixeira_ipa.pii_clean FOR VERSION AS OF 8811920360682490090.
-- Reference evidence and evaluation dates come from the stored publication.
SELECT source, npi_registry_status, npi_registry_status_reason,
       count(*) AS metric_rows, count(DISTINCT metric_row_id) AS unique_metric_rows,
       count(DISTINCT ROW(email, npi)) AS distinct_links,
       count(DISTINCT npi) AS distinct_npis
FROM iceberg.jteixeira_ipa.pii_clean FOR VERSION AS OF 8811920360682490090
GROUP BY source, npi_registry_status, npi_registry_status_reason
ORDER BY source, npi_registry_status, npi_registry_status_reason

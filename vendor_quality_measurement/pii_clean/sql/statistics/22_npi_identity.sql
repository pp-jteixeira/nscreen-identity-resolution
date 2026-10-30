-- Each vendor/NPI contributes once to identifier counts and carries its retained record count.
WITH measured AS (SELECT * FROM iceberg.jteixeira_ipa.pii_clean), npis AS (
    SELECT source, npi, npi_identity_as_of_day, npi_structure_reason, npi_entity_type,
           npi_entity_type_reason, count(*) AS metric_rows
    FROM measured
    GROUP BY source, npi, npi_identity_as_of_day, npi_structure_reason, npi_entity_type, npi_entity_type_reason
), outcomes AS (
    SELECT n.*, d.dimension, CASE d.dimension WHEN 'structure' THEN npi_structure_reason
           WHEN 'entity_type' THEN npi_entity_type ELSE npi_entity_type_reason END AS outcome
    FROM npis n CROSS JOIN (VALUES ('structure'), ('entity_type'), ('entity_reason')) AS d(dimension)
), grouped AS (
    SELECT source, npi_identity_as_of_day, dimension, outcome, sum(metric_rows) AS metric_rows,
           count(*) AS distinct_npis
    FROM outcomes GROUP BY source, npi_identity_as_of_day, dimension, outcome
)
SELECT *, sum(metric_rows) OVER (PARTITION BY source, npi_identity_as_of_day, dimension) AS vendor_metric_rows,
       sum(distinct_npis) OVER (PARTITION BY source, npi_identity_as_of_day, dimension) AS vendor_distinct_npis,
       100e0 * metric_rows / sum(metric_rows) OVER (PARTITION BY source, npi_identity_as_of_day, dimension) AS metric_row_pct,
       100e0 * distinct_npis / sum(distinct_npis) OVER (PARTITION BY source, npi_identity_as_of_day, dimension) AS distinct_npi_pct
FROM grouped ORDER BY source, npi_identity_as_of_day, dimension, outcome

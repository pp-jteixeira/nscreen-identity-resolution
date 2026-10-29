SELECT 'healthlink' AS source, 'iceberg.thirdparty.healthlink_email' AS source_table, min(partition.day) AS first_partition, max(partition.day) AS last_partition, count(*) AS partition_count,
       sum(record_count) AS metadata_records, sum(total_size) AS metadata_bytes
FROM iceberg.thirdparty."healthlink_email$partitions"
UNION ALL
SELECT 'quantummedica' AS source, 'iceberg.thirdparty.quantummedica_hcpdata' AS source_table, min(partition.day) AS first_partition, max(partition.day) AS last_partition, count(*) AS partition_count,
       sum(record_count) AS metadata_records, sum(total_size) AS metadata_bytes
FROM iceberg.thirdparty."quantummedica_hcpdata$partitions"
UNION ALL
SELECT 'medscape' AS source, 'iceberg.thirdparty.medscape_pii_global' AS source_table, min(partition.day) AS first_partition, max(partition.day) AS last_partition, count(*) AS partition_count,
       sum(record_count) AS metadata_records, sum(total_size) AS metadata_bytes
FROM iceberg.thirdparty."medscape_pii_global$partitions"
UNION ALL
SELECT 'haymarket' AS source, 'iceberg.thirdparty.haymarket_npi' AS source_table, min(partition.day) AS first_partition, max(partition.day) AS last_partition, count(*) AS partition_count,
       sum(record_count) AS metadata_records, sum(total_size) AS metadata_bytes
FROM iceberg.thirdparty."haymarket_npi$partitions"
UNION ALL
SELECT 'endato' AS source, 'iceberg.thirdparty.endato_pii' AS source_table, CAST(NULL AS varchar) AS first_partition, CAST(NULL AS varchar) AS last_partition, CAST(NULL AS bigint) AS partition_count,
       sum(record_count) AS metadata_records, sum(total_size) AS metadata_bytes
FROM iceberg.thirdparty."endato_pii$partitions"
UNION ALL
SELECT 'drdb' AS source, 'iceberg.thirdparty.drdb_npi' AS source_table, CAST(NULL AS varchar) AS first_partition, CAST(NULL AS varchar) AS last_partition, CAST(NULL AS bigint) AS partition_count,
       sum(record_count) AS metadata_records, sum(total_size) AS metadata_bytes
FROM iceberg.thirdparty."drdb_npi$partitions"
UNION ALL
SELECT 'drdb' AS source, 'iceberg.thirdparty.npi_enrich_emails_hashlower' AS source_table, CAST(NULL AS varchar) AS first_partition, CAST(NULL AS varchar) AS last_partition, CAST(NULL AS bigint) AS partition_count,
       sum(record_count) AS metadata_records, sum(total_size) AS metadata_bytes
FROM iceberg.thirdparty."npi_enrich_emails_hashlower$partitions"
UNION ALL
SELECT 'rocketreach' AS source, 'iceberg.npi.rocket_reach_npi_lookup' AS source_table, CAST(NULL AS varchar) AS first_partition, CAST(NULL AS varchar) AS last_partition, CAST(NULL AS bigint) AS partition_count,
       sum(record_count) AS metadata_records, sum(total_size) AS metadata_bytes
FROM iceberg.npi."rocket_reach_npi_lookup$partitions"
ORDER BY source, source_table

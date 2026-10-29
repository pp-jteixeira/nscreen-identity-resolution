-- Independent self-replacement check
SELECT count(*) AS reported_replacements, count_if(npi = replacement_npi) AS self_replacements,
 count_if(npi <> replacement_npi) AS other_replacements
FROM iceberg.npi.nppes_npidata_latest WHERE replacement_npi IS NOT NULL

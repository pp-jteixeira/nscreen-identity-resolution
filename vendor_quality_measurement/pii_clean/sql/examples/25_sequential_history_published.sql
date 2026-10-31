SELECT source,email,count(*) AS metric_rows,
       array_sort(array_agg(DISTINCT npi)) AS retained_npis,
       max(sequence_as_of_day) AS as_of_day,max(n_versions_observed) AS versions,
       max(n_npis_window) AS dated_npis,max(n_npi_changes) AS changes,
       max(n_swaps) AS swaps,max(n_flipbacks) AS flipbacks,
       bool_or(stability_history_sufficient) AS sufficient_history
FROM iceberg.jteixeira_ipa.pii_clean FOR VERSION AS OF 8811920360682490090
WHERE source='healthlink' AND email='jjacobson@mchswecare.com'
GROUP BY source,email

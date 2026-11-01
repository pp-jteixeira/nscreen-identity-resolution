-- Executed on the verified name-evidence core, October 31 2026
-- Classes overlap at record grain and must not be summed as disjoint populations
WITH records AS (
    SELECT source, vendor_registry_match_classes, vendor_name_matches_registry_name, name_match_evidence
    FROM iceberg.jteixeira_ipa.pii__int_pii__metrics FOR VERSION AS OF 3003274000539755025
), totals AS (
    SELECT source, count(*) AS metric_records,
           count_if(cardinality(vendor_registry_match_classes) > 1) AS records_with_multiple_classes,
           count_if(cardinality(name_match_evidence) > 1) AS records_with_multiple_comparisons
    FROM records
    GROUP BY source
), classes AS (
    SELECT source, match_class, count(*) AS records_with_class,
           count_if(cardinality(vendor_registry_match_classes) > 1) AS records_with_other_classes,
           count_if(vendor_name_matches_registry_name) AS records_with_true_aggregate
    FROM records
    CROSS JOIN UNNEST(vendor_registry_match_classes) AS c(match_class)
    GROUP BY source, match_class
)
SELECT c.source, c.match_class, t.metric_records, c.records_with_class,
       round(100.0 * c.records_with_class / t.metric_records, 6) AS percent_of_source_records,
       c.records_with_other_classes, c.records_with_true_aggregate,
       t.records_with_multiple_classes, t.records_with_multiple_comparisons
FROM classes c
JOIN totals t ON c.source = t.source
ORDER BY c.source, c.match_class

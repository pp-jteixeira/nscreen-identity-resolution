-- Executed on the verified name-evidence core, October 31 2026
-- Classes overlap within a link and must not be summed as disjoint populations
WITH stored AS (
    SELECT source, vendor_registry_match_classes, vendor_name_matches_registry_name, name_match_evidence
    FROM iceberg.jteixeira_ipa.pii__int_pii__metrics
), totals AS (
    SELECT source, count(*) AS links_total,
           count_if(cardinality(vendor_registry_match_classes) > 1) AS links_with_multiple_classes,
           count_if(cardinality(name_match_evidence) > 1) AS links_with_multiple_comparisons
    FROM stored
    GROUP BY source
), classes AS (
    SELECT source, match_class, count(*) AS links_with_class,
           count_if(cardinality(vendor_registry_match_classes) > 1) AS links_with_other_classes,
           count_if(vendor_name_matches_registry_name) AS links_with_true_aggregate
    FROM stored
    CROSS JOIN UNNEST(vendor_registry_match_classes) AS c(match_class)
    GROUP BY source, match_class
)
SELECT c.source, c.match_class, t.links_total, c.links_with_class,
       round(100.0 * c.links_with_class / t.links_total, 6) AS percent_of_source_links,
       c.links_with_other_classes, c.links_with_true_aggregate,
       t.links_with_multiple_classes, t.links_with_multiple_comparisons
FROM classes c
JOIN totals t ON c.source = t.source
ORDER BY c.source, c.match_class

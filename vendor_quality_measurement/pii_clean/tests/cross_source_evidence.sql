SELECT source, count(*) AS failing_metric_rows
FROM {{ ref(var('metric_model')) }}
WHERE cross_source_evidence_version IS DISTINCT FROM 'cross_source_evidence_v1'
   OR xsrc_npi_agree_sources IS NULL OR xsrc_npi_disagree_sources IS NULL OR xsrc_state_agree_sources IS NULL
   OR xsrc_state_disagree_sources IS NULL OR xsrc_name_agree_sources IS NULL OR xsrc_name_disagree_sources IS NULL
   OR contains(xsrc_npi_agree_sources, source) OR contains(xsrc_npi_disagree_sources, source)
   OR cardinality(array_intersect(xsrc_npi_agree_sources, xsrc_npi_disagree_sources)) > 0
   OR cardinality(array_intersect(xsrc_state_agree_sources, xsrc_npi_agree_sources)) <> cardinality(xsrc_state_agree_sources)
   OR cardinality(array_intersect(xsrc_state_disagree_sources, xsrc_npi_agree_sources)) <> cardinality(xsrc_state_disagree_sources)
   OR cardinality(array_intersect(xsrc_name_agree_sources, xsrc_npi_agree_sources)) <> cardinality(xsrc_name_agree_sources)
   OR cardinality(array_intersect(xsrc_name_disagree_sources, xsrc_npi_agree_sources)) <> cardinality(xsrc_name_disagree_sources)
   OR cardinality(array_intersect(xsrc_state_agree_sources, xsrc_state_disagree_sources)) > 0
   OR cardinality(array_intersect(xsrc_name_agree_sources, xsrc_name_disagree_sources)) > 0
   OR xsrc_npi_agree_count <> cardinality(xsrc_npi_agree_sources) OR xsrc_npi_disagree_count <> cardinality(xsrc_npi_disagree_sources)
   OR xsrc_state_agree_count <> cardinality(xsrc_state_agree_sources) OR xsrc_state_disagree_count <> cardinality(xsrc_state_disagree_sources)
   OR xsrc_name_agree_count <> cardinality(xsrc_name_agree_sources) OR xsrc_name_disagree_count <> cardinality(xsrc_name_disagree_sources)
   OR xsrc_email_source_count <> xsrc_npi_agree_count + xsrc_npi_disagree_count
GROUP BY source

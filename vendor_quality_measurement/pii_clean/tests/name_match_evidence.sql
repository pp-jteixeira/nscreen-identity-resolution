WITH checked AS (
    SELECT *,
           CASE WHEN any_match(name_match_evidence, x -> x.email_matches_source_name = true) THEN true
                WHEN any_match(name_match_evidence, x -> x.email_matches_source_name = false) THEN false END AS explained_source_match,
           CASE WHEN any_match(name_match_evidence, x -> x.email_matches_registry_name = true) THEN true
                WHEN any_match(name_match_evidence, x -> x.email_matches_registry_name = false) THEN false END AS explained_registry_match,
           CASE WHEN any_match(name_match_evidence, x -> x.vendor_name_matches_registry_name = true) THEN true
                WHEN any_match(name_match_evidence, x -> x.vendor_name_matches_registry_name = false) THEN false END AS explained_vendor_match
    FROM {{ ref(var('metric_model')) }}
)
SELECT source, metric_row_id
FROM checked
WHERE name_match_evidence IS NULL OR cardinality(name_match_evidence) = 0
   OR cardinality(name_match_evidence) <> cardinality(array_distinct(name_match_evidence))
   OR vendor_registry_match_classes IS DISTINCT FROM array_sort(array_distinct(transform(name_match_evidence, x -> x.match_class)))
   OR email_matches_source_name IS DISTINCT FROM explained_source_match
   OR email_matches_registry_name IS DISTINCT FROM explained_registry_match
   OR vendor_name_matches_registry_name IS DISTINCT FROM explained_vendor_match
   OR name_match_evaluated_at IS NULL
   OR name_match_definition_version IS DISTINCT FROM 'stored_name_comparisons_v1'
   OR any_match(name_match_evidence, x -> x IS NULL OR x.match_class IS NULL
       OR x.match_class NOT IN ('exact', 'nickname', 'token', 'edit', 'first_only', 'last_only', 'none', 'unknown')
       OR x.first_name_match_kind IS NULL OR x.last_name_match_kind IS NULL
       OR x.first_name_match_kind NOT IN ('exact', 'nickname', 'token', 'edit', 'none', 'unknown')
       OR x.last_name_match_kind NOT IN ('exact', 'token', 'edit', 'none', 'unknown')
       OR x.match_class IS DISTINCT FROM CASE
          WHEN NOT {{ usable_name('x.source_first_name', 'x.source_last_name') }}
            OR NOT {{ usable_name('x.registry_first_name', 'x.registry_last_name') }} THEN 'unknown'
          WHEN x.last_name_match_kind = 'none' AND x.first_name_match_kind <> 'none' THEN 'first_only'
          WHEN x.first_name_match_kind = 'none' AND x.last_name_match_kind <> 'none' THEN 'last_only'
          WHEN x.first_name_match_kind = 'none' OR x.last_name_match_kind = 'none' THEN 'none'
          WHEN x.first_name_match_kind = 'edit' OR x.last_name_match_kind = 'edit' THEN 'edit'
          WHEN x.first_name_match_kind = 'nickname' THEN 'nickname'
          WHEN x.first_name_match_kind = 'token' OR x.last_name_match_kind = 'token' THEN 'token'
          ELSE 'exact' END
       OR (x.match_class = 'unknown') IS DISTINCT FROM
          (x.first_name_match_kind = 'unknown' AND x.last_name_match_kind = 'unknown')
       OR (x.match_class <> 'unknown' AND
          (x.first_name_match_kind = 'unknown' OR x.last_name_match_kind = 'unknown'))
       OR x.vendor_name_matches_registry_name IS DISTINCT FROM
          CASE WHEN x.match_class = 'unknown' THEN CAST(NULL AS boolean)
               ELSE x.match_class IN ('exact', 'nickname', 'token', 'edit') END)

-- Independently reconstruct day-specific peers from stored vendor evidence.
WITH records AS (
    SELECT * FROM {{ ref(var('metric_model')) }}
), daily AS (
    SELECT m.source, m.email, m.npi, m.metric_row_id, m.conflict_days, m.has_conflict_linkage,
           (element_at(m.vendor_professional_evidence, u.evidence_index)).evidence_day AS evidence_day,
           (element_at(m.vendor_professional_evidence, u.evidence_index)).specialties AS specialties,
           (element_at(m.vendor_professional_evidence, u.evidence_index)).professions AS professions
    FROM records m CROSS JOIN UNNEST(sequence(1, cardinality(m.vendor_professional_evidence))) AS u(evidence_index)
    WHERE cardinality(m.vendor_professional_evidence) > 0
), peers AS (
    SELECT a.source, a.metric_row_id,
           {% for kind, field in [('specialty', 'specialties'), ('profession', 'professions')] %}
           CASE WHEN cardinality(a.{{ field }}) > 0 AND cardinality(b.{{ field }}) > 0
                THEN arrays_overlap(a.{{ field }}, b.{{ field }}) END AS shares_{{ kind }},
           CAST(ROW(b.npi, b.metric_row_id, a.evidence_day, a.{{ field }}, b.{{ field }},
                    array_sort(array_intersect(a.{{ field }}, b.{{ field }})),
                    CASE WHEN cardinality(a.{{ field }}) > 0 AND cardinality(b.{{ field }}) > 0
                         THEN arrays_overlap(a.{{ field }}, b.{{ field }}) END)
               AS ROW(npi varchar, metric_row_id varchar, evidence_day date, own_values array(varchar),
                      peer_values array(varchar), shared_values array(varchar), shares_{{ kind }} boolean)) AS {{ kind }}_comparison{% if not loop.last %},{% endif %}
           {% endfor %}
    FROM daily a JOIN daily b ON a.source = b.source AND a.email = b.email AND a.npi <> b.npi
        AND a.has_conflict_linkage AND b.has_conflict_linkage
        AND (a.source IN ('endato', 'rocketreach', 'drdb')
             OR (a.evidence_day = b.evidence_day AND contains(a.conflict_days, a.evidence_day)
                 AND contains(b.conflict_days, b.evidence_day)))
), expected AS (
    SELECT source, metric_row_id,
           {% for kind in ['specialty', 'profession'] %}
           CASE WHEN count_if(shares_{{ kind }}) > 0 THEN true
                WHEN count_if(shares_{{ kind }} IS NULL) > 0 THEN CAST(NULL AS boolean)
                ELSE false END AS {{ kind }}_flag,
           array_sort(array_distinct(array_agg({{ kind }}_comparison))) AS {{ kind }}_comparisons{% if not loop.last %},{% endif %}
           {% endfor %}
    FROM peers GROUP BY source, metric_row_id
)
SELECT m.source, count(*) AS failing_metric_rows
FROM records m LEFT JOIN expected e ON m.source = e.source AND m.metric_row_id = e.metric_row_id
WHERE m.vendor_professional_evidence IS NULL OR cardinality(m.vendor_professional_evidence) = 0
   OR m.vendor_professional_definition_version IS DISTINCT FROM 'vendor_labels_exact_same_day_v1'
   OR m.source_vendor_specialty_values IS DISTINCT FROM array_sort(array_distinct(flatten(transform(m.vendor_professional_evidence, v -> v.specialties))))
   OR m.source_vendor_profession_values IS DISTINCT FROM array_sort(array_distinct(flatten(transform(m.vendor_professional_evidence, v -> v.professions))))
   OR array_sort(array_distinct(filter(transform(m.vendor_professional_evidence, v -> v.evidence_day), d -> d IS NOT NULL))) IS DISTINCT FROM m.observed_days
   {% for kind in ['specialty', 'profession'] %}
   OR m.conflicting_npis_share_vendor_{{ kind }} IS DISTINCT FROM e.{{ kind }}_flag
   OR m.conflicting_npi_vendor_{{ kind }}_comparisons IS DISTINCT FROM coalesce(e.{{ kind }}_comparisons, CAST(ARRAY[] AS {{ vendor_professional_comparison_type(kind) }}))
   {% endfor %}
GROUP BY m.source

-- Enrich each stored source independently with domain, cross-source and cookie evidence, then combine the complete record outputs.
{% set cookie_sources = var('cookie_sources', ['healthlink', 'quantummedica', 'medscape', 'endato', 'rocketreach', 'drdb', 'haymarket']) %}
WITH
{% for cookie_source in cookie_sources %}
source_{{ loop.index }} AS (
WITH core_metrics AS (
    SELECT * FROM {{ ref('int_pii__metrics') }} WHERE source = '{{ cookie_source }}'
), domained AS (
{{ domain_evidence_records('core_metrics') }}
), crossed AS (
{{ cross_source_evidence_records('domained', ref('int_pii__metrics')) }}
), enriched AS (
{{ cookie_location_records('crossed') }}
)
SELECT
{% for field in metric_columns(include_cookie=true) %}
    e.{{ field }}{% if not loop.last %},{% endif %}
{% endfor %}
FROM enriched e
){% if not loop.last %},{% endif %}
{% endfor %}
{% for cookie_source in cookie_sources %}
SELECT * FROM source_{{ loop.index }}{% if not loop.last %} UNION ALL{% endif %}
{% endfor %}

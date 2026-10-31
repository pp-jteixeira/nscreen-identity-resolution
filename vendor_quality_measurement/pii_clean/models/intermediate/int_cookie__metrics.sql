-- Compute actual cookie metrics after core attribution has been materialized.
WITH core_metrics AS (
    SELECT * FROM {{ ref('int_pii__metrics') }}
), enriched AS (
{{ cookie_location_records('core_metrics') }}
)
SELECT
{% for field in metric_columns(include_cookie=true) %}
    e.{{ field }}{% if not loop.last %},{% endif %}
{% endfor %}
FROM enriched e

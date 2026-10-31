-- Materialized union of core vendor metrics. No cookie work runs here.
{% for vendor in ['healthlink', 'quantummedica', 'medscape', 'endato', 'rocketreach', 'drdb', 'haymarket'] %}
SELECT * FROM {{ ref('int_' ~ vendor ~ '__metrics') }}
{% if not loop.last %}UNION ALL{% endif %}
{% endfor %}

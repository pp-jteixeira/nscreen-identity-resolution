-- Preserve every vendor metric row and every column. No deduplication or scoring.
{% for vendor in ['healthlink', 'quantummedica', 'medscape', 'endato', 'rocketreach', 'drdb', 'haymarket'] %}
SELECT * FROM {{ ref('int_' ~ vendor ~ '__metrics') }}
{% if not loop.last %}UNION ALL{% endif %}
{% endfor %}

{% macro clean_text(value) -%}
nullif(trim(cast({{ value }} AS varchar)), '')
{%- endmacro %}

{% macro clean_email(value) -%}
lower({{ clean_text(value) }})
{%- endmacro %}

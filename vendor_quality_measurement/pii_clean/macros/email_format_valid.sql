{% macro email_format_valid(email) -%}
regexp_like({{ email }}, '^[a-z0-9._%+-]+@[a-z0-9.-]+[.][a-z]{2,}$')
{%- endmacro %}

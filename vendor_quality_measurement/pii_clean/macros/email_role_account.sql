{% macro email_role_account(col) -%}
    coalesce(regexp_extract({{ col }}, '^([^@]+)@', 1) in ('admin', 'info', 'office', 'contact', 'frontdesk', 'billing', 'reception', 'appointments', 'scheduling', 'support', 'noreply'), false)
{%- endmacro %}

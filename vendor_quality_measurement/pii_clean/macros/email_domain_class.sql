{# Ordered domain-text heuristic. Format validity and ownership are separate. #}
{% macro email_domain_class(email) -%}
    case
        when {{ email }} is null or position('@' in {{ email }}) = 0 then 'unknown'
        when regexp_like(lower(regexp_extract({{ email }}, '@(.*)$', 1)), '(\.(edu|gov|mil)$)|(\.(edu|ac)\.[a-z]{2}$)|(hospital|health|clinic|medical|medicine|physician|pharm|dental|surgery|univ|ortho|cardio|derm|urgent|rehab|oncolog|pediatric)') then 'institutional'
        when regexp_like(lower(regexp_extract({{ email }}, '@(.*)$', 1)), '^(gmail|googlemail|yahoo|ymail|hotmail|outlook|live|msn|aol|icloud|me|mac|comcast|verizon|att|sbcglobal|bellsouth|cox|charter|earthlink|protonmail|proton|mail|gmx|optonline|juno|netzero|roadrunner|frontier|windstream|centurylink|aim|rocketmail)\.') then 'free'
        else 'custom'
    end
{%- endmacro %}

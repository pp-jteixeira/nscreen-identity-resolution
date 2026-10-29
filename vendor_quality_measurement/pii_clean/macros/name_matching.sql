{# Name normalization and fuzzy comparisons; no weights or scores. #}
{% macro nt(expr) -%}
    case when lower(trim({{ expr }})) in ('', 'null', 'nan', chr(92) || 'n') then null else {{ expr }} end
{%- endmacro %}

{% macro squash_ws(expr) -%}
    trim(regexp_replace(translate({{ expr }}, chr(9) || chr(10) || chr(13) || chr(160), '    '), ' +', ' '))
{%- endmacro %}

{% macro strip_accents(expr) -%}
    translate({{ expr }}, 'ÁÀÂÄÃÅĀÇĆČÉÈÊËĒĖĘÍÌÎÏĪÑŃÓÒÔÖÕØŌŚŠÚÙÛÜŪÝŸŽŹŻ', 'AAAAAAACCCEEEEEEEIIIIINNOOOOOOOSSUUUUUYYZZZ')
{%- endmacro %}

{% macro norm_name(expr) -%}
    nullif({{ squash_ws("regexp_replace(" ~ strip_accents("upper(" ~ squash_ws(nt(expr)) ~ ")") ~ ", '[^A-Z' || chr(39) || ' -]', '')") }}, '')
{%- endmacro %}

{% macro pos(haystack, needle) -%}
    {%- if var('dialect', 'trino') == 'trino' -%}strpos({{ haystack }}, {{ needle }}){%- else -%}instr({{ haystack }}, {{ needle }}){%- endif -%}
{%- endmacro %}

{% macro starts(a, b) -%}
    {%- if var('dialect', 'trino') == 'trino' -%}starts_with({{ a }}, {{ b }}){%- else -%}startswith({{ a }}, {{ b }}){%- endif -%}
{%- endmacro %}

{% macro name_email_match(local, f, l) -%}
    case
        when coalesce({{ f }}, '') = '' or length(coalesce({{ l }}, '')) < 2 then null
        when length({{ f }}) >= 2 and length({{ l }}) >= 2 and {{ pos(local, f) }} > 0 and {{ pos(local, l) }} > 0 then true
        when length({{ l }}) >= 2 and length({{ local }}) > length({{ l }})
            and (
                ({{ starts(local, "substr(" ~ f ~ ", 1, 1)") }} and substr({{ local }}, -length({{ l }})) = {{ l }})
                or ({{ starts(local, l) }} and substr({{ local }}, -1) = substr({{ f }}, 1, 1))
            ) then true
        else false
    end
{%- endmacro %}

{% macro lev(a, b) -%}
    {%- if var('dialect', 'trino') == 'trino' -%}levenshtein_distance({{ a }}, {{ b }}){%- else -%}levenshtein({{ a }}, {{ b }}){%- endif -%}
{%- endmacro %}

{% macro any_in(arr, lambda_var, cond) -%}
    {%- if var('dialect', 'trino') == 'trino' -%}any_match({{ arr }}, {{ lambda_var }} -> {{ cond }}){%- else -%}exists({{ arr }}, {{ lambda_var }} -> {{ cond }}){%- endif -%}
{%- endmacro %}

{% macro letters(expr) -%}
    regexp_replace({{ expr }}, '[^A-Z]', '')
{%- endmacro %}

{% macro edit_close(a, b) -%}
    (
        (least(length({{ a }}), length({{ b }})) >= 5 and {{ lev(a, b) }} <= 1)
        or (least(length({{ a }}), length({{ b }})) >= 8 and {{ lev(a, b) }} <= 2)
    )
{%- endmacro %}

{% macro prefix_close(a, b) -%}
    (
        least(length({{ a }}), length({{ b }})) >= 3
        and (substr({{ a }}, 1, length({{ b }})) = {{ b }} or substr({{ b }}, 1, length({{ a }})) = {{ a }})
    )
{%- endmacro %}

{% macro last_similar(la, lb) -%}
    (
        {{ letters(la) }} = {{ letters(lb) }}
        or arrays_overlap(split(regexp_replace({{ la }}, '[- ]+', ' '), ' '), split(regexp_replace({{ lb }}, '[- ]+', ' '), ' '))
        or {{ edit_close(letters(la), letters(lb)) }}
    )
{%- endmacro %}

{% macro first_similar(fa_set, fa, fb_set, fb) -%}
    (
        arrays_overlap({{ fa_set }}, {{ fb_set }})
        or {{ prefix_close("split_part(" ~ fa ~ ", ' ', 1)", "split_part(" ~ fb ~ ", ' ', 1)") }}
        or {{ edit_close(letters("split_part(" ~ fa ~ ", ' ', 1)"), letters("split_part(" ~ fb ~ ", ' ', 1)")) }}
    )
{%- endmacro %}

{% macro last_kind(la, lb) -%}
    case
        when {{ letters(la) }} = {{ letters(lb) }} then 'exact'
        when arrays_overlap(split(regexp_replace({{ la }}, '[- ]+', ' '), ' '), split(regexp_replace({{ lb }}, '[- ]+', ' '), ' ')) then 'token'
        when {{ edit_close(letters(la), letters(lb)) }} then 'edit'
        else 'none'
    end
{%- endmacro %}

{% macro first_kind(fa_set, fa, fb_set, fb) -%}
    case
        when {{ fa }} = {{ fb }} then 'exact'
        when split_part({{ fa }}, ' ', 1) = split_part({{ fb }}, ' ', 1)
            or arrays_overlap(split({{ fa }}, ' '), split({{ fb }}, ' '))
            or {{ prefix_close("split_part(" ~ fa ~ ", ' ', 1)", "split_part(" ~ fb ~ ", ' ', 1)") }} then 'token'
        when arrays_overlap({{ fa_set }}, {{ fb_set }}) then 'nickname'
        when {{ edit_close(letters("split_part(" ~ fa ~ ", ' ', 1)"), letters("split_part(" ~ fb ~ ", ' ', 1)")) }} then 'edit'
        else 'none'
    end
{%- endmacro %}

{% macro name_match_class(fa_set, fa, la, fb_set, fb, lb) -%}
    case
        when {{ fa }} is null or {{ la }} is null or {{ fb }} is null or {{ lb }} is null then null
        else
            case
                when lk = 'none' and fk <> 'none' then 'married'
                when lk = 'none' or fk = 'none' then 'none'
                when lk = 'edit' or fk = 'edit' then 'edit'
                when fk = 'nickname' then 'nickname'
                when lk = 'token' or fk = 'token' then 'token'
                else 'exact'
            end
    end
{%- endmacro %}

{% macro name_email_match_fuzzy(local, f_set, l) -%}
    case
        when cardinality({{ f_set }}) = 0 or length({{ letters("coalesce(" ~ l ~ ", '')") }}) < 2
            or not {{ any_in(f_set, 'fv', "length(" ~ letters('fv') ~ ") >= 1") }} then null
        when {{ any_in(f_set, 'fv', "(" ~ name_email_match(local, "lower(" ~ letters('fv') ~ ")", "lower(" ~ letters(l) ~ ")") ~ ")") }} then true
        when length({{ local }}) >= 6 and {{ any_in(f_set, 'fv', "("
            ~ lev(local, "lower(" ~ letters('fv') ~ ") || lower(" ~ letters(l) ~ ")") ~ " <= 1 or "
            ~ lev(local, "lower(" ~ letters(l) ~ ") || lower(" ~ letters('fv') ~ ")") ~ " <= 1 or "
            ~ lev(local, "substr(lower(" ~ letters('fv') ~ "), 1, 1) || lower(" ~ letters(l) ~ ")") ~ " <= 1 or "
            ~ lev(local, "lower(" ~ letters(l) ~ ") || substr(lower(" ~ letters('fv') ~ "), 1, 1)") ~ " <= 1)") }} then true
        else false
    end
{%- endmacro %}

{% macro usable_name(first, last) -%}
coalesce(length({{ letters(first) }}) >= 1 AND length({{ letters(last) }}) >= 2, false)
{%- endmacro %}

{% macro link_name_metrics(input_model, detail=false, record_grain=false, input_relation=none, include_source_names=false) -%}
WITH expanded AS (
    SELECT s.*,
           array_distinct(filter(concat(ARRAY[s.first_name], coalesce(v.variants, CAST(ARRAY[] AS array(varchar)))), x -> x IS NOT NULL)) AS first_set,
           regexp_replace(lower(regexp_extract(s.email, '^([^@]*)@', 1)), '[^a-z]', '') AS local_letters
    FROM {{ input_relation if input_relation is not none else ref(input_model) }} s
    LEFT JOIN {{ ref('int_name__variants') }} v ON split_part(s.first_name, ' ', 1) = v.first_name
), joined AS (
    SELECT s.*, r.npi IS NOT NULL AS registry_npi_present,
           r.first_name AS registry_first_name, r.last_name AS registry_last_name,
           coalesce(r.first_set, CAST(ARRAY[] AS array(varchar))) AS registry_first_set,
           {{ usable_name('s.first_name', 's.last_name') }} AS source_name_usable,
           {{ usable_name('r.first_name', 'r.last_name') }} AS registry_name_usable
    FROM expanded s
    LEFT JOIN {{ ref('int_npi__names') }} r ON s.npi = r.npi
), kinds AS (
    SELECT *,
           {{ last_kind('last_name', 'registry_last_name') }} AS lk,
           {{ first_kind('first_set', 'first_name', 'registry_first_set', 'registry_first_name') }} AS fk
    FROM joined
), evaluated AS (
    SELECT *,
           {{ name_email_match_fuzzy('local_letters', 'first_set', 'last_name') }} AS source_match,
           {{ name_email_match_fuzzy('local_letters', 'registry_first_set', 'registry_last_name') }} AS registry_match,
           CASE WHEN source_name_usable AND registry_name_usable THEN
             {{ name_match_class('first_set', 'first_name', 'last_name', 'registry_first_set', 'registry_first_name', 'registry_last_name') }} IN ('exact', 'nickname', 'token', 'edit')
           END AS vendor_registry_match
    FROM kinds
)
{% if detail %}
SELECT {% if record_grain %}metric_row_id, {% endif %}email, npi,
       first_name AS source_first_name, last_name AS source_last_name,
       registry_first_name, registry_last_name,
       first_set AS source_first_name_variants,
       registry_first_set AS registry_first_name_variants,
       local_letters AS email_local_letters,
       source_name_usable AS comparison_source_name_usable,
       registry_name_usable AS comparison_registry_name_usable,
       fk AS first_name_match_kind, lk AS last_name_match_kind,
       CASE WHEN NOT source_name_usable OR NOT registry_name_usable THEN 'unknown'
            WHEN lk = 'none' AND fk <> 'none' THEN 'first_only'
            WHEN fk = 'none' AND lk <> 'none' THEN 'last_only'
            ELSE {{ name_match_class('first_set', 'first_name', 'last_name', 'registry_first_set', 'registry_first_name', 'registry_last_name') }}
       END AS vendor_registry_match_class,
       source_match AS comparison_email_matches_source_name,
       registry_match AS comparison_email_matches_registry_name,
       vendor_registry_match AS comparison_vendor_name_matches_registry_name
FROM evaluated
{% else %}
SELECT {% if record_grain %}metric_row_id, {% endif %}email, npi,
       bool_or(source_match) AS email_matches_source_name,
       bool_or(registry_match) AS email_matches_registry_name,
       bool_or(vendor_registry_match) AS vendor_name_matches_registry_name,
       bool_or(source_name_usable) AS source_name_usable,
       bool_or(registry_name_usable) AS registry_name_usable,
       bool_or(registry_npi_present) AS registry_npi_present
       {% if include_source_names %},
       coalesce(array_sort(array_agg(DISTINCT CAST(ROW(first_name, last_name, array_sort(first_set))
           AS row(first_name varchar, last_name varchar, first_variants array(varchar))))
           FILTER (WHERE source_name_usable)), CAST(ARRAY[] AS {{ source_name_array_type() }})) AS source_name_values
       {% endif %}
FROM evaluated
GROUP BY {% if record_grain %}metric_row_id, {% endif %}email, npi
{% endif %}
{%- endmacro %}

{% macro debug_name_rows(metric_relation, comparison_relation) -%}
SELECT m.*,
       c.source_first_name, c.source_last_name,
       c.registry_first_name, c.registry_last_name,
       c.source_first_name_variants, c.registry_first_name_variants,
       c.email_local_letters,
       c.comparison_source_name_usable, c.comparison_registry_name_usable,
       c.first_name_match_kind, c.last_name_match_kind, c.vendor_registry_match_class,
       c.comparison_email_matches_source_name,
       c.comparison_email_matches_registry_name,
       c.comparison_vendor_name_matches_registry_name,
       to_hex(sha256(to_utf8(json_format(CAST(ROW(
           m.source, m.metric_row_id, c.source_first_name, c.source_last_name,
           c.registry_first_name, c.registry_last_name) AS json))))) AS debug_comparison_id,
       CAST(current_timestamp AS timestamp(6) with time zone) AS debug_built_at,
       'name_matching_debug_records_v1' AS debug_definition
FROM {{ metric_relation }} m
LEFT JOIN {{ comparison_relation }} c ON m.metric_row_id = c.metric_row_id
{%- endmacro %}

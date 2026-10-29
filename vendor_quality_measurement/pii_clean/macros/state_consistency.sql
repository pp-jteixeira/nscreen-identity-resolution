{# Recognized US states, DC and five territories; no fuzzy geography matching. #}
{% macro normalized_state(value) -%}
CASE upper(regexp_replace(trim(cast({{ value }} AS varchar)), '\s+', ' '))
    WHEN 'AL' THEN 'AL' WHEN 'ALABAMA' THEN 'AL'
    WHEN 'AK' THEN 'AK' WHEN 'ALASKA' THEN 'AK'
    WHEN 'AZ' THEN 'AZ' WHEN 'ARIZONA' THEN 'AZ'
    WHEN 'AR' THEN 'AR' WHEN 'ARKANSAS' THEN 'AR'
    WHEN 'CA' THEN 'CA' WHEN 'CALIFORNIA' THEN 'CA'
    WHEN 'CO' THEN 'CO' WHEN 'COLORADO' THEN 'CO'
    WHEN 'CT' THEN 'CT' WHEN 'CONNECTICUT' THEN 'CT'
    WHEN 'DE' THEN 'DE' WHEN 'DELAWARE' THEN 'DE'
    WHEN 'DC' THEN 'DC' WHEN 'DISTRICT OF COLUMBIA' THEN 'DC'
    WHEN 'FL' THEN 'FL' WHEN 'FLORIDA' THEN 'FL'
    WHEN 'GA' THEN 'GA' WHEN 'GEORGIA' THEN 'GA'
    WHEN 'HI' THEN 'HI' WHEN 'HAWAII' THEN 'HI'
    WHEN 'ID' THEN 'ID' WHEN 'IDAHO' THEN 'ID'
    WHEN 'IL' THEN 'IL' WHEN 'ILLINOIS' THEN 'IL'
    WHEN 'IN' THEN 'IN' WHEN 'INDIANA' THEN 'IN'
    WHEN 'IA' THEN 'IA' WHEN 'IOWA' THEN 'IA'
    WHEN 'KS' THEN 'KS' WHEN 'KANSAS' THEN 'KS'
    WHEN 'KY' THEN 'KY' WHEN 'KENTUCKY' THEN 'KY'
    WHEN 'LA' THEN 'LA' WHEN 'LOUISIANA' THEN 'LA'
    WHEN 'ME' THEN 'ME' WHEN 'MAINE' THEN 'ME'
    WHEN 'MD' THEN 'MD' WHEN 'MARYLAND' THEN 'MD'
    WHEN 'MA' THEN 'MA' WHEN 'MASSACHUSETTS' THEN 'MA'
    WHEN 'MI' THEN 'MI' WHEN 'MICHIGAN' THEN 'MI'
    WHEN 'MN' THEN 'MN' WHEN 'MINNESOTA' THEN 'MN'
    WHEN 'MS' THEN 'MS' WHEN 'MISSISSIPPI' THEN 'MS'
    WHEN 'MO' THEN 'MO' WHEN 'MISSOURI' THEN 'MO'
    WHEN 'MT' THEN 'MT' WHEN 'MONTANA' THEN 'MT'
    WHEN 'NE' THEN 'NE' WHEN 'NEBRASKA' THEN 'NE'
    WHEN 'NV' THEN 'NV' WHEN 'NEVADA' THEN 'NV'
    WHEN 'NH' THEN 'NH' WHEN 'NEW HAMPSHIRE' THEN 'NH'
    WHEN 'NJ' THEN 'NJ' WHEN 'NEW JERSEY' THEN 'NJ'
    WHEN 'NM' THEN 'NM' WHEN 'NEW MEXICO' THEN 'NM'
    WHEN 'NY' THEN 'NY' WHEN 'NEW YORK' THEN 'NY'
    WHEN 'NC' THEN 'NC' WHEN 'NORTH CAROLINA' THEN 'NC'
    WHEN 'ND' THEN 'ND' WHEN 'NORTH DAKOTA' THEN 'ND'
    WHEN 'OH' THEN 'OH' WHEN 'OHIO' THEN 'OH'
    WHEN 'OK' THEN 'OK' WHEN 'OKLAHOMA' THEN 'OK'
    WHEN 'OR' THEN 'OR' WHEN 'OREGON' THEN 'OR'
    WHEN 'PA' THEN 'PA' WHEN 'PENNSYLVANIA' THEN 'PA'
    WHEN 'RI' THEN 'RI' WHEN 'RHODE ISLAND' THEN 'RI'
    WHEN 'SC' THEN 'SC' WHEN 'SOUTH CAROLINA' THEN 'SC'
    WHEN 'SD' THEN 'SD' WHEN 'SOUTH DAKOTA' THEN 'SD'
    WHEN 'TN' THEN 'TN' WHEN 'TENNESSEE' THEN 'TN'
    WHEN 'TX' THEN 'TX' WHEN 'TEXAS' THEN 'TX'
    WHEN 'UT' THEN 'UT' WHEN 'UTAH' THEN 'UT'
    WHEN 'VT' THEN 'VT' WHEN 'VERMONT' THEN 'VT'
    WHEN 'VA' THEN 'VA' WHEN 'VIRGINIA' THEN 'VA'
    WHEN 'WA' THEN 'WA' WHEN 'WASHINGTON' THEN 'WA'
    WHEN 'WV' THEN 'WV' WHEN 'WEST VIRGINIA' THEN 'WV'
    WHEN 'WI' THEN 'WI' WHEN 'WISCONSIN' THEN 'WI'
    WHEN 'WY' THEN 'WY' WHEN 'WYOMING' THEN 'WY'
    WHEN 'AS' THEN 'AS' WHEN 'AMERICAN SAMOA' THEN 'AS'
    WHEN 'GU' THEN 'GU' WHEN 'GUAM' THEN 'GU'
    WHEN 'MP' THEN 'MP' WHEN 'NORTHERN MARIANA ISLANDS' THEN 'MP'
    WHEN 'PR' THEN 'PR' WHEN 'PUERTO RICO' THEN 'PR'
    WHEN 'VI' THEN 'VI' WHEN 'US VIRGIN ISLANDS' THEN 'VI'
    WHEN 'U.S. VIRGIN ISLANDS' THEN 'VI' WHEN 'VIRGIN ISLANDS' THEN 'VI'
END
{%- endmacro %}

{% macro state_values_from_payload(vendor, payload) -%}
{%- set field = 'address_state' if vendor == 'endato' else ('region' if vendor == 'rocketreach' else 'state') -%}
{%- set raw = "json_extract_scalar(" ~ payload ~ ", '$." ~ field ~ "')" -%}
{%- if vendor in ['medscape', 'rocketreach'] -%}
CASE WHEN
{% for field in ['country_code', 'country'] %}
    (nullif(trim(json_extract_scalar({{ payload }}, '$.{{ field }}')), '') IS NULL
     OR upper(trim(json_extract_scalar({{ payload }}, '$.{{ field }}')))
         IN ('US', 'USA', 'UNITED STATES', 'UNITED STATES OF AMERICA', 'PR', 'PUERTO RICO',
             'GU', 'GUAM', 'AS', 'AMERICAN SAMOA', 'MP', 'NORTHERN MARIANA ISLANDS',
             'VI', 'US VIRGIN ISLANDS', 'U.S. VIRGIN ISLANDS', 'VIRGIN ISLANDS'))
    {% if not loop.last %}AND{% endif %}
{% endfor %}
     THEN filter(ARRAY[{{ normalized_state(raw) }}], x -> x IS NOT NULL)
     ELSE CAST(ARRAY[] AS array(varchar)) END
{%- else -%}
filter(ARRAY[{{ normalized_state(raw) }}], x -> x IS NOT NULL)
{%- endif -%}
{%- endmacro %}

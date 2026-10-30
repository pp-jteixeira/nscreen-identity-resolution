# Email name count

**Principle:** count distinct usable normalized first/last-name pairs reported for an email within one vendor, across all retained history. This counts name spellings, not people.

**Where:** `iceberg.jteixeira_ipa.pii__int_<vendor>__metrics` and `iceberg.jteixeira_ipa.pii_clean`. Inputs: `source`, `email`, `source_name_values`; output: bigint `email_name_count`. Every row for the same vendor/email receives the same count, across all its NPIs.

## How it is computed

Combine usable `source_name_values` across each vendor/email into `email_names`, including all its NPIs. Remove repeated first/last-name pairs and count the remaining spellings:

```sql
cast(cardinality(array_distinct(transform(email_names,
    n -> ROW(n.first_name, n.last_name)))) AS bigint) AS email_name_count
```

Names use the existing uppercase, accent and whitespace normalization. A usable pair has at least one first-name letter and two last-name letters. Missing, partial and punctuation-only names do not contribute. Zero means no usable names were observed. Repeated records, email slots, dates and registry-name matches cannot inflate the count.

HealthLink uses its HCP-name reference by NPI across retained HCP history, without date alignment. Other vendors use their existing record name inputs; both DRDB feeds contribute. Registry names do not fill missing vendor names. `source_name_values` retains each record's normalized pairs and first-name variants for inspection.

## Real examples: contrasting outcomes

Selected real records, queried October 30, 2026, from `iceberg.jteixeira_ipa.pii_clean` at snapshot `8096642935433856886`. These examples explain outcomes; they are not prevalence estimates. `email_key` is a shortened SHA-256 label. `email_names` is an inspection helper collecting distinct normalized pairs across all retained records and NPIs for that vendor/email.

[Runnable example SQL](../../sql/examples/11_email_name_count.sql):

```sql
WITH selected AS (
    SELECT *
    FROM iceberg.jteixeira_ipa.pii_clean FOR VERSION AS OF 8096642935433856886
    WHERE (source = 'drdb' AND metric_row_id IN (
        '76F42EB2F2C6093316B5CDEF2587E5A52525DDC28EA8CF1B437507091D8AF857'))
       OR (source = 'endato' AND metric_row_id IN (
        '730FB3822EC1EB3855BF21A4E1C10C1F2788A9DAA943ED02124432207C2B0194'))
       OR (source = 'quantummedica' AND metric_row_id IN (
        '3DD35EF677E8852E5BADCA2E63D87755D8184021D9CBC395E23F6BBD95E7E8DE'))
), context_names AS (
    SELECT t.source, t.email,
           array_sort(array_distinct(flatten(array_agg(transform(t.source_name_values, n -> concat(n.first_name, ' ', n.last_name)))))) AS names
    FROM iceberg.jteixeira_ipa.pii_clean FOR VERSION AS OF 8096642935433856886 t
    JOIN (SELECT DISTINCT source, email FROM selected) k
      ON t.source = k.source AND t.email = k.email
    GROUP BY t.source, t.email
)
SELECT m.source,
       substr(to_hex(sha256(to_utf8(m.email))), 1, 12) AS email_key,
       m.email_npi_count,
       m.email_name_count,
       c.names AS email_names,
       m.email_npi_has_name_conflict
FROM selected m
LEFT JOIN context_names c ON m.source = c.source AND m.email = c.email
ORDER BY m.source, m.metric_row_id
```

**Result:** 3 rows.

| source | email_key | email_npi_count | email_name_count | email_names | email_npi_has_name_conflict |
|---|---|---|---|---|---|
| drdb | 6B7B55A02822 | 1 | 2 | [KEITH LONG, KEITHLINTON LONG] | false |
| endato | 87CB8A58EDB9 | 2 | 2 | [ANGRETTE MCCLOSKEY, TAHANI MCCLOSKEY] | false |
| quantummedica | EBE10F43F336 | 1 | 0 | [] | NULL |

**What differentiates these cases:** Different normalized spellings count separately even when fuzzy rules agree. An email-level name count can also span different NPIs. Zero means no usable vendor names; registry names do not fill that gap. Name count measures spellings, not people.

Stored indicators are unchanged by display helpers. Reproduction requires the pinned snapshot to remain available.

## Statistics by vendor

[Statistics SQL](../../sql/statistics/11_email_name_count.sql) was executed against the current published `iceberg.jteixeira_ipa.pii_clean` table.

Measured **October 29, 2026**, across all retained source history. Extraction completed at `2026-10-29T17:20:35.379565+01:00`. Published snapshot `6346435822181920647` remained unchanged throughout the six-query refresh. Counts are exact. Percentages use each vendor's distinct emails.

| Vendor | Distinct emails | No usable name, n (%) | Multiple names, n (%) | Maximum names/email |
|---|---:|---:|---:|---:|
| HealthLink | 7,688,331 | 515 (0.00670%) | 165 (0.00215%) | 2 |
| QuantumMedica | 1,705,695 | 1,705,694 (99.99994%) | 0 (0.00000%) | 1 |
| Medscape | 3,550,052 | 44,693 (1.25894%) | 4,174 (0.11758%) | 6 |
| Endato | 5,324,318 | 215 (0.00404%) | 28,014 (0.52615%) | 2,155 |
| RocketReach | 3,163,679 | 1,908 (0.06031%) | 21,276 (0.67251%) | 24 |
| DRDB | 819,454 | 56 (0.00683%) | 13,376 (1.63231%) | 3 |
| Haymarket | 4,223,245 | 191,914 (4.54423%) | 0 (0.00000%) | 1 |

Current measured counts, executed SQL and snapshot checks (historical output, not retained: `../../results/published_metric_refresh_20261029.json`) · Native validation and field-preservation checks (historical output, not retained: `../../results/name_consistency_native_validation.json`)

[Profile SQL](../../sql/name_consistency_profile.sql) · [Rules](../../macros/name_consistency.sql) · [Name conflict](12_email_npi_has_name_conflict.md) · [Source fields](../00_source_map.md)

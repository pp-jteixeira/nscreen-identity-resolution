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

## Real examples

Executed October 31, 2026, against canonical snapshot `8811920360682490090`. These selected cases explain outcomes; they do not measure prevalence.

[Executed example SQL](../../sql/examples/11_email_name_count.sql):

```sql
WITH selected AS (
    SELECT *
    FROM iceberg.jteixeira_ipa.pii_clean FOR VERSION AS OF 8811920360682490090
    WHERE (source = 'drdb' AND metric_row_id IN (
        '76F42EB2F2C6093316B5CDEF2587E5A52525DDC28EA8CF1B437507091D8AF857'))
       OR (source = 'endato' AND metric_row_id IN (
        '730FB3822EC1EB3855BF21A4E1C10C1F2788A9DAA943ED02124432207C2B0194'))
       OR (source = 'quantummedica' AND metric_row_id IN (
        '3DD35EF677E8852E5BADCA2E63D87755D8184021D9CBC395E23F6BBD95E7E8DE'))
), context_names AS (
    SELECT t.source, t.email,
           array_sort(array_distinct(flatten(array_agg(transform(t.source_name_values, n -> concat(n.first_name, ' ', n.last_name)))))) AS names
    FROM iceberg.jteixeira_ipa.pii_clean FOR VERSION AS OF 8811920360682490090 t
    JOIN (SELECT DISTINCT source, email FROM selected) k
      ON t.source = k.source AND t.email = k.email
    GROUP BY t.source, t.email
)
SELECT m.source,
       m.email,
       m.email_npi_count,
       m.email_name_count,
       c.names AS email_names,
       m.email_npi_has_name_conflict
FROM selected m
LEFT JOIN context_names c ON m.source = c.source AND m.email = c.email
ORDER BY m.source, m.metric_row_id
```

| source | email | email_npi_count | email_name_count | email_names | email_npi_has_name_conflict |
|---|---|---|---|---|---|
| drdb | klong.md@verizon.net | 1 | 2 | [KEITH LONG, KEITHLINTON LONG] | false |
| endato | cmizelle@att.net | 2 | 2 | [ANGRETTE MCCLOSKEY, TAHANI MCCLOSKEY] | false |
| quantummedica | ojoy0115@yahoo.com | 1 | 0 | [] | NULL |

**What differentiates these cases:** Different normalized spellings count separately even when fuzzy rules agree. An email-level name count can also span different NPIs. Zero means no usable vendor names; registry names do not fill that gap. Name count measures spellings, not people.

## Statistics by source

Measured **October 31, 2026** from `iceberg.jteixeira_ipa.pii_clean` snapshot `8811920360682490090`. These are exact published-population counts across retained eligible history, not a sample. Stored evaluation dates remain unchanged.

[Executed statistics SQL](../../sql/statistics/11_email_name_count.sql)

| Source | Distinct emails | No names: emails, n (%) | Multiple names: emails, n (%) | Maximum names/email |
|---|---|---|---|---|
| HealthLink | 7,688,331 | 515 (0.006698%) | 165 (0.002146%) | 2 |
| QuantumMedica | 1,705,695 | 1,705,694 (99.999941%) | 0 (0.000000%) | 1 |
| Medscape | 3,550,359 | 44,685 (1.258605%) | 4,173 (0.117537%) | 6 |
| Endato | 5,324,318 | 215 (0.004038%) | 28,014 (0.526152%) | 2,155 |
| RocketReach | 3,163,679 | 1,908 (0.060310%) | 21,276 (0.672508%) | 24 |
| DRDB | 819,454 | 56 (0.006834%) | 13,376 (1.632306%) | 3 |
| Haymarket | 4,223,245 | 191,914 (4.544231%) | 0 (0.000000%) | 1 |

Percentages use distinct source/emails. Multiple means at least two normalized spellings, not two verified people. Zero usable names is an observed lack of vendor evidence.

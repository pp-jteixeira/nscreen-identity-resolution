# Email name count

**Principle:** count distinct usable normalized first/last-name pairs reported for an email within one vendor, across all retained history. This counts name spellings, not people.

**Where:** `iceberg.jteixeira_ipa.pii__int_<vendor>__metrics` and `iceberg.jteixeira_ipa.pii_clean`. Inputs: `source`, `email`, `source_name_values`; output: bigint `email_name_count`. Every link for the same vendor/email receives the same count, across all its NPIs.

## How it is computed

Each link's `source_name_values` already holds the usable names of all its versions. Combine them across each vendor/email into `email_names`, including all its NPIs. Remove repeated first/last-name pairs and count the remaining spellings:

```sql
cast(cardinality(array_distinct(transform(email_names,
    n -> ROW(n.first_name, n.last_name)))) AS bigint) AS email_name_count
```

Names use the existing uppercase, accent and whitespace normalization. A usable pair has at least one first-name letter and two last-name letters. Missing, partial and punctuation-only names do not contribute. Zero means no usable names were observed. Versions, email slots, dates and registry-name matches cannot inflate the count.

HealthLink uses its HCP-name reference by NPI across retained HCP history, without date alignment. Other vendors use the names of every version of each link; both DRDB feeds contribute. Registry names do not fill missing vendor names. `source_name_values` retains each link's normalized pairs and first-name variants for inspection.

## Real examples

No examples have been executed against this definition yet.

Cases worth contrasting: one NPI with two normalized spellings that fuzzy rules accept (count two), an email whose names come from different NPIs, and an email without usable vendor names (zero). Registry names do not fill that gap. Name count measures spellings, not people.

## Statistics by source

No measurements exist yet for this definition. [Statistics SQL](../../sql/statistics/11_email_name_count.sql) reports, per source, distinct emails, emails without names, emails with multiple names and the maximum names per email.

Percentages use distinct source/emails. Multiple means at least two normalized spellings, not two verified people. Zero usable names is an observed lack of vendor evidence.

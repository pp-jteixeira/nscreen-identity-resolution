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

**Illustrative examples:**

| Names for one vendor/email | Count | Explanation |
|---|---:|---|
| `José Smith`, `JOSE SMITH` | 1 | Normalization produces the same pair. |
| `ROBERT SMITH`, `BOB SMITH` | 2 | Different spellings, despite fuzzy agreement. |
| `JOHN SMITH` on NPI A; `JANE JONES` on NPI B | 2 | Count includes all NPIs for this email. |
| First names only, or no names | 0 | No usable complete pair. |

HealthLink uses its HCP-name reference by NPI across retained HCP history, without date alignment. Other vendors use their existing record name inputs; both DRDB feeds contribute. Registry names do not fill missing vendor names. `source_name_values` retains each record's normalized pairs and first-name variants for inspection.

## Statistics by vendor

[Statistics SQL](../../sql/statistics/11_email_name_count.sql). This file preserves the executed read-only SQL behind these statistics, including the original measurement relation. Re-running it requires that relation and reference inputs; changing sources will change the results.

Historical baseline: `pii__evidence` was the measurement relation at the stated extraction time; it is outside the current managed build. This table is not a live population report.

Measured **October 29, 2026**, on `iceberg.jteixeira_ipa.pii__evidence`, across all retained history. Extraction timestamp: `2026-10-29T07:42:53.767364+00:00`. Counts are exact.

Percentages use each vendor's distinct emails.

| Vendor | Distinct emails | No usable name, n (%) | Multiple names, n (%) | Maximum names/email |
|---|---:|---:|---:|---:|
| HealthLink | 7,688,331 | 515 (0.00670%) | 165 (0.00215%) | 2 |
| QuantumMedica | 1,705,695 | 1,705,694 (99.99994%) | 0 (0.00000%) | 1 |
| Medscape | 3,550,052 | 44,693 (1.25894%) | 4,174 (0.11758%) | 6 |
| Endato | 5,324,318 | 215 (0.00404%) | 28,014 (0.52615%) | 2,155 |
| RocketReach | 3,163,679 | 1,908 (0.06031%) | 21,276 (0.67251%) | 24 |
| DRDB | 819,454 | 56 (0.00683%) | 13,376 (1.63231%) | 3 |
| Haymarket | 4,223,245 | 191,914 (4.54423%) | 0 (0.00000%) | 1 |

Measured counts and executed SQL (local-only: `../../results/name_consistency_measurements.json`) · Native validation and field-preservation checks (local-only: `../../results/name_consistency_native_validation.json`)

[Profile SQL](../../sql/name_consistency_profile.sql) · [Rules](../../macros/name_consistency.sql) · [Name conflict](12_email_npi_has_name_conflict.md) · [Source fields](../00_source_map.md)

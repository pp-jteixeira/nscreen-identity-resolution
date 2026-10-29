# Email format

**Question:** does the email match the format pattern below? A match does not prove that a mailbox exists, receives mail, or belongs to the NPI holder.

**Where:** source views `iceberg.jteixeira_ipa.pii__int_<vendor>__metrics`, column `email_format_valid`. Input: `email`; key: `source`, `metric_row_id`. Emails are lowercased and trimmed before this check.

## How it is computed

Trim and lowercase the vendor email value; convert blanks to null. Then test the cleaned `email` against the format pattern:

```sql
-- Cleaning step; raw_email represents the vendor's email field or slot.
lower(nullif(trim(cast(raw_email AS varchar)), '')) AS email
```

```sql
regexp_like(email, '^[a-z0-9._%+-]+@[a-z0-9.-]+[.][a-z]{2,}$') AS email_format_valid
```

A match gives true, a non-match false, and a null input null. Metric views exclude blank/null email keys.

**Illustrative examples:**

| Email | Result | Why |
|---|---|---|
| `alex+work@example.com` | true | Matches the pattern |
| `o'neil@example.com` | false | Apostrophe is outside the allowed characters |
| `josé@example.com` | false | Non-ASCII character is outside the pattern |
| `alex..smith@example.com` | true | The pattern allows repeated dots |

This rule can reject legitimate formats and accept malformed-looking ones. It does not test domain or mailbox existence. Role accounts and test addresses are not excluded by this flag. This indicator does not filter rows or assign scores.

## Statistics by source

[Statistics SQL](../../sql/statistics/02_email_format_valid.sql). This standalone read-only equivalent calculates the displayed row counts and percentages from the published table. The saved October 29 tables were derived from the linked grouped-population extraction; this equivalent has been checked locally, not executed against Trino.

Measured October 29, 2026, on `iceberg.jteixeira_ipa.pii_clean` at exact source-record/email-position grain. Percentages use all metric rows within each vendor. Counts are exact and cover all retained history; email–NPI links remain undeduplicated. These are saved measurements, not live counts.

| Source | Metric rows | Invalid rows, n (%) |
|---|---:|---:|
| HealthLink | 11,156,016 | 503 (0.00451%) |
| QuantumMedica | 1,705,723 | 528 (0.03095%) |
| Medscape | 47,072,262 | 13,434 (0.02854%) |
| Endato | 5,427,459 | 358 (0.00660%) |
| RocketReach | 4,864,145 | 212 (0.00436%) |
| DRDB | 1,115,415 | 1,317 (0.11807%) |
| Haymarket | 4,223,245 | 225 (0.00533%) |

No unknown format outcomes were observed. The indicator retains all rows. Distinct-email counts are not reconstructed by summing grouped distinct counts, because groups can overlap.

Derived row statistics (local-only: `../../results/documentation_row_statistics.json`) · [Executed population SQL](../../results/metric_population_20261029/grouped.sql) · Measurement metadata (local-only: `../../results/metric_population_20261029/analysis_metadata.json`) · Published-table validation (local-only: `../../results/final_build.json`)

[Profile SQL](../../sql/email_format_profile.sql) · [Rule SQL](../../macros/email_format_valid.sql)

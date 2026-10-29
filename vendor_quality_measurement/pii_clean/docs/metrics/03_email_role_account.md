# Role accounts

**Question:** does this email use a potentially shared mailbox name? A match does not prove shared ownership or incorrect attribution.

**Where:** column `email_role_account` in each source view `iceberg.jteixeira_ipa.pii__int_<vendor>__metrics`. Substitute `healthlink`, `quantummedica`, `medscape`, `endato`, `rocketreach`, `drdb` or `haymarket`. Input: cleaned `email`; row key: `source`, `metric_row_id`.

## How it is computed

From the trimmed, lowercase email, extract the mailbox before `@` and compare it with the exact role-name list. Suffixes and plus tags remain part of the mailbox, so they do not match.

```sql
coalesce(regexp_extract(email, '^([^@]+)@', 1) IN (
    'admin', 'info', 'office', 'contact', 'frontdesk', 'billing',
    'reception', 'appointments', 'scheduling', 'support', 'noreply'
), false) AS email_role_account
```

| Illustrative email | Flag |
|---|---|
| `billing@clinic.com` | true |
| `jane@clinic.com` | false |
| `billing.team@clinic.com` | false |
| `billing+work@clinic.com` | false |
| `info@` | true (format check fails) |

**Limits:** false means outside this list, not confirmed personal ownership. Missing emails return false; metric views exclude empty email/NPI keys. Format validity is separate. No filtering or scoring.

## Statistics by source

Measured October 29, 2026, on `iceberg.jteixeira_ipa.pii_clean` at exact source-record/email-position grain. Percentages use all metric rows within each vendor. Counts are exact and cover all retained history; email–NPI links remain undeduplicated. These are saved measurements, not live counts.

| Source | Metric rows | Flagged rows, n (%) |
|---|---:|---:|
| HealthLink | 11,156,016 | 44 (0.00039%) |
| QuantumMedica | 1,705,723 | 622 (0.03647%) |
| Medscape | 47,072,262 | 23,761 (0.05048%) |
| Endato | 5,427,459 | 2,253 (0.04151%) |
| RocketReach | 4,864,145 | 109 (0.00224%) |
| DRDB | 1,115,415 | 2,658 (0.23830%) |
| Haymarket | 4,223,245 | 2,294 (0.05432%) |

Flagged means `email_role_account = true`. Repeated records and email positions can count the same email more than once. Distinct-email counts are not reconstructed by summing grouped distinct counts, because groups can overlap.

Derived row statistics (local-only: `../../results/documentation_row_statistics.json`) · [Executed population SQL](../../results/metric_population_20261029/grouped.sql) · Measurement metadata (local-only: `../../results/metric_population_20261029/analysis_metadata.json`) · Published-table validation (local-only: `../../results/final_build.json`)

[Profile SQL](../../sql/email_role_profile.sql) · [Rule SQL](../../macros/email_role_account.sql)

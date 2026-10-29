# Domain classification

**Question:** does the email domain text suggest institutional, free-provider or other usage? This is a text heuristic, not verified affiliation, mailbox availability or ownership.

**Where:** `email_domain_class` in `iceberg.jteixeira_ipa.pii__int_<vendor>__metrics`; vendors: `healthlink`, `quantummedica`, `medscape`, `endato`, `rocketreach`, `drdb`, `haymarket`. Input: cleaned `email`; row key: `source`, `metric_row_id`. No additional joins.

## How it is computed

Lowercase the text after the first `@`. Classify each email using the first matching rule; institutional takes priority over free-provider.

```sql
lower(regexp_extract(email, '@(.*)$', 1)) AS domain
```

```sql
CASE
    WHEN email IS NULL OR strpos(email, '@') = 0 THEN 'unknown'
    WHEN regexp_like(domain, institutional_pattern) THEN 'institutional'
    WHEN regexp_like(domain, free_provider_pattern) THEN 'free'
    ELSE 'custom'
END AS email_domain_class
```

The pattern names abbreviate the [exact regular expressions](../../macros/email_domain_class.sql). Institutional checks cover `.edu`, `.gov`, `.mil`, `.edu.xx`/`.ac.xx` and keywords such as `health`, `clinic` or `univ`. Free-provider checks require a configured name, such as `gmail` or `yahoo`, followed by a dot at the domain's start.

**Illustrative examples:** `alex@clinic.example` → institutional; `alex@gmail.example` → free; `alex@example.test` → custom; `alex.example.test` → unknown.

**Limits:** `unhealthy.example` also matches institutional. `gmail.clinic.example` matches institutional before free. `alex@` becomes custom despite invalid format. Custom does not establish a privately owned domain. Empty email/NPI keys remain outside metric views. Format validity stays separate; no filtering or scoring.

## Statistics by source

[Statistics SQL](../../sql/statistics/04_email_domain_class.sql). This standalone read-only equivalent calculates the displayed row counts and percentages from the published table. The saved October 29 tables were derived from the linked grouped-population extraction; this equivalent has been checked locally, not executed against Trino.

Measured October 29, 2026, on `iceberg.jteixeira_ipa.pii_clean` at exact source-record/email-position grain. Percentages use all metric rows within each vendor. Counts are exact and cover all retained history; email–NPI links remain undeduplicated. These are saved measurements, not live counts.

| Source | Metric rows | Institutional, n (%) | Free, n (%) | Custom, n (%) | Unknown, n (%) |
|---|---:|---:|---:|---:|---:|
| HealthLink | 11,156,016 | 2,115,994 (18.96729%) | 6,607,958 (59.23224%) | 2,432,064 (21.80047%) | 0 (0.00000%) |
| QuantumMedica | 1,705,723 | 267,230 (15.66667%) | 899,876 (52.75628%) | 538,616 (31.57699%) | 1 (0.00006%) |
| Medscape | 47,072,262 | 6,452,445 (13.70753%) | 31,966,928 (67.91033%) | 8,650,719 (18.37753%) | 2,170 (0.00461%) |
| Endato | 5,427,459 | 45,910 (0.84588%) | 4,595,327 (84.66811%) | 786,222 (14.48601%) | 0 (0.00000%) |
| RocketReach | 4,864,145 | 1,022,757 (21.02645%) | 2,246,093 (46.17652%) | 1,595,295 (32.79703%) | 0 (0.00000%) |
| DRDB | 1,115,415 | 198,825 (17.82520%) | 561,202 (50.31329%) | 355,299 (31.85353%) | 89 (0.00798%) |
| Haymarket | 4,223,245 | 1,095,489 (25.93951%) | 1,829,518 (43.32020%) | 1,298,238 (30.74030%) | 0 (0.00000%) |

Every row has one category. Unknown means missing `@`, not an unmeasured row.

Derived row statistics (local-only: `../../results/documentation_row_statistics.json`) · [Executed population SQL](../../results/metric_population_20261029/grouped.sql) · Measurement metadata (local-only: `../../results/metric_population_20261029/analysis_metadata.json`) · Published-table validation (local-only: `../../results/final_build.json`)

[Profile SQL](../../sql/email_domain_profile.sql) · [Rule SQL](../../macros/email_domain_class.sql)

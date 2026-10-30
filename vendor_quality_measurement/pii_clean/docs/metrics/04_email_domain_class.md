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

**Limits:** `unhealthy.example` also matches institutional. `gmail.clinic.example` matches institutional before free. `alex@` becomes custom despite invalid format. Custom does not establish a privately owned domain. Empty email/NPI keys remain outside metric views. Format validity stays separate; no filtering or scoring.

## Real examples: contrasting outcomes

Selected real records, queried October 30, 2026, from `iceberg.jteixeira_ipa.pii_clean` at snapshot `8096642935433856886`. These examples explain outcomes; they are not prevalence estimates. Mailbox text is omitted; only the extracted domain is displayed.

[Runnable example SQL](../../sql/examples/04_email_domain_class.sql):

```sql
WITH selected AS (
    SELECT *
    FROM iceberg.jteixeira_ipa.pii_clean FOR VERSION AS OF 8096642935433856886
    WHERE (source = 'endato' AND metric_row_id IN (
        '15A7CE1D623FCBA4AE051F8C51990D1C50F1E52AFB488C415FFCF1AA87D52B5C',
        '9982987297DF72C149474BB117CF1E80D17C1D9C0C505EE5C907B87830133454',
        'A74664CA2BA51AE5D7B13D02524BAFA5CFEE1368279C5337D1EC275D7A0051FA'))
       OR (source = 'medscape' AND metric_row_id IN (
        'DBA5C659BCB71479B83AC76050B928A4EC4FAAED4C6057C6C2814DBBB52BB12C'))
)
SELECT m.source,
       regexp_extract(m.email, '@(.*)$', 1) AS domain,
       m.email_domain_class,
       m.email_format_valid
FROM selected m
ORDER BY m.source, m.metric_row_id
```

**Result:** 4 rows.

| source | domain | email_domain_class | email_format_valid |
|---|---|---|---|
| endato | hotmail.com | free | true |
| endato | mindspring.com | custom | true |
| endato | medstudent.pitt.edu | institutional | true |
| medscape | NULL | unknown | false |

**What differentiates these cases:** The domain text drives institutional, free-provider and custom categories. A missing `@` yields a NULL extracted domain and `unknown`, rather than `custom`. The custom label for `mindspring.com` reflects the configured free-provider list, not verified ownership. These categories describe text patterns, not verified affiliation.

Stored indicators are unchanged by display helpers. Reproduction requires the pinned snapshot to remain available.

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

Derived row statistics (historical output, not retained: `../../results/documentation_row_statistics.json`) · [Executed population SQL](../../results/metric_population_20261029/grouped.sql) · Measurement metadata (historical output, not retained: `../../results/metric_population_20261029/analysis_metadata.json`) · Published-table validation (historical output, not retained: `../../results/final_build.json`)

[Profile SQL](../../sql/email_domain_profile.sql) · [Rule SQL](../../macros/email_domain_class.sql)

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

## Real examples

Executed October 31, 2026, against canonical snapshot `8811920360682490090`. These selected cases explain outcomes; they do not measure prevalence.

[Executed example SQL](../../sql/examples/04_email_domain_class.sql):

```sql
WITH selected AS (
    SELECT *
    FROM iceberg.jteixeira_ipa.pii_clean FOR VERSION AS OF 8811920360682490090
    WHERE (source = 'endato' AND metric_row_id IN (
        '15A7CE1D623FCBA4AE051F8C51990D1C50F1E52AFB488C415FFCF1AA87D52B5C',
        '9982987297DF72C149474BB117CF1E80D17C1D9C0C505EE5C907B87830133454',
        'A74664CA2BA51AE5D7B13D02524BAFA5CFEE1368279C5337D1EC275D7A0051FA'))
       OR (source = 'medscape' AND metric_row_id IN (
        'DBA5C659BCB71479B83AC76050B928A4EC4FAAED4C6057C6C2814DBBB52BB12C'))
)
SELECT m.source,
       m.email,
       regexp_extract(m.email, '@(.*)$', 1) AS domain,
       m.email_domain_class,
       m.email_format_valid
FROM selected m
ORDER BY m.source, m.metric_row_id
```

| source | email | domain | email_domain_class | email_format_valid |
|---|---|---|---|---|
| endato | ruthbrauer@hotmail.com | hotmail.com | free | true |
| endato | rshillpinney@mindspring.com | mindspring.com | custom | true |
| endato | ztoney.laurenm1@medstudent.pitt.edu | medstudent.pitt.edu | institutional | true |
| medscape | pa | NULL | unknown | false |

**What differentiates these cases:** The domain text drives institutional, free-provider and custom categories. A missing `@` yields a NULL extracted domain and `unknown`, rather than `custom`. The custom label for `mindspring.com` reflects the configured free-provider list, not verified ownership. These categories describe text patterns, not verified affiliation.

## Statistics by source

Measured **October 31, 2026** from `iceberg.jteixeira_ipa.pii_clean` snapshot `8811920360682490090`. These are exact published-population counts across retained eligible history, not a sample. Stored evaluation dates remain unchanged.

[Executed statistics SQL](../../sql/statistics/04_email_domain_class.sql)

| Source | Metric records | Institutional, n (%) | Free, n (%) | Custom, n (%) | Unknown, n (%) |
|---|---|---|---|---|---|
| HealthLink | 11,156,016 | 2,115,994 (18.967291%) | 6,607,958 (59.232238%) | 2,432,064 (21.800471%) | 0 (0.000000%) |
| QuantumMedica | 1,705,723 | 267,230 (15.666670%) | 899,876 (52.756280%) | 538,616 (31.576991%) | 1 (0.000059%) |
| Medscape | 47,164,366 | 6,466,209 (13.709946%) | 32,027,495 (67.906129%) | 8,668,490 (18.379321%) | 2,172 (0.004605%) |
| Endato | 5,427,459 | 45,910 (0.845884%) | 4,595,327 (84.668111%) | 786,222 (14.486005%) | 0 (0.000000%) |
| RocketReach | 4,864,145 | 1,022,757 (21.026450%) | 2,246,093 (46.176522%) | 1,595,295 (32.797028%) | 0 (0.000000%) |
| DRDB | 1,115,415 | 198,825 (17.825204%) | 561,202 (50.313291%) | 355,299 (31.853525%) | 89 (0.007979%) |
| Haymarket | 4,223,245 | 1,095,489 (25.939509%) | 1,829,518 (43.320196%) | 1,298,238 (30.740296%) | 0 (0.000000%) |

Percentages use all metric records within each source. Categories partition records. Distinct-email outcomes cannot be inferred by adding record counts.

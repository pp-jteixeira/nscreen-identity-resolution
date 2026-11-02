# Domain classification

**Question:** does the email domain text suggest institutional, free-provider or other usage? This is a text heuristic, not verified affiliation, mailbox availability or ownership.

**Where:** `email_domain_class` in `iceberg.jteixeira_ipa.pii__int_<vendor>__metrics`; vendors: `healthlink`, `quantummedica`, `medscape`, `endato`, `rocketreach`, `drdb`, `haymarket`. Input: cleaned `email`; row key: `source`, `link_id` (one source/email/NPI link). No additional joins.

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

**Limits:** `unhealthy.example` also matches institutional. `gmail.clinic.example` matches institutional before free. `alex@` becomes custom despite invalid format. Custom does not establish a privately owned domain. Empty email/NPI keys remain outside metric views. The result depends only on the link's email. Format validity stays separate; no filtering or scoring.

## Real examples

No examples have been executed against this definition yet.

Cases worth contrasting: a free-provider domain such as `hotmail.com`, an institutional `.edu` domain, a custom domain outside the configured free-provider list, and an email without `@`, which yields a NULL extracted domain and `unknown` rather than `custom`. These categories describe text patterns, not verified affiliation.

## Statistics by source

No measurements exist yet for this definition. [Statistics SQL](../../sql/statistics/04_email_domain_class.sql) reports, per source, metric rows (links) and the institutional, free, custom and unknown shares.

Percentages use all links within each source. Categories partition links. Distinct-email outcomes cannot be inferred by adding link counts.

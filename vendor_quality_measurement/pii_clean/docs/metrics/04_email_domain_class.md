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

Executed November 2, 2026, against `iceberg.jteixeira_ipa.pii_clean` snapshot `2837737034249693554`. These selected cases explain outcomes; they do not measure prevalence.

```sql
SELECT source,
       email,
       npi,
       email_domain_class
FROM iceberg.jteixeira_ipa.pii_clean FOR VERSION AS OF 2837737034249693554
WHERE (source = 'healthlink' AND link_id IN (
        '000003E1464D72618D55F78C6D464B854F2B8213906F0546468EE5C189A1376A',
        '000009F089C4DBC8CE55C0EC5FDFAE178C0984C864E9A8B6EE61656DEADEF74F',
        '000003EF65550016D15786DAA9351C829F608354411ECD4C845B5E20C1276CC8'))
   OR (source = 'medscape' AND link_id IN (
        '00B591EA1F1EBE58D013ED2D3CE15670C48EF1C905F79984EC94173D49F52497'))
   OR (source = 'drdb' AND link_id IN (
        '0329091836A2527C77EDBB7997A87217ED1F2CDEC45F02EC8BA6D3317D91DA68'))
ORDER BY source, email_domain_class, email
```

| source | email | npi | email_domain_class |
|---|---|---|---|
| drdb | http://secure.eyehub.com/secure/index.cfm?fuseaction=site.appointments&domain=visionsource-emeraldcoasteyecare.com | 1265668842 | unknown |
| healthlink | jnance219676@cookchildrens.direct-ci.com | 1770745390 | custom |
| healthlink | csteele@hotmail.com | 1720286941 | free |
| healthlink | jtorres@rwjuh.edu | 1356332324 | institutional |
| medscape | ny | 1669559613 | unknown |

**What differentiates these cases:** `hotmail.com` is a configured free provider. `rwjuh.edu` is institutional through its `.edu` suffix. `cookchildrens.direct-ci.com` matches neither list, so it is custom, which does not establish a privately owned domain. The Medscape value `ny` and the DRDB web address contain no `@`, so their class is `unknown` rather than `custom`. These categories describe text patterns, not verified affiliation.

## Statistics by source

Measured **November 2, 2026** from `iceberg.jteixeira_ipa.pii_clean` snapshot `2837737034249693554`. These are exact published-population counts across retained eligible history, not a sample.

Source data period (first to last observed day): HealthLink 2026-01-07 to 2026-10-03; QuantumMedica 2025-09-14 to 2026-10-15; Medscape 2024-01-10 to 2026-11-01; Haymarket 2021-07-06 (a single day). Endato, RocketReach and DRDB are undated.

[Statistics SQL](../../sql/statistics/04_email_domain_class.sql) reports, per source, links and the institutional, free, custom and unknown counts.

| Source | Links | Institutional, n (%) | Free, n (%) | Custom, n (%) | Unknown, n (%) |
|---|---:|---:|---:|---:|---:|
| HealthLink | 7,688,451 | 1,501,163 (19.524908%) | 4,367,980 (56.812224%) | 1,819,308 (23.662868%) | 0 (0.000000%) |
| QuantumMedica | 1,705,723 | 267,230 (15.666670%) | 899,876 (52.756280%) | 538,616 (31.576991%) | 1 (0.000059%) |
| Medscape | 3,661,537 | 567,981 (15.512092%) | 2,378,320 (64.954144%) | 715,099 (19.530023%) | 137 (0.003742%) |
| Endato | 5,427,459 | 45,910 (0.845884%) | 4,595,327 (84.668111%) | 786,222 (14.486005%) | 0 (0.000000%) |
| RocketReach | 3,199,535 | 801,446 (25.048827%) | 1,095,169 (34.229005%) | 1,302,920 (40.722167%) | 0 (0.000000%) |
| DRDB | 826,886 | 160,202 (19.374134%) | 368,985 (44.623443%) | 297,653 (35.996861%) | 46 (0.005563%) |
| Haymarket | 4,223,245 | 1,095,489 (25.939509%) | 1,829,518 (43.320196%) | 1,298,238 (30.740296%) | 0 (0.000000%) |

Percentages use all links within each source. Categories partition links. Distinct-email outcomes cannot be inferred by adding link counts.

Endato is dominated by free-provider addresses (84.67%) and has the smallest institutional share (0.85%). Haymarket (25.94%) and RocketReach (25.05%) have the largest institutional shares, and RocketReach has the largest custom share (40.72%). Unknown occurs only for DRDB (46 links), Medscape (137) and QuantumMedica (1).

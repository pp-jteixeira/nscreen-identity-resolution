# Domain evidence

**Status:** implemented, stored and measured.

**Principle:** an email domain is a context the mailbox text cannot show. A domain whose NPIs share a state and a facility looks like one institution. A domain with unrelated NPIs is a shared service or a free provider. This metric publishes per-source counts and concentrations for the domain of every link.

**Where to find it:** `email_domain`, `domain_email_count`, `domain_npi_count`, `domain_npis_with_state`, `domain_state_count`, `domain_top_state_share`, `domain_npis_with_facility`, `domain_top_facility_npi`, `domain_top_facility_share` and `domain_evidence_version` in `iceberg.jteixeira_ipa.pii_clean`. One row per source/email/NPI link; key: `source`, `link_id`. The fields are computed downstream of stored core by `int_cookie__metrics`, because the aggregates need every link of the source, which per-vendor batches such as the Medscape email buckets do not hold. Inputs: stored `email`, `npi`, `email_domain_class`, `facility_primary_state` and `facility_npi_values`.

## How it is computed

`email_domain` is the lowercase text after the first `@`, or null. Within a source, per domain:

```sql
count(DISTINCT email) AS domain_email_count, count(DISTINCT npi) AS domain_npi_count
```

Counts include every domain class. State and facility concentration use only domains classed `custom` or `institutional` ([page 04](04_email_domain_class.md)); free-provider and unknown domains show null, since a free-mail domain is not an institution. For each such domain, each NPI counts once with its `facility_primary_state` and its retained facility NPIs. `domain_top_state_share` is the share of NPIs with a usable state that sit in the most common state. `domain_top_facility_share` is the share of NPIs with any facility NPI whose facilities include the most common facility NPI. Ties go to the greater NPI text. NPIs without evidence stay out of both denominators, which are published as `domain_npis_with_state` and `domain_npis_with_facility`. Domains are never pooled across sources. The implementation is [domain_evidence.sql](../../macros/domain_evidence.sql).

## Real examples: contrasting outcomes

Executed November 3, 2026 against `iceberg.jteixeira_ipa.pii_clean` (snapshot `985110448175465479`) for source `healthlink`, reading the stored domain columns. One row per domain; these selected cases do not measure prevalence.

| email_domain | class | emails | NPIs | NPIs with state | states | top state share | NPIs with facility | top facility share | What it shows |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| 1823.direct.athenahealth.com | institutional | 36 | 36 | 26 | 1 | 1.00 | 26 | 0.85 | One practice: one state, one shared facility |
| acadiahealthcare.com | institutional | 64 | 64 | 26 | 15 | 0.19 | 26 | 0.04 | A national chain: many states, no shared facility |
| 0to10.net | custom | 1 | 1 | null | null | null | null | null | One NPI without state or facility evidence |
| gmail.com | free | 2,334,778 | 1,935,023 | null | null | null | null | null | Counts only |

## Statistics by source

Measured **November 3, 2026** from `iceberg.jteixeira_ipa.pii_clean` snapshot `985110448175465479`, reading the stored domain columns. Exact population counts, not a sample, except the approximate median. Percentages use the links of the source and domain class; the facility column uses links that have a facility share. The 10-NPI and half-share cut points only describe the distribution and are not quality thresholds.

[Statistics SQL](../../sql/statistics/28_domain_evidence.sql)

| Source | Domain class | Links | Domains | On a single-NPI domain, n (%) | On a domain with 10+ NPIs, n (%) | Median NPIs per domain (approximate) | Single-state domain, n (%) | With facility share, n (%) | Top facility share ≥ 0.5, n (%) |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| DRDB | custom | 297,653 | 43,674 | 28,050 (9.4%) | 222,802 (74.9%) | 80 | 53,076 (17.8%) | 266,114 (89.4%) | 86,827 (32.6%) |
| DRDB | free | 368,985 | 220 | 115 (0.0%) | 368,671 (99.9%) | 93,793 | not applicable | not applicable | not applicable |
| DRDB | institutional | 160,202 | 12,315 | 6,344 (4.0%) | 136,723 (85.3%) | 161 | 19,467 (12.2%) | 151,594 (94.6%) | 42,633 (28.1%) |
| DRDB | unknown | 46 | 0 | not applicable | not applicable | not measured | not applicable | not applicable | not applicable |
| Endato | custom | 786,222 | 125,789 | 114,215 (14.5%) | 609,090 (77.5%) | 3,437 | 61,287 (7.8%) | 685,020 (87.1%) | 75,614 (11.0%) |
| Endato | free | 4,595,327 | 861 | 556 (0.0%) | 4,594,097 (100.0%) | 683,200 | not applicable | not applicable | not applicable |
| Endato | institutional | 45,910 | 11,195 | 8,109 (17.7%) | 26,580 (57.9%) | 17 | 7,263 (15.8%) | 37,040 (80.7%) | 10,448 (28.2%) |
| Haymarket | custom | 1,298,238 | 96,367 | 65,021 (5.0%) | 1,129,929 (87.0%) | 469 | 103,421 (8.0%) | 1,229,825 (94.7%) | 220,965 (18.0%) |
| Haymarket | free | 1,829,518 | 262 | 129 (0.0%) | 1,829,176 (100.0%) | 378,070 | not applicable | not applicable | not applicable |
| Haymarket | institutional | 1,095,489 | 27,375 | 14,056 (1.3%) | 1,041,379 (95.1%) | 1,453 | 36,540 (3.3%) | 1,077,360 (98.3%) | 121,031 (11.2%) |
| HealthLink | custom | 1,819,308 | 112,399 | 73,555 (4.0%) | 1,627,026 (89.4%) | 963 | 126,597 (7.0%) | 1,725,050 (94.8%) | 357,968 (20.8%) |
| HealthLink | free | 4,367,980 | 70 | 13 (0.0%) | 4,367,918 (100.0%) | 1,626,728 | not applicable | not applicable | not applicable |
| HealthLink | institutional | 1,501,163 | 34,367 | 17,916 (1.2%) | 1,439,363 (95.9%) | 2,203 | 46,408 (3.1%) | 1,467,831 (97.8%) | 235,757 (16.1%) |
| Medscape | custom | 715,189 | 107,418 | 80,332 (11.2%) | 554,703 (77.6%) | 353 | 76,616 (10.7%) | 627,489 (87.7%) | 132,882 (21.2%) |
| Medscape | free | 2,378,668 | 909 | 502 (0.0%) | 2,377,297 (99.9%) | 484,086 | not applicable | not applicable | not applicable |
| Medscape | institutional | 568,061 | 28,893 | 17,067 (3.0%) | 519,713 (91.5%) | 737 | 27,232 (4.8%) | 544,672 (95.9%) | 60,143 (11.0%) |
| Medscape | unknown | 137 | 0 | not applicable | not applicable | not measured | not applicable | not applicable | not applicable |
| QuantumMedica | custom | 538,616 | 142,573 | 103,124 (19.1%) | 325,009 (60.3%) | 28 | 101,989 (18.9%) | 462,083 (85.8%) | 151,058 (32.7%) |
| QuantumMedica | free | 899,876 | 159 | 63 (0.0%) | 899,658 (100.0%) | 167,592 | not applicable | not applicable | not applicable |
| QuantumMedica | institutional | 267,230 | 14,381 | 7,203 (2.7%) | 240,586 (90.0%) | 453 | 14,653 (5.5%) | 260,226 (97.4%) | 39,889 (15.3%) |
| QuantumMedica | unknown | 1 | 0 | not applicable | not applicable | not measured | not applicable | not applicable | not applicable |
| RocketReach | custom | 1,302,920 | 125,506 | 222,498 (17.1%) | 824,410 (63.3%) | 36 | 255,883 (19.6%) | 1,063,859 (81.7%) | 405,324 (38.1%) |
| RocketReach | free | 1,095,169 | 634 | 397 (0.0%) | 1,094,137 (99.9%) | 142,288 | not applicable | not applicable | not applicable |
| RocketReach | institutional | 801,446 | 28,598 | 50,261 (6.3%) | 649,466 (81.0%) | 201 | 97,347 (12.1%) | 731,098 (91.2%) | 195,850 (26.8%) |

**Interpretation:** Free-provider domains hold 34% to 85% of each source's links, and the median link's domain names about 95,000 to 1.9 million NPIs, so they carry no institutional signal and show counts only. Custom and institutional domains split into two groups. Between 1% and 19% of their links sit on a domain with a single NPI, which has no peers to compare. Most links sit on domains with ten or more NPIs, where the concentration fields apply. There, a top facility share of at least 0.5 holds for 11% to 38% of the links that have a share, so most domains, even institutional ones, do not point to one facility. The `institutional` class is a text guess and includes national chains, as the acadiahealthcare.com row shows. Concentration describes how related the NPIs are; it does not prove that a given email belongs to its NPI.

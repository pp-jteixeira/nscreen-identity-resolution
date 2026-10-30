# 20. Link freshness

Freshness separates an old vendor feed from a link that trails the vendor's latest observed day. It describes retained evidence, not current ownership, deliverability or a verified deletion.

## How it is computed

The [macro](../../macros/link_freshness.sql) reads eligible vendor records before reference enrichment. It groups by `source`, `email`, `npi`, computes `max(last_seen_day) AS link_last_observed_day`, then takes the maximum link date within each source as `source_latest_observed_day`. This is the latest day among records eligible for metrics, not necessarily the latest raw delivery.

It joins these dates back to every original record without collapsing email positions. Five columns are appended to `iceberg.jteixeira_ipa.pii_clean`:

| Column | Meaning |
|---|---|
| `link_freshness_as_of_day` | Evaluation date, defaulting to Europe/Paris today. The same-named rendering variable overrides it. |
| `source_latest_observed_day` | Latest retained observation date for this vendor. |
| `link_last_observed_day` | Latest retained observation date for this source/email/NPI link. |
| `source_age_days` | `date_diff('day', source_latest_observed_day, link_freshness_as_of_day)`. |
| `link_lag_days` | `date_diff('day', link_last_observed_day, source_latest_observed_day)`. |

Missing dates remain null. Undated records can inherit a known date from another record of the same link. Future dates remain visible, but a future vendor maximum makes both day counts null for that vendor. No negative ages, thresholds, filters or scores are introduced.

**Illustrative example:** evaluated October 30, a vendor last observed October 28 has source age 2. A link last observed October 10 has lag 18; a link observed October 28 has lag 0.

## Statistics and limits

[Standalone population SQL](../../sql/statistics/20_link_freshness.sql) reads the published columns. Each source/email/NPI contributes once to link counts and exact nearest-rank p50/p95 lag. Latest-day percentages use known-lag links; missing-date percentages use all links. Metric-row counts retain every record.

Repeated deliveries are not independent confirmation. Missing links can reflect partial feeds. Endato, RocketReach and DRDB have no observation dates. See [source dates](../00_source_map.md) and [publication validation](../../results/publication_20261030/report.md).

### Published population, October 30, 2026

Evaluation day: `2026-10-30`. The query covers all 75,564,265 retained rows and 26,730,605 source/email/NPI links. Dates below are latest eligible observations. Percentiles use the exact nearest-rank method and exclude unknown lags. Unknown values display as —.

| Vendor | Links | Undated links (%) | Latest day | Source age (days) | At latest day / known-lag links (%) | p50 / p95 lag (days) | Maximum lag (days) |
|---|---:|---:|---|---:|---:|---:|---:|
| drdb | 826,886 | 826,886 (100.00%) | — | — | — | — / — | — |
| endato | 5,427,459 | 5,427,459 (100.00%) | — | — | — | — / — | — |
| haymarket | 4,223,245 | 0 (0.00%) | 2021-07-06 | 1,942 | 4,223,245 / 4,223,245 (100.00%) | 0 / 0 | 0 |
| healthlink | 7,688,451 | 0 (0.00%) | 2026-10-25 | 5 | 6,163,984 / 7,688,451 (80.17%) | 0 / 22 | 291 |
| medscape | 3,659,306 | 0 (0.00%) | 2026-10-28 | 2 | 845,413 / 3,659,306 (23.10%) | 260 / 965 | 1,022 |
| quantummedica | 1,705,723 | 0 (0.00%) | 2026-10-15 | 15 | 1,692,618 / 1,705,723 (99.23%) | 0 / 0 | 396 |
| rocketreach | 3,199,535 | 3,199,535 (100.00%) | — | — | — | — / — | — |

Measured on published snapshot `1613450720463268051`. The linked standalone SQL is the executed aggregation. No future-dated links were observed. Detailed SQL and aggregate measurements are local-only: `../../results/link_freshness_published_statistics_20261030.json`.

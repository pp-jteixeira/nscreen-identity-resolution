# 20. Link freshness

Freshness separates an old vendor feed from a link that trails the vendor's latest observed day. It describes retained evidence, not current ownership, deliverability or a verified deletion.

## How it is computed

The [macro](../../macros/link_freshness.sql) reads eligible vendor links before reference enrichment. Each row is one `source`, `email`, `npi` link, and `link_last_observed_day` is its `last_seen_day`, the latest day across all versions of the link. The maximum link date within each source is `source_latest_observed_day`. This is the latest day among links eligible for metrics, not necessarily the latest raw delivery.

Five columns are appended to each link in `iceberg.jteixeira_ipa.pii_clean`:

| Column | Meaning |
|---|---|
| `link_freshness_as_of_day` | Evaluation date, defaulting to Europe/Paris today. The same-named rendering variable overrides it. |
| `source_latest_observed_day` | Latest retained observation date for this vendor. |
| `link_last_observed_day` | Latest retained observation date for this source/email/NPI link. |
| `source_age_days` | `date_diff('day', source_latest_observed_day, link_freshness_as_of_day)`. |
| `link_lag_days` | `date_diff('day', link_last_observed_day, source_latest_observed_day)`. |

Missing dates remain null. A link with both dated and undated versions takes its date from the dated versions. Future dates remain visible, but a future vendor maximum makes both day counts null for that vendor. No negative ages, thresholds, filters or scores are introduced.

## Real examples

No executed examples exist yet for this definition.

**What differentiates outcomes:** Haymarket can have zero link lag while the entire feed is old. Medscape separates a link far behind its feed from a link present on the feed's latest day. Undated Endato evidence stays NULL. Zero lag therefore means current within the retained feed, not fresh in calendar time.

## Statistics by source

No measurements exist yet for this definition.

[Statistics SQL](../../sql/statistics/20_link_freshness.sql)

Latest-day percentages use links with a known lag. Lag quantiles use exact nearest ranks over known lags. Missing or future-dated source history can leave lag unknown. Zero lag can accompany an old feed.

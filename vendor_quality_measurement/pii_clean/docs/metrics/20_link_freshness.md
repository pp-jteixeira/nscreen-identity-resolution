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

Executed November 2, 2026, against `iceberg.jteixeira_ipa.pii_clean` snapshot `2837737034249693554`. These selected cases explain outcomes; they do not measure prevalence.

```sql
SELECT source, email, npi, record_count, first_seen_day, last_seen_day,
       source_latest_observed_day, source_age_days, link_lag_days
FROM iceberg.jteixeira_ipa.pii_clean
WHERE ROW(source, link_id) IN (
    ROW('haymarket', '000001F7A2912A5F067399B37D6E035976692BB806F3C0D9BFEE46B2319F5867'),
    ROW('healthlink', '000003E1464D72618D55F78C6D464B854F2B8213906F0546468EE5C189A1376A'),
    ROW('healthlink', '000032267A4E0ECB889781B89117C8EB41173BD4A86B837B3A5D8108ACD40968'),
    ROW('medscape', '000135B3B11198600E8D09848CB9CC7469321202CB66FA55ACA17658F213A9FF'),
    ROW('medscape', '000003E89687B0747799F66B933F62332C57BB2FD0FDFE3D96D63F41944A4C61'),
    ROW('quantummedica', '000239C8024AE964D08B93D526D1CF09D9947533CC679D6824894E2480019F75'),
    ROW('endato', '00000359411756A423CF6FA62F7ADEA5FAF7F0213AB36334DF4DE1CD16782DF9'))
ORDER BY source, link_id
```

| source | email | npi | record_count | first_seen_day | last_seen_day | source_latest_observed_day | source_age_days | link_lag_days |
|---|---|---|---|---|---|---|---|---|
| endato | hhutch2@gmail.com | 1922407774 | 1 | NULL | NULL | NULL | NULL | NULL |
| haymarket | ejshim41@yahoo.com | 1104930056 | 1 | 2021-07-06 | 2021-07-06 | 2021-07-06 | 1945 | 0 |
| healthlink | csteele@hotmail.com | 1720286941 | 3 | 2026-01-07 | 2026-10-03 | 2026-10-03 | 30 | 0 |
| healthlink | jennifercatlett@hotmail.com | 1235148750 | 2 | 2026-01-07 | 2026-10-02 | 2026-10-03 | 30 | 1 |
| medscape | roadrunner262001@yahoo.com | 1003803560 | 1 | 2024-01-10 | 2025-10-29 | 2026-11-01 | 1 | 368 |
| medscape | rojanasthien@gmail.com | 1457706723 | 3 | 2024-01-10 | 2026-11-01 | 2026-11-01 | 1 | 0 |
| quantummedica | isebastian@yahoo.com | 1407803430 | 1 | 2025-09-14 | 2026-04-15 | 2026-10-15 | 18 | 183 |

**What differentiates these cases:** Haymarket `ejshim41@yahoo.com` has zero lag because it is on the feed's only day, while the feed itself is 1,945 days old. HealthLink `csteele@hotmail.com` has three versions and its `last_seen_day` is the latest day across them, 2026-10-03, so its lag is 0; `jennifercatlett@hotmail.com` was last seen one day before the feed's latest day (lag 1). Medscape `rojanasthien@gmail.com` is on the feed's latest day (lag 0, feed age 1 day), while `roadrunner262001@yahoo.com` was last seen 368 days earlier. QuantumMedica `isebastian@yahoo.com` trails its feed by 183 days. Endato `hhutch2@gmail.com` is undated, so every freshness day count is NULL. Zero lag therefore means current within the retained feed, not fresh in calendar time.

## Statistics by source

Measured **November 2, 2026** from `iceberg.jteixeira_ipa.pii_clean` snapshot `2837737034249693554`. These are exact published-population counts across retained eligible history, not a sample. The evaluation day (`link_freshness_as_of_day`) is 2026-11-02 for every link.

Source data period (first and last observed day): HealthLink 2026-01-07 to 2026-10-03, QuantumMedica 2025-09-14 to 2026-10-15, Medscape 2024-01-10 to 2026-11-01 and Haymarket 2021-07-06 (one snapshot day). Endato, RocketReach and DRDB are undated.

[Statistics SQL](../../sql/statistics/20_link_freshness.sql)

| Source | Links | Source latest observed day | Source age (days) | undated links, n (%) | lag 0, n (% of known lag) | lag above 0, n (% of known lag) | p50 lag (days) | p95 lag (days) | maximum lag (days) |
|---|---|---|---|---|---|---|---|---|---|
| HealthLink | 7,688,451 | 2026-10-03 | 30 | 0 (0.000000%) | 6,903,398 (89.789192%) | 785,053 (10.210808%) | 0 | 1 | 269 |
| QuantumMedica | 1,705,723 | 2026-10-15 | 18 | 0 (0.000000%) | 1,692,618 (99.231704%) | 13,105 (0.768296%) | 0 | 0 | 396 |
| Medscape | 3,661,537 | 2026-11-01 | 1 | 0 (0.000000%) | 843,440 (23.035135%) | 2,818,097 (76.964865%) | 264 | 969 | 1026 |
| Endato | 5,427,459 | NULL | NULL | 5,427,459 (100.000000%) | — | — | — | — | — |
| RocketReach | 3,199,535 | NULL | NULL | 3,199,535 (100.000000%) | — | — | — | — | — |
| DRDB | 826,886 | NULL | NULL | 826,886 (100.000000%) | — | — | — | — | — |
| Haymarket | 4,223,245 | 2021-07-06 | 1945 | 0 (0.000000%) | 4,223,245 (100.000000%) | 0 (0.000000%) | 0 | 0 | 0 |

Latest-day percentages use links with a known lag. Lag quantiles use exact nearest ranks over known lags. Missing or future-dated source history can leave lag unknown. Zero lag can accompany an old feed. No link is dated after the evaluation day.

Endato, RocketReach and DRDB are entirely undated, so source age and lag are unknown for all of their links. Haymarket has zero lag for every link although its feed is 1,945 days old. HealthLink has 89.8% and QuantumMedica 99.2% of links on their feed's latest day. Medscape has only 23.0% of links on its latest day; its median lag is 264 days, its 95th percentile 969 days, and its maximum lag of 1,026 days equals the length of its observed period.

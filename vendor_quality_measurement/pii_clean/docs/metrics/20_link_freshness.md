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

## Real examples

Executed October 31, 2026, against canonical snapshot `8811920360682490090`. These selected cases explain outcomes; they do not measure prevalence.

[Executed example SQL](../../sql/examples/20_link_freshness.sql):

```sql
WITH selected AS (
    SELECT *
    FROM iceberg.jteixeira_ipa.pii_clean FOR VERSION AS OF 8811920360682490090
    WHERE (source = 'endato' AND metric_row_id IN (
        '174DF23ED50299325123B7660ECB3AA68FEDD02FA7345B47D575396DEAF0419A'))
       OR (source = 'haymarket' AND metric_row_id IN (
        '774416407C42EA3A688EA08521D045D280032B7973C5D95696F91DC9BB8CE731'))
       OR (source = 'medscape' AND metric_row_id IN (
        '5871A1225861F4254047C0F9F0C40D5B0E9F433B8AAA9632B36BAEACE4DCD51D',
        'ABDD5253F7AE1234C4E9B5856FF54938AD6993BA3DA4740DDF24B1DB96F480AA'))
)
SELECT m.source,
       m.email,
       m.npi,
       m.link_last_observed_day,
       m.source_latest_observed_day,
       m.source_age_days,
       m.link_lag_days,
       m.link_freshness_as_of_day AS evaluated_on
FROM selected m
ORDER BY m.source, m.metric_row_id
```

| source | email | npi | link_last_observed_day | source_latest_observed_day | source_age_days | link_lag_days | evaluated_on |
|---|---|---|---|---|---|---|---|
| endato | arnie.hicks@gmail.com | 1124164199 | NULL | NULL | NULL | NULL | 2026-10-30 |
| haymarket | mdusn@yahoo.com | 1497727853 | 2021-07-06 | 2021-07-06 | 1,942 | 0 | 2026-10-30 |
| medscape | jonathan.weinkle@gmail.com | 1598891004 | 2026-10-29 | 2026-10-29 | 1 | 0 | 2026-10-30 |
| medscape | jlee2@lghealth.org | 1629337647 | 2024-03-07 | 2026-10-29 | 1 | 966 | 2026-10-30 |

**What differentiates these cases:** Haymarket can have zero link lag while the entire feed is old. Medscape separates a link far behind its feed from a link present on the feed's latest day. Undated Endato evidence stays NULL. Zero lag therefore means current within the retained feed, not fresh in calendar time.

## Statistics by source

Measured **October 31, 2026** from `iceberg.jteixeira_ipa.pii_clean` snapshot `8811920360682490090`. These are exact published-population counts across retained eligible history, not a sample. Stored evaluation dates remain unchanged.

[Executed statistics SQL](../../sql/statistics/20_link_freshness.sql)

| Source | Stored evaluation day | Latest source observation | Source age, days | Email/NPI links | Unknown lag links | At latest day / known lag, n (%) | Lag median / P95, days |
|---|---|---|---|---|---|---|---|
| HealthLink | 2026-10-30 | 2026-10-03 | 27 | 7,688,451 | 0 | 6,903,398 (89.789192%) | 0 / 1 |
| QuantumMedica | 2026-10-30 | 2026-10-15 | 15 | 1,705,723 | 0 | 1,692,618 (99.231704%) | 0 / 0 |
| Medscape | 2026-10-30 | 2026-10-29 | 1 | 3,659,659 | 0 | 841,805 (23.002280%) | 261 / 966 |
| Endato | 2026-10-30 | NULL | NULL | 5,427,459 | 5,427,459 | 0 (—) | NULL / NULL |
| RocketReach | 2026-10-30 | NULL | NULL | 3,199,535 | 3,199,535 | 0 (—) | NULL / NULL |
| DRDB | 2026-10-30 | NULL | NULL | 826,886 | 826,886 | 0 (—) | NULL / NULL |
| Haymarket | 2026-10-30 | 2021-07-06 | 1,942 | 4,223,245 | 0 | 4,223,245 (100.000000%) | 0 / 0 |

Latest-day percentages use links with a known lag. Lag quantiles use exact nearest ranks over known lags. Stored evaluation days remain unchanged; October 31 extraction does not reevaluate age. Missing or future-dated source history can leave lag unknown. Zero lag can accompany an old feed.

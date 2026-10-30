# Observation counts

**Principle:** repeated identical records measure repetition, not accuracy. Email–NPI deduplication follows metrics and indicators.

**Where:** `iceberg.jteixeira_ipa.pii__int_<vendor>__metrics`, keyed by `source`, `metric_row_id`. Each row represents one exact raw source record and one email position.

## How it is computed

Within each input table, group raw rows only when every original column except `day` agrees. Parse delivery days with `try_cast(day AS date)`; sources without a day use null. Before unfolding email positions, calculate:

```sql
count(*) AS observation_count,
nullif(count(DISTINCT vendor_day), 0) AS observed_day_count,
min(vendor_day) AS first_seen_day,
max(vendor_day) AS last_seen_day,
count_if(vendor_day IS NULL) AS undated_observation_count,
count_if(invalid_vendor_day) AS invalid_day_observation_count
```

`invalid_vendor_day` means a supplied day cannot be parsed. `observed_days` stores sorted unique valid dates, or an empty array. Date bounds and `observed_day_count` stay null when no valid date exists. Changes to other raw fields produce separate records.

Counts repeat across a record's email positions. Their sum measures email-position observations, not raw rows or independent confirmations. `record_id` identifies the source record; `metric_row_id` also includes email position. `record_payload` retains raw values except `day` for inspection.

## Real examples: contrasting outcomes

Selected real records, queried October 30, 2026, from `iceberg.jteixeira_ipa.pii_clean` at snapshot `8096642935433856886`. These examples explain outcomes; they are not prevalence estimates. The stored cleaned email and NPI are shown unchanged, with exact record keys retained in the SQL.

[Runnable example SQL](../../sql/examples/01_observation_counts.sql):

```sql
WITH selected AS (
    SELECT *
    FROM iceberg.jteixeira_ipa.pii_clean FOR VERSION AS OF 8096642935433856886
    WHERE (source = 'endato' AND metric_row_id IN (
        '174DF23ED50299325123B7660ECB3AA68FEDD02FA7345B47D575396DEAF0419A'))
       OR (source = 'healthlink' AND metric_row_id IN (
        '39C2F78FA687F1D8257987C722B350B90A42B9D83BDCB5B4C32B9E8D2EC80905'))
       OR (source = 'medscape' AND metric_row_id IN (
        '1D343DCA154DC149F0A4E90D7B8561D297C4AECDD3C3E710080DF56062E864CE'))
)
SELECT m.source,
       m.email,
       m.npi,
       m.observation_count,
       m.observed_day_count,
       m.first_seen_day,
       m.last_seen_day,
       m.undated_observation_count
FROM selected m
ORDER BY m.source, m.metric_row_id
```

**Result:** 3 rows.

| source | email | npi | observation_count | observed_day_count | first_seen_day | last_seen_day | undated_observation_count |
|---|---|---|---|---|---|---|---|
| endato | arnie.hicks@gmail.com | 1124164199 | 1 | NULL | NULL | NULL | 1 |
| healthlink | joshhagen@live.com | 1205185006 | 237 | 237 | 2026-03-02 | 2026-10-25 | 0 |
| medscape | jonathan.weinkle@gmail.com | 1598891004 | 1 | 1 | 2025-08-07 | 2025-08-07 | 0 |

**What differentiates these cases:** The repeated HealthLink record spans many distinct dates. A single dated Medscape observation has a day count of one, while a single undated Endato observation has NULL date bounds and day count. Observation count cannot substitute for date coverage, and repetition is not independent confirmation.

Stored indicators are unchanged by display helpers. Reproduction requires the pinned snapshot to remain available.

## Statistics by source

[Statistics SQL](../../sql/statistics/01_observation_counts.sql). This standalone read-only equivalent calculates the displayed row counts and percentages from the published table. The saved October 29 tables were derived from the linked grouped-population extraction; this equivalent has been checked locally, not executed against Trino. Its median and P95 use exact weighted nearest-rank quantiles.

Measured October 29, 2026, on `iceberg.jteixeira_ipa.pii_clean` at exact source-record/email-position grain. Percentages use all metric rows within each vendor. Counts are exact and cover all retained history; email–NPI links remain undeduplicated. These are saved measurements, not live counts.

| Source | Metric rows | Email-position observations | Rows repeated, n (%) | Median / P95 / max |
|---|---:|---:|---:|---:|
| HealthLink | 11,156,016 | 1,629,707,643 | 7,219,502 (64.71398%) | 238 / 267 / 267 |
| QuantumMedica | 1,705,723 | 18,701,175 | 1,704,636 (99.93627%) | 11 / 11 / 11 |
| Medscape | 47,072,262 | 297,880,567 | 26,793,275 (56.91946%) | 2 / 29 / 326 |
| Endato | 5,427,459 | 5,427,459 | 0 (0.00000%) | 1 / 1 / 1 |
| RocketReach | 4,864,145 | 4,864,145 | 0 (0.00000%) | 1 / 1 / 1 |
| DRDB | 1,115,415 | 1,115,415 | 0 (0.00000%) | 1 / 1 / 1 |
| Haymarket | 4,223,245 | 4,223,245 | 0 (0.00000%) | 1 / 1 / 1 |

Median and P95 use exact weighted nearest-rank quantiles over metric rows. Repeated means `observation_count > 1`. Observation totals repeat across email positions; they are not raw source-row totals.

Derived row statistics (historical output, not retained: `../../results/documentation_row_statistics.json`) · [Executed population SQL](../../results/metric_population_20261029/grouped.sql) · Measurement metadata (historical output, not retained: `../../results/metric_population_20261029/analysis_metadata.json`) · Published-table validation (historical output, not retained: `../../results/final_build.json`)

[Profile SQL](../../sql/profile.sql) · [Rule SQL](../../macros/record_versions.sql)

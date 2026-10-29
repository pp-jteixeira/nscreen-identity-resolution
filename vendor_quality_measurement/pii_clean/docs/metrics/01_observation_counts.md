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

**Illustrative examples:**

| Input | Metric output |
|---|---|
| Same record on three dates | One row per email position, three observations, three dates. |
| Same email/NPI, changed name on second date | Separate rows; name indicators evaluated separately. |
| Same email in two slots, identical record on three dates | Two rows, each with three observations and three dates. |
| Same undated record twice | One row per email position, two observations, null date bounds. |

Counts repeat across a record's email positions. Their sum measures email-position observations, not raw rows or independent confirmations. `record_id` identifies the source record; `metric_row_id` also includes email position. `record_payload` retains raw values except `day` for inspection.

## Statistics by source

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

Derived row statistics (local-only: `../../results/documentation_row_statistics.json`) · [Executed population SQL](../../results/metric_population_20261029/grouped.sql) · Measurement metadata (local-only: `../../results/metric_population_20261029/analysis_metadata.json`) · Published-table validation (local-only: `../../results/final_build.json`)

[Profile SQL](../../sql/profile.sql) · [Rule SQL](../../macros/record_versions.sql)

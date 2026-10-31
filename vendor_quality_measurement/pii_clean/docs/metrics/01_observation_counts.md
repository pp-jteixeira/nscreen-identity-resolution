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

## Real examples

Executed October 31, 2026, against canonical snapshot `8811920360682490090`. These selected cases explain outcomes; they do not measure prevalence.

[Executed example SQL](../../sql/examples/01_observation_counts.sql):

```sql
WITH selected AS (
    SELECT *
    FROM iceberg.jteixeira_ipa.pii_clean FOR VERSION AS OF 8811920360682490090
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

| source | email | npi | observation_count | observed_day_count | first_seen_day | last_seen_day | undated_observation_count |
|---|---|---|---|---|---|---|---|
| endato | arnie.hicks@gmail.com | 1124164199 | 1 | NULL | NULL | NULL | 1 |
| healthlink | joshhagen@live.com | 1205185006 | 215 | 215 | 2026-03-02 | 2026-10-02 | 0 |
| medscape | jonathan.weinkle@gmail.com | 1598891004 | 1 | 1 | 2025-08-07 | 2025-08-07 | 0 |

**What differentiates these cases:** The repeated HealthLink record spans many distinct dates. A single dated Medscape observation has a day count of one, while a single undated Endato observation has NULL date bounds and day count. Observation count cannot substitute for date coverage, and repetition is not independent confirmation.

## Statistics by source

Measured **October 31, 2026** from `iceberg.jteixeira_ipa.pii_clean` snapshot `8811920360682490090`. These are exact published-population counts across retained eligible history, not a sample. Stored evaluation dates remain unchanged.

[Executed statistics SQL](../../sql/statistics/01_observation_counts.sql)

| Source | Metric records | Email-position observations | Repeated records, n (%) | Median / P95 / max |
|---|---|---|---|---|
| HealthLink | 11,156,016 | 1,494,099,995 | 7,219,502 (64.713980%) | 216 / 245 / 245 |
| QuantumMedica | 1,705,723 | 18,701,175 | 1,704,636 (99.936273%) | 11 / 11 / 11 |
| Medscape | 47,164,366 | 298,710,643 | 26,863,983 (56.958219%) | 2 / 29 / 326 |
| Endato | 5,427,459 | 5,427,459 | 0 (0.000000%) | 1 / 1 / 1 |
| RocketReach | 4,864,145 | 4,864,145 | 0 (0.000000%) | 1 / 1 / 1 |
| DRDB | 1,115,415 | 1,115,415 | 0 (0.000000%) | 1 / 1 / 1 |
| Haymarket | 4,223,245 | 4,223,245 | 0 (0.000000%) | 1 / 1 / 1 |

Repeated means `observation_count > 1`. Quantiles use exact weighted nearest ranks across metric records. Observation totals repeat across email positions and are not raw input-row counts. Repeated deliveries are not independent confirmations.

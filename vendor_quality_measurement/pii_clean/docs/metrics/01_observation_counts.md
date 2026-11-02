# Observation counts

**Principle:** repeated identical deliveries measure repetition, not accuracy. Each metric row is one link: a vendor, an email and an NPI.

**Where:** `iceberg.jteixeira_ipa.pii__int_<vendor>__metrics` and `iceberg.jteixeira_ipa.pii_clean`, keyed by `source`, `link_id`. `link_id` is the SHA256 of source, email and NPI and is unique. Each link merges every source record version that reports this email for this NPI.

## How it is computed

**Versions.** Within each input table, group raw rows only when every identity column agrees; `day` and the schema's volatile fields are ignored. Medscape's volatile fields (raw `email_address` spelling, `huid`, `ip`, `payer_status`, `practice_setting`, `source`, `validated`) are kept as sorted distinct arrays and never split a version. Each version has a `record_id`: the SHA256 of its source table and identity payload. Parse delivery days with `try_cast(day AS date)`; sources without a day use null. For each version:

```sql
count(*) AS observation_count,
nullif(count(DISTINCT vendor_day), 0) AS observed_day_count,
min(vendor_day) AS first_seen_day,
max(vendor_day) AS last_seen_day,
count_if(vendor_day IS NULL) AS undated_observation_count,
count_if(invalid_vendor_day) AS invalid_day_observation_count
```

`invalid_vendor_day` means a supplied day cannot be parsed.

**Links.** Unfold each version's email positions, then collapse to one row per `source`, `email`, `npi`. The [implementation](../../macros/record_versions.sql) derives the link history:

- `observed_days`: sorted unique valid dates across all versions, or an empty array. `observed_day_count`, `first_seen_day` and `last_seen_day` come from these dates and stay null when no valid date exists.
- `observation_count`, `undated_observation_count`, `invalid_day_observation_count`: summed over versions.
- `record_count` and `record_ids`: the number of merged versions and their sorted `record_id` values.
- `latest_record_id`: the version with the unique greatest `last_seen_day`, or the only version. It is null when the link has several undated versions or when the greatest `last_seen_day` is tied.
- `email_origins`: sorted source columns or array positions where the email appeared, across versions.
- `attribute_versions`: one entry per version, ordered by `first_seen_day`, `last_seen_day`, `record_id`, with `record_id`, first and last seen day, observed day count, observation count, email origins and the JSON identity payload `record_payload`. Volatile fields appear as arrays inside the payload. Name or address changes over time are visible here.
- `source_tables` and `source_feeds`: contributing input tables and feed labels.

A version that lists the same email in several positions counts once for the link. Observation totals measure raw source-row observations of the link's versions, not independent confirmations.

## Real examples

Executed November 2, 2026, against `iceberg.jteixeira_ipa.pii_clean` snapshot `2837737034249693554`. These selected cases explain outcomes; they do not measure prevalence.

```sql
SELECT source,
       email,
       npi,
       observation_count,
       undated_observation_count,
       observed_day_count,
       first_seen_day,
       last_seen_day,
       record_count,
       latest_record_id IS NOT NULL AS has_latest_record
FROM iceberg.jteixeira_ipa.pii_clean FOR VERSION AS OF 2837737034249693554
WHERE (source = 'healthlink' AND link_id IN (
        '0000065665E6489027FB5457F8CA2DB2F4AFC16591017C7EBA86A3D71F18463B',
        '000003EF65550016D15786DAA9351C829F608354411ECD4C845B5E20C1276CC8'))
   OR (source = 'medscape' AND link_id IN (
        '0A1FBAAAF884085FEE6166550EDA6A98C21792E871ADDB65D80DABDE3F5A0187'))
   OR (source = 'endato' AND link_id IN (
        '00000359411756A423CF6FA62F7ADEA5FAF7F0213AB36334DF4DE1CD16782DF9'))
   OR (source = 'drdb' AND link_id IN (
        '000016421AFD3B585B294CA0C5360789770F24578685F0F7E0C5C956318A2D3B'))
ORDER BY source, email, npi
```

| source | email | npi | observation_count | undated_observation_count | observed_day_count | first_seen_day | last_seen_day | record_count | has_latest_record |
|---|---|---|---|---|---|---|---|---|---|
| drdb | katherine.chiu.md@gmail.com | 1518040575 | 2 | 2 | NULL | NULL | NULL | 2 | false |
| endato | hhutch2@gmail.com | 1922407774 | 1 | 1 | NULL | NULL | NULL | 1 | true |
| healthlink | jnance219676@cookchildrens.direct-ci.com | 1770745390 | 1 | 0 | 1 | 2026-10-03 | 2026-10-03 | 1 | true |
| healthlink | thomasbusch@outlook.com | 1891374278 | 245 | 0 | 245 | 2026-01-07 | 2026-10-03 | 2 | true |
| medscape | sekar.tumma@gmail.com | 1043657455 | 6 | 0 | 3 | 2024-01-10 | 2024-03-07 | 2 | false |

**What differentiates these cases:** The first HealthLink link was delivered once on a single day (one version, one observation). The second HealthLink link was delivered on 245 distinct days between 2026-01-07 and 2026-10-03 and merges two versions; the version with the unique latest `last_seen_day` is its `latest_record_id`. The Medscape link merges two versions but has no single latest version: the greatest `last_seen_day` is tied between them, so `latest_record_id` is null (`has_latest_record` false). The Endato link is undated: its one observation is undated, so the day count and date bounds are null. The DRDB link is also undated and merges two versions; with no dates to order them, it has no single latest version. Observation counts measure deliveries, not confirmations.

## Statistics by source

Measured **November 2, 2026** from `iceberg.jteixeira_ipa.pii_clean` snapshot `2837737034249693554`. These are exact published-population counts across retained eligible history, not a sample.

Source data period (first to last observed day): HealthLink 2026-01-07 to 2026-10-03; QuantumMedica 2025-09-14 to 2026-10-15; Medscape 2024-01-10 to 2026-11-01; Haymarket 2021-07-06 (a single day). Endato, RocketReach and DRDB are undated.

[Statistics SQL](../../sql/statistics/01_observation_counts.sql) and its [version companion](../../sql/statistics/01_observation_counts_statement_002.sql) report, per source, links, summed observations, repeated links (`observation_count > 1`), exact weighted nearest-rank median, P95 and maximum observation counts, merged versions and links without a single latest version.

| Source | Links | Link observations | Links observed more than once, n (%) | Median observations | P95 observations | Maximum observations |
|---|---:|---:|---:|---:|---:|---:|
| HealthLink | 7,688,451 | 1,494,099,995 | 6,465,136 (84.088928%) | 245 | 245 | 303 |
| QuantumMedica | 1,705,723 | 18,701,175 | 1,704,636 (99.936273%) | 11 | 11 | 11 |
| Medscape | 3,661,537 | 301,238,083 | 3,622,208 (98.925888%) | 32 | 346 | 1,065 |
| Endato | 5,427,459 | 5,427,459 | 0 (0.000000%) | 1 | 1 | 1 |
| RocketReach | 3,199,535 | 3,199,535 | 0 (0.000000%) | 1 | 1 | 1 |
| DRDB | 826,886 | 1,115,415 | 219,146 (26.502565%) | 1 | 3 | 3 |
| Haymarket | 4,223,245 | 4,223,245 | 0 (0.000000%) | 1 | 1 | 1 |

**Versions per link**

| Source | Links | Versions | Multi-version links, n (%) | Maximum versions per link | Links without a single latest version, n (%) |
|---|---:|---:|---:|---:|---:|
| HealthLink | 7,688,451 | 11,156,016 | 2,995,627 (38.962686%) | 7 | 202 (0.002627%) |
| QuantumMedica | 1,705,723 | 1,705,723 | 0 (0.000000%) | 1 | 0 (0.000000%) |
| Medscape | 3,661,537 | 3,765,035 | 86,484 (2.361959%) | 41 | 31 (0.000847%) |
| Endato | 5,427,459 | 5,427,459 | 0 (0.000000%) | 1 | 0 (0.000000%) |
| RocketReach | 3,199,535 | 3,199,535 | 0 (0.000000%) | 1 | 0 (0.000000%) |
| DRDB | 826,886 | 1,115,415 | 219,146 (26.502565%) | 3 | 219,146 (26.502565%) |
| Haymarket | 4,223,245 | 4,223,245 | 0 (0.000000%) | 1 | 0 (0.000000%) |

Percentages use all links within each source. Repeated deliveries are not independent confirmations. Counts across vendors can overlap and must not be added.

Endato, RocketReach and Haymarket deliver each link once (median, P95 and maximum of 1), and Haymarket has a single delivery day. HealthLink repeats 84.09% of its links, with a median of 245 observations. Medscape repeats 98.93% of its links, with a median of 32 and a maximum of 1,065. QuantumMedica repeats nearly every link (median, P95 and maximum of 11).

HealthLink links merge up to 7 versions (38.96% of its links have more than one) and Medscape links up to 41 (2.36%). All 219,146 multi-version DRDB links (26.50%) lack a single latest version, because DRDB has no delivery days to order versions. HealthLink has 202 and Medscape 31 links without a single latest version, from tied last-seen days.

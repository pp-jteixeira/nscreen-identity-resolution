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

No examples have been executed against this definition yet.

Cases worth contrasting: a dated link with many observed days, a dated link observed once, an undated link with null date bounds and day count, and a link with several versions where `attribute_versions` shows changed attributes. A link without a single latest version shows null `latest_record_id`.

## Statistics by source

No measurements exist yet for this definition. [Statistics SQL](../../sql/statistics/01_observation_counts.sql) reports, per source, metric rows (links), summed observations, repeated links (`observation_count > 1`) and exact weighted nearest-rank median, P95 and maximum observation counts.

Repeated deliveries are not independent confirmations. Counts across vendors can overlap and must not be added.

# Email matches source name

**Question:** does the email's mailbox text resemble a name supplied by this vendor? A match is name evidence, not proof of ownership.

**Where:** `email_matches_source_name` in `iceberg.jteixeira_ipa.pii__int_<vendor>__metrics`, keyed by `source`, `metric_row_id`. Vendors: `healthlink`, `quantummedica`, `medscape`, `endato`, `rocketreach`, `drdb`, `haymarket`. Inputs and name parsing are listed in the [source map](../00_source_map.md#name-comparison-inputs).

## How it is computed

Normalize each paired first/last name: uppercase, supported accents removed, spaces/hyphens/apostrophes retained; empty, `NULL`, `NaN` and `\N` become missing. Expand first names through the [nickname list](../../seeds/nicknames.csv). Reduce the email mailbox to lowercase letters:

```sql
regexp_replace(lower(regexp_extract(email, '^([^@]*)@', 1)), '[^a-z]', '') AS local_letters
```

For each usable name, compute `source_match` using these rules:

- Both first and last names occur anywhere; each needs two letters.
- Or the local part starts with the first initial and ends with the last name, or the reverse. It must be longer than the last name.
- Or a local part of six or more letters differs by at most one insertion, deletion or substitution from first+last, last+first, initial+last or last+initial.

A usable name needs at least one first-name letter and two last-name letters. `source_name_usable` records availability. Within `source`, `metric_row_id`, any matching comparison gives true; usable comparisons with no match give false; all-null comparisons stay unknown.

```sql
bool_or(source_match) AS email_matches_source_name
```

Names stay paired within their source record. Changed source records stay separate. HealthLink alone attaches distinct HCP-reference names by NPI across retained history, without date alignment. Repeated observations add no weight.

**Illustrative examples:** `bobsmith@example.test` matches ROBERT SMITH; `jsmith@example.test` can match both JOHN SMITH and JANE SMITH; no usable name means unknown. Format validation is separate. RocketReach and DRDB full-name parsing can mistake titles or suffixes for name parts.

## Statistics by source

[Statistics SQL](../../sql/statistics/05_email_matches_source_name.sql). This standalone read-only equivalent calculates the displayed row counts and percentages from the published table. The saved October 29 tables were derived from the linked grouped-population extraction; this equivalent has been checked locally, not executed against Trino.

Measured October 29, 2026, on `iceberg.jteixeira_ipa.pii_clean` at exact source-record/email-position grain. Percentages use all metric rows within each vendor. Counts are exact and cover all retained history; email–NPI links remain undeduplicated. These are saved measurements, not live counts.

| Source | Metric rows | Match, n (%) | No match, n (%) | Unknown, n (%) |
|---|---:|---:|---:|---:|
| HealthLink | 11,156,016 | 7,587,293 (68.01078%) | 3,568,038 (31.98308%) | 685 (0.00614%) |
| QuantumMedica | 1,705,723 | 0 (0.00000%) | 1 (0.00006%) | 1,705,722 (99.99994%) |
| Medscape | 47,072,262 | 24,943,545 (52.98990%) | 21,969,572 (46.67201%) | 159,145 (0.33809%) |
| Endato | 5,427,459 | 1,999,756 (36.84516%) | 3,427,481 (63.15075%) | 222 (0.00409%) |
| RocketReach | 4,864,145 | 2,977,399 (61.21115%) | 1,884,149 (38.73546%) | 2,597 (0.05339%) |
| DRDB | 1,115,415 | 788,347 (70.67746%) | 321,591 (28.83151%) | 5,477 (0.49103%) |
| Haymarket | 4,223,245 | 2,528,601 (59.87341%) | 1,502,730 (35.58235%) | 191,914 (4.54423%) |

Unknown is null, not false. Name outcomes can differ across records sharing the same email/NPI. These row counts do not establish distinct-email outcome counts.

Derived row statistics (local-only: `../../results/documentation_row_statistics.json`) · [Executed population SQL](../../results/metric_population_20261029/grouped.sql) · Measurement metadata (local-only: `../../results/metric_population_20261029/analysis_metadata.json`) · Published-table validation (local-only: `../../results/final_build.json`)

[Profile SQL](../../sql/name_match_profile.sql) · [Rule SQL](../../macros/name_matching.sql)

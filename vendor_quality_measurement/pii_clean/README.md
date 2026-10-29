# PII Clean V3

V3 evaluates vendor records across all retained source history. Metrics and indicators precede email–NPI deduplication. Scoring remains unimplemented.

Documentation reconciled against local code and saved validation on October 29, 2026. Warehouse state below is the last verified state, not a fresh live inspection.

| Output | Columns | Availability |
|---|---:|---|
| Published `iceberg.jteixeira_ipa.pii_clean` | 41 | Stored record attributes and metrics through shared state. |
| Local vendor/final models | 103 | Published fields plus five unpublished groups: facility, specialty, lifecycle, vendor/facility state and cookie location. |
| Complete email lookup | 109 | All 103 model fields plus six display/comparison fields, computed read-only for one email. |

| Layer | Responsibility |
|---|---|
| [Staging](models/staging/README.md) | Preserve every raw row and column; add cleaned helpers. |
| [Intermediate](models/intermediate/README.md) | Combine otherwise-identical raw records across days, unfold email positions, attach reference evidence and compute metrics. |
| [Final](models/final/README.md) | Union the seven vendor metric views into `iceberg.jteixeira_ipa.pii_clean`, preserving record grain. |

## What one metric row means

One row represents one exact source record and one email position. Its key is `source`, `metric_row_id`. Multiple rows can report the same email–NPI link. A reported link is evidence, not proof of ownership.

Raw rows combine only when every original column except `day` agrees. Changes to names, addresses, feeds, identifiers, raw casing/whitespace, arrays or other timestamps produce separate records. Different source tables also stay separate. Identical records can combine across nonconsecutive dates. No latest-partition selection applies.

| Column | Meaning |
|---|---|
| `record_id` | SHA256 of source-table identity and raw record payload excluding `day`. |
| `record_payload` | JSON text containing every raw identity field except `day`. Top-level timestamps, dates and decimals are serialized as strings. |
| `email_ordinal`, `email_origin` | Original email position and source field/token/array location. Duplicate email positions remain separate. |
| `metric_row_id` | SHA256 of `record_id` and email position. |
| `observed_days`, `conflict_days` | Exact source dates for the record and the subset with same-day NPI conflicts. Empty for undated vendors. |
| `first_seen_day`, `last_seen_day`, `observed_day_count`, `observation_count` | History of that exact raw record; see [observation counts](docs/metrics/01_observation_counts.md). |

**Illustrative example:** JOHN SMITH and JANE JONES share an email/NPI in different deliveries. Both records remain, with separate name indicators. An unchanged JOHN SMITH record repeated on two dates combines and records two observations.

Names normally come from the exact email-bearing record. HealthLink uses its separate HCP reference by NPI; registry comparisons also join by NPI. These reference joins use readable name variants without historical date alignment. Neither reference comparison merges source records.

Only nonempty cleaned email/NPI keys enter metric outputs. Missing-key records remain in staging. Malformed nonempty values remain available for indicators. Endato attributes returned person-email slots; provider-input email fields are excluded. RocketReach uses its array plus recommended/current fields; QuantumMedica unfolds pipe-separated values. DRDB retains both input tables separately. See the [source map](docs/00_source_map.md).

## Unpublished metric implementations

[Facility overlap](docs/metrics/15_conflicting_npis_share_facility.md) is implemented locally and measured through read-only Trino queries. Existing warehouse views and the published table do not yet contain its five new evidence/metric columns. The [measurement summary](results/conflicting_facilities_summary.md) gives coverage, outcomes, examples and validation. Publication remains pending.

[Specialty overlap](docs/metrics/16_conflicting_npis_share_specialty.md) is also implemented locally and measured read-only. It uses exact recognized NPPES taxonomy codes across all fifteen slots, with no broad-label fallback. Its five new columns remain unpublished. See [coverage, outcomes and validation](results/conflicting_specialties_summary.md).

[NPI registry status](docs/metrics/17_npi_registry_status.md) adds current NPPES lifecycle evidence, preserving deactivation/reactivation dates, replacement values and uncertainty reasons. Its eleven columns are implemented locally and measured read-only; publication is pending. It does not rewrite links or infer activity on historical vendor dates. See [per-vendor counts and validation](results/registry_status_summary.md).

[Vendor/facility state](docs/metrics/18_vendor_facility_state.md) and [cookie-location evidence](docs/metrics/19_cookie_location_evidence.md) are implemented locally. The latest complete local suite passed all 58 tests, including the complete email lookup. They add eleven and thirty descriptive columns respectively, without filtering records or adding scores. Native Trino fixtures, all seven vendor plans and full-population read-only measurements passed on October 29, 2026. All 75,564,265 metric rows were retained with no invariant failures. Usable untied cookie locations cover 2,728,645 of 26,730,605 source/email/NPI links (10.21%). October 29 evaluation uses October 22–28; source inspection found six mapping dates and seven geo dates. See [the evidence contract and validation status](results/location_evidence_summary.md). These columns remain unpublished.

## Validation and measurements

Intermediate contains [nine SQL models](models/intermediate/README.md): one CTE pipeline per vendor and two shared lookups. Staging and final remain separate. Legacy helper views are outside the managed build graph.

The managed build contains 23 dependency views and `iceberg.jteixeira_ipa.pii_clean`. The published table contains 75,564,265 metric rows with the previously published record attributes and indicators, including raw `record_payload`, normalized names/states and comparison details. The local final model remains a plain `UNION ALL`; its newly added fields are not yet published. It represents 26,730,605 distinct source/email/NPI links. Counts measured October 29, 2026.

| Vendor | Metric rows | Distinct email–NPI links | Distinct emails |
|---|---:|---:|---:|
| HealthLink | 11,156,016 | 7,688,451 | 7,688,331 |
| QuantumMedica | 1,705,723 | 1,705,723 | 1,705,695 |
| Medscape | 47,072,262 | 3,659,306 | 3,550,052 |
| Endato | 5,427,459 | 5,427,459 | 5,324,318 |
| RocketReach | 4,864,145 | 3,199,535 | 3,163,679 |
| DRDB | 1,115,415 | 826,886 | 819,454 |
| Haymarket | 4,223,245 | 4,223,245 | 4,223,245 |

The October 29 publication check matched every then-published vendor view’s row count and substantive-column checksum to the 41-column final table. Previous metrics and record attributes were checked separately against the saved baseline. These checks predate the five unpublished additions and do not validate a full rebuild of the current 103-column models. `computed_at` is excluded from checksum comparisons because it records query time.

Measured counts and SQL (local-only: `results/conflicting_states_measurements.json`) · Native validation and preservation (local-only: `results/conflicting_states_native_validation.json`) · Local tests (local-only: `results/conflicting_states_local_tests.txt`) · Final publication (local-only: `results/final_build.json`)

## Run and test

From this directory, using the repository `.venv` and PulsePoint Trino connection:

```bash
# Build all normal views and the final table
../../.venv/bin/python tools/pipeline.py build

# Refresh only the final table from existing views
../../.venv/bin/python tools/pipeline.py final

# Inspect, create and evaluate one vendor
../../.venv/bin/python tools/pipeline.py render --model stg_healthlink__email
../../.venv/bin/python tools/pipeline.py source --source healthlink
../../.venv/bin/python tools/pipeline.py test --source healthlink
../../.venv/bin/python tools/pipeline.py report --source healthlink
../../.venv/bin/python tools/pipeline.py report --source healthlink --metric email_role_account
../../.venv/bin/python tools/pipeline.py report --source all --metric email_domain_class
../../.venv/bin/python tools/pipeline.py report --source all --metric email_matches_source_name
../../.venv/bin/python tools/pipeline.py report --source all --metric email_matches_registry_name
../../.venv/bin/python tools/pipeline.py report --source all --metric vendor_name_matches_registry_name
../../.venv/bin/python tools/pipeline.py report --source all --metric email_npi_count
../../.venv/bin/python tools/pipeline.py report --source all --metric has_been_reassigned
../../.venv/bin/python tools/pipeline.py report --source all --metric has_conflict_linkage
../../.venv/bin/python tools/pipeline.py report --source all --metric email_name_count
../../.venv/bin/python tools/pipeline.py report --source all --metric email_npi_has_name_conflict
../../.venv/bin/python tools/pipeline.py report --source all --metric conflicting_npis_share_name
../../.venv/bin/python tools/pipeline.py report --source all --metric conflicting_npis_share_state
```

Use `--source all` to apply source, test or report to every vendor separately. Source commands recreate selected staging/intermediate views and shared name dependencies; they do not refresh the published final table. `build` recreates all 23 dependency views once, then atomically replaces `pii_clean`. If the seven-vendor union exceeds Trino’s stage limit, the local runner builds one uniquely named candidate table in vendor batches, validates its schema, counts, checksums and metrics, then atomically replaces the final table from that candidate. Candidate tables remain for audit; they are not automatically deleted. This fallback has local failure-path tests; warehouse execution remains unverified. `final` replaces only the table. Both compare per-vendor row counts and checksums of every substantive column with the live source views and test evidence integrity. `computed_at` records materialization time in the table. Source snapshots are not pinned; concurrent source changes can fail checksum validation. Build SQL and validation are saved in `results/final_build.json`.

The latest saved complete local run (local-only: `results/email_lookup_full_local_tests.txt`) passed 58 tests. Historical metric-specific logs preserve their smaller suite sizes. Tests include local synthetic execution, live raw-versus-staging row counts and intermediate integrity checks. Local fixtures run translated SQL in DuckDB; they do not replace Trino checks. Install local test dependencies from [requirements-dev.txt](requirements-dev.txt). The runner renders Jinja; dbt itself is not the execution engine, and Spark has not been tested.

After publication of the respective metrics, report commands are:

```bash
../../.venv/bin/python tools/pipeline.py report --source all --metric conflicting_npis_share_facility
../../.venv/bin/python tools/pipeline.py report --source all --metric conflicting_npis_share_specialty
../../.venv/bin/python tools/pipeline.py report --source all --metric npi_registry_status
../../.venv/bin/python tools/pipeline.py report --source all --metric vendor_state_evidence
../../.venv/bin/python tools/pipeline.py report --source all --metric cookie_location_status
```

The [complete single-email lookup](docs/email_lookup.md) now computes all implemented metric groups read-only, including unpublished fields. The linked published-table shortcut is explicitly a subset. No warehouse publication is required to run the complete lookup.

## Documentation

References labelled **local-only** identify saved measurement outputs or validation logs excluded from Git. Paths are relative to the document containing them. These files can contain warehouse extracts and are not included in a fresh checkout. Reports, models, queries and tools are versioned; the nickname seed is an explicit exception to the CSV ignore rule. Dated statistics remain documented, but their saved execution evidence requires the local artifacts. Re-running queries against changing references does not reproduce the original snapshot automatically.

Email investigation: [Email lookup query and metric reference](docs/email_lookup.md). Enter one email to inspect names, states, NPIs, history and quality indicators per source record.

1. [Source map](docs/00_source_map.md): input tables, name joins and date limitations.
2. [Metrics](docs/metrics/README.md): definitions, examples and source statistics.
3. [Final table](models/final/README.md): grain, refresh and inspection.

See [project instructions](INSTRUCTIONS.md) and [model details](models/README.md).

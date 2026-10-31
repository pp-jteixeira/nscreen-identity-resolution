# PII Clean

PII Clean evaluates vendor records across all retained source history. Metrics and indicators precede email–NPI deduplication. Scoring remains unimplemented.

[Table dependency diagrams](docs/table_dependencies.md) cover vendor lineage, shared references and exact model inputs. All [26 metric pages](docs/metrics/README.md) contain real examples and population statistics refreshed October 31, 2026; their SQL is pinned to the verified canonical snapshot.

**Published and verified, October 31, 2026:** `iceberg.jteixeira_ipa.pii_clean` contains **75,656,369 records across all seven sources**, with 154 stored fields, at snapshot `8811920360682490090`. Stored core has 124 fields. Final enrichment adds thirty actual cookie fields over October 28–30. Both cookie inputs lack October 30, recorded explicitly as `missing_source_days`. All core values, keys and counts were preserved through enrichment, and cookie integrity checks passed. See [build evidence and recovery](docs/build_recovery.md).

The earlier October 30 stability publication had 114 columns and 75,564,265 metric rows. It preserved all 108 previous fields and rows, including stored freshness dates and `computed_at`. These are historical checkpoints; earlier measurements retain their extraction dates.

| Output | Columns | Availability |
|---|---:|---|
| Canonical `iceberg.jteixeira_ipa.pii_clean` | 154 | Published and verified across all seven sources: 75,656,369 records. |
| Vendor metric views | 124 | Core attributes and metrics. Cookie processing runs separately downstream. |
| Local vendor models | 124 | Include twelve metric 22 fields, eight vendor specialty/profession fields and twenty sequential-history/supersession fields. Published in the complete canonical table. |
| Complete email lookup | 160 | Runs against the current 154-column table. Includes Medscape and all six other sources. |

| Layer | Responsibility |
|---|---|
| [Staging](models/staging/README.md) | Preserve every raw row and column; add cleaned helpers. |
| [Intermediate](models/intermediate/README.md) | Combine otherwise-identical raw records across days, unfold email positions, attach reference evidence and compute metrics. |
| [Final](models/final/README.md) | Store cookie-enriched output from materialized core in `iceberg.jteixeira_ipa.pii_clean`, preserving record grain. |

The local NPPES specialty flag is `conflicting_npis_share_nppes_specialty`. Current views and the canonical table use the renamed flag. The historical 114-field snapshot used `conflicting_npis_share_specialty`. Updated specialty reports and debug queries require the renamed schema. Historical statistics/example SQL retains the original field name for reproducibility.

## Independent cookie enrichment

Vendor metric models contain 124 core fields. Their union is stored in `int_pii__metrics`. The downstream `int_cookie__metrics` computes thirty actual cookie fields over three completed days, and `pii_clean` stores the resulting 154 fields. `tools/pipeline.py cookies` republishes cookie enrichment from stored core. [Architecture, commands and validation](docs/cookie_stage.md). Core publication never scans raw cookie mappings or geo observations.

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

Only nonempty cleaned email/NPI keys enter metric outputs. Medscape additionally excludes every NPI present in the cumulative opt-out feed before computing intermediate metrics. [Opt-out policy and validation](docs/medscape_optout.md) describe the published exclusion. Missing-key records remain in staging. Malformed nonempty values remain available for indicators. Endato attributes returned person-email slots; provider-input email fields are excluded. RocketReach uses its array plus recommended/current fields; QuantumMedica unfolds pipe-separated values. DRDB retains both input tables separately. See the [source map](docs/00_source_map.md).

## Vendor specialty and profession metrics

[Vendor specialty overlap](docs/metrics/23_conflicting_npis_share_vendor_specialty.md) and [vendor profession overlap](docs/metrics/24_conflicting_npis_share_vendor_profession.md) compare exact normalized vendor labels between conflicting NPIs. Metadata joins use the same delivery day and NPI, plus Medscape registration `guid`. HealthLink and DRDB contribute specialty fields; only QuantumMedica and Medscape expose supported profession fields. All eight fields are published across the complete seven-source population. Native Medscape integrity checks passed, and the six recovered vendors preserved every previously validated core field. [Build evidence](docs/build_recovery.md).

## Published metric implementations

[Facility overlap](docs/metrics/15_conflicting_npis_share_facility.md) is published in vendor views and the final table, with current examples and statistics measured from the October 31 snapshot. The [measurement summary](results/conflicting_facilities_summary.md) gives coverage, outcomes, examples and validation. Full publication and integrity checks passed on October 29, 2026.

[NPPES specialty overlap](docs/metrics/16_conflicting_npis_share_specialty.md) uses exact recognized NPPES taxonomy codes across all fifteen slots, with no broad-label fallback. Its five evidence columns were published under the original flag name `conflicting_npis_share_specialty`. Current views and the canonical table use `conflicting_npis_share_nppes_specialty`. Vendor specialty/profession comparisons are separate metrics. See [coverage, outcomes and validation](results/conflicting_specialties_summary.md).

[NPI registry status](docs/metrics/17_npi_registry_status.md) adds current NPPES lifecycle evidence, preserving deactivation/reactivation dates, replacement values and uncertainty reasons. Its eleven evidence/status columns are published and passed native integrity checks. It does not rewrite links or infer activity on historical vendor dates. See [per-vendor counts and validation](results/registry_status_summary.md).

[Vendor/facility state](docs/metrics/18_vendor_facility_state.md) and [cookie-location evidence](docs/metrics/19_cookie_location_evidence.md) are published with eleven and thirty descriptive fields respectively, without filtering records or assigning scores. Current metric pages contain October 31 examples and population statistics from the complete publication. Cookies use October 28–30; each input has two available days and explicitly flags October 30 as missing. The standalone statistical checks use the stored window length and passed native execution.

[Link freshness](docs/metrics/20_link_freshness.md) separates vendor source age from link lag. Its five published columns use retained vendor observation dates, with no thresholds or scoring. Missing dates stay unknown. The October 30 publication preserved every existing field, row and stored evidence date.

[Link stability](docs/metrics/21_link_stability.md) publishes distinct email/link/conflict day counts, presence and overlap fractions, and an incomplete-date flag. It measures dated history without adding thresholds or scores. One-day histories and undated peers remain visible.

[NPI validity and entity type](docs/metrics/22_npi_identity.md) has twelve fields in vendor views and the complete 154-field publication. Native core integrity checks passed. The metric page retains separately dated candidate measurements for reproducibility.

## Sequential history and registration supersession

[Sequential history](docs/metrics/25_sequential_history.md) adds source/email delivery-version counts, set changes, swaps, flip-backs and ordered daily cumulative evidence. It reads all retained eligible observations through `sequence_as_of_day`, default Europe/Paris today. HealthLink and QuantumMedica collapse consecutive repeated delivery content. Daily evidence never uses later NPI observations. Unknown dates stay explicit.

[Medscape registration supersession](docs/metrics/26_registration_supersession.md) compares observations within source/GUID/email. It preserves older claims, flags ambiguous latest NPIs and treats missing chronology as unknown. These fields are published for Medscape; other vendors receive `not_applicable`. Existing presence/overlap and conflict definitions remain unchanged. Complete Medscape core measurements found 109,120 superseded registration links and 3,551,648 latest-observed links. Real examples and exact stored-field queries appear in the metric pages.

## Validation and measurements

Intermediate contains [eleven SQL models](models/intermediate/README.md): seven vendor pipelines, two shared name lookups, the stored core union and downstream cookie enrichment. Staging and final remain separate. Legacy helper views are outside the managed build graph.

The following counts were queried from complete canonical snapshot `8811920360682490090` on October 31, 2026. It contains 75,656,369 records and 26,730,958 distinct source/email/NPI links. Medscape uses newer pinned source inputs; the six recovered vendors preserve their earlier values. Email counts overlap across vendors. See [build evidence](docs/build_recovery.md).

| Vendor | Metric rows | Distinct email–NPI links | Distinct emails |
|---|---:|---:|---:|
| HealthLink | 11,156,016 | 7,688,451 | 7,688,331 |
| QuantumMedica | 1,705,723 | 1,705,723 | 1,705,695 |
| Medscape | 47,164,366 | 3,659,659 | 3,550,359 |
| Endato | 5,427,459 | 5,427,459 | 5,324,318 |
| RocketReach | 4,864,145 | 3,199,535 | 3,163,679 |
| DRDB | 1,115,415 | 826,886 | 819,454 |
| Haymarket | 4,223,245 | 4,223,245 | 4,223,245 |

The historical October 30 stability publication contained 75,564,265 records and 26,730,605 source/email/NPI links. Its earlier October 29 full build matched every vendor's substantive-column checksum to the then-current 103-column final table, excluding query-time `computed_at`. The October 31 core-to-final preservation check includes `computed_at` and every other core field. All sixteen rebuilt Medscape core checks and final cookie checks passed.

Measured counts and SQL (historical output, not retained: `results/conflicting_states_measurements.json`) · Native validation and preservation (historical output, not retained: `results/conflicting_states_native_validation.json`) · Local tests (historical output, not retained: `results/conflicting_states_local_tests.txt`) · Final publication (historical output, not retained: `results/final_build.json`)

## Run and test

From this directory, using the repository `.venv` and PulsePoint Trino connection:

```bash
# Build all normal views and the final table
../../.venv/bin/python tools/pipeline.py build

# Compute cookies and publish the final table from stored core
../../.venv/bin/python tools/pipeline.py final

# Skip the oversized combined plan and build validated vendor batches
../../.venv/bin/python tools/pipeline.py core --vendor-batches

# Rebuild the development table directly, then validate after all vendor batches
../../.venv/bin/python tools/pipeline.py core --direct

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
../../.venv/bin/python tools/pipeline.py report --source all --metric link_freshness
../../.venv/bin/python tools/pipeline.py report --source all --metric link_stability
../../.venv/bin/python tools/pipeline.py report --source all --metric npi_identity
```

Use `--source all` to apply source, test or report to every vendor separately. The `report` command reads `iceberg.jteixeira_ipa.pii_clean` filtered to the requested vendor. Reports use stored evidence and evaluation dates, so changes to raw data or model code appear only after publication. Report metadata records the published relation and vendor. Source and candidate validation continue to inspect their respective build inputs. Source commands recreate selected staging/intermediate views and shared name dependencies; they do not refresh the published final table. `build` recreates source dependencies, builds stored core, then publishes cookie-enriched `pii_clean`. `final` reads stored core.

Core builds can use a validated candidate or write directly with `core --direct`. Stage-limit fallback materializes narrow execution inputs before attaching later metrics. The core contract contains 124 fields and requires all seven sources, unique keys and sixteen integrity checks. `final` then computes actual cookie fields from stored core. It verifies all 124 core fields, including `computed_at`, are unchanged and checks cookie invariants. Source snapshots are not pinned by ordinary core builds. Checkpoints are printed without saving local result files.

The October 31 recovery verified all sixteen Medscape email batches against pinned raw key/history checksums. All sixteen native core integrity checks passed for the rebuilt Medscape population. The six recovered vendors matched all 124 previously validated fields, including `computed_at`. Final enrichment preserved the complete core population and passed cookie integrity checks.

Current validation covers core/cookie separation, three-day boundaries, email-batch equivalence, sequential history, registration supersession and publication failure handling. Latest suite and warehouse outcomes are recorded in the [execution checkpoint](docs/build_recovery.md). The earlier lookup checkpoint (historical output, not retained: `results/email_lookup_full_local_tests.txt`) passed 58 tests. Historical metric-specific checkpoints report their smaller suite sizes in the documentation; result logs are not retained. Local tests cover synthetic execution and publication control flow. Separate warehouse checks cover live raw-versus-staging row counts and intermediate integrity. Local fixtures run translated SQL in DuckDB; they do not replace Trino checks. Install local test dependencies from [requirements-dev.txt](requirements-dev.txt). The runner renders Jinja; dbt itself is not the execution engine, and Spark has not been tested.

All 21 profile SQL files remain templates for reusable validation. `tools/pipeline.py` supplies published rows through `render_profile(filename, source=None)` and renders any metric macros. A specific `source` restricts the input before aggregation; omitting it profiles all vendors. Existing `report` commands use this renderer. For the general observation profile, render SQL from the project directory:

```bash
PYTHONPATH=tools ../../.venv/bin/python -c 'import pipeline; print(pipeline.render_profile("profile.sql"))'
```

The facility debug query directly unnests stored peer comparisons from `pii_clean`; it does not rebuild facility reference joins. On October 29, 2026, all 15 profiles passed native validation for the all-vendor input and full execution for Endato, including source-scope and reported integrity checks. The facility debug query passed native validation and a 100-row execution check. SQL, query metadata and check outcomes are historical output, not retained: `results/published_profiles_validation_20261029.json`; the execution artifact is no longer retained.

Report commands for the published metrics are:

```bash
../../.venv/bin/python tools/pipeline.py report --source all --metric conflicting_npis_share_facility
../../.venv/bin/python tools/pipeline.py report --source all --metric conflicting_npis_share_nppes_specialty
../../.venv/bin/python tools/pipeline.py report --source all --metric conflicting_npis_share_vendor_specialty
../../.venv/bin/python tools/pipeline.py report --source all --metric conflicting_npis_share_vendor_profession
../../.venv/bin/python tools/pipeline.py report --source all --metric npi_registry_status
../../.venv/bin/python tools/pipeline.py report --source all --metric vendor_state_evidence
../../.venv/bin/python tools/pipeline.py report --source all --metric cookie_location_status
```

The [complete single-email lookup](docs/email_lookup.md) selects 154 model fields and six helpers from the complete seven-source canonical table. The shorter shortcut selects a subset of the same stored data. The lookup uses stored evaluation dates and does not repeat reference joins.

## Documentation

Historical execution outputs and validation logs are not retained locally or in Git. References labelled **historical output, not retained** identify the original extraction provenance only. Dated findings remain in Markdown, and SQL sources remain available for reruns. Reports and measurement tools display results on stdout. Notebook outputs must be cleared before saving. The nickname reference seed is a model dependency, not an exported dataset. Changing warehouse references means a later query may not reproduce a dated measurement.

Email investigation: [Email lookup query and metric reference](docs/email_lookup.md). Enter one email to inspect names, states, NPIs, history and quality indicators per source record.

1. [Source map](docs/00_source_map.md): input tables, name joins and date limitations.
2. [Metrics](docs/metrics/README.md): definitions, examples and source statistics.
3. [Final table](models/final/README.md): grain, refresh and inspection.

See [project instructions](INSTRUCTIONS.md) and [model details](models/README.md).

## Direct core-table builds

`core --direct` writes source batches directly into `iceberg.jteixeira_ipa.pii__int_pii__metrics`, avoiding a separate complete core candidate and copy. The core remains partial until all sources finish. `--resume` retains existing source batches after schema and key checks and assumes those sources are complete.

Medscape recovery uses `tools/build_medscape_batches.py` to bound transaction sizes. Each normalized email stays entirely within one of sixteen hash buckets. Expected raw keys and observation-history checksums determine whether a bucket is complete before it can be skipped. Do not use source-level resume as proof that partial email batches are complete. [Recovery details](docs/build_recovery.md).

The final table is built from actual cookie-enriched core output. No pending cookie columns are added to core. [Cookie workflow](docs/cookie_stage.md).

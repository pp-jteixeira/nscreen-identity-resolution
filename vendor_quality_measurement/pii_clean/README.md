# PII Clean

PII Clean evaluates vendor-reported email–NPI links across all retained source history. The output `iceberg.jteixeira_ipa.pii_clean` has one row per link: a source, a cleaned email and a reported NPI, keyed by `link_id`. Metrics and indicators precede any cross-vendor deduplication. Scoring remains unimplemented.

[Table dependency diagrams](docs/table_dependencies.md) cover vendor lineage, shared references and exact model inputs. The [28 metric pages](docs/metrics/README.md) define each metric and link its statistics SQL. The table was published on November 2, 2026 at snapshot `2837737034249693554`: 26,732,836 links (HealthLink 7,688,451, Endato 5,427,459, Haymarket 4,223,245, Medscape 3,661,537, RocketReach 3,199,535, QuantumMedica 1,705,723, DRDB 826,886), each source verified against stored core. That snapshot stores 165 fields; the 15 fields of metric pages 27 and 28 are stored from the next build.

| Output | Columns | Contents |
|---|---:|---|
| Canonical `iceberg.jteixeira_ipa.pii_clean` | 180 | 139 core fields, 10 domain fields and 31 cookie fields, with stored name explanations. |
| Vendor metric views | 139 | Core attributes, metrics and stored name explanations. Cookie processing runs separately downstream. |
| Stored core `pii__int_pii__metrics` | 139 | Union of the seven vendor outputs. |
| Complete email lookup | 171 | All 165 stored fields plus six display/comparison helpers. |

| Layer | Responsibility |
|---|---|
| [Staging](models/staging/README.md) | Preserve every raw row and column; add cleaned helpers. |
| [Intermediate](models/intermediate/README.md) | Group raw rows into versions, unfold email positions, collapse to links, attach reference evidence and compute metrics. |
| [Final](models/final/README.md) | Store cookie-enriched output from materialized core in `iceberg.jteixeira_ipa.pii_clean`, preserving link grain. |

The local NPPES specialty flag is `conflicting_npis_share_nppes_specialty`.

## Independent cookie enrichment

Vendor models define 139 core fields, including four stored name-explanation fields. Their union is stored in `int_pii__metrics`. The downstream `int_cookie__metrics` filters and enriches each source independently with domain aggregates and cookie evidence over three completed days, then combines the 180-field outputs. The runner writes source batches separately and reuses pinned inputs on resume. Stored core is the preservation baseline for cookie refreshes. `tools/pipeline.py cookies` republishes cookie enrichment from stored core. [Architecture, commands and validation](docs/cookie_stage.md). Core publication never scans raw cookie mappings or geo observations.

## Stored name explanations

[Name explanations](docs/name_match_evidence.md) retain distinct normalized name comparisons, component match kinds and all aggregate classes for each link, across every usable vendor name of its versions. The three nullable booleans aggregate those comparisons. Comparisons reuse the shared name join and aggregate to link grain. No score or cross-vendor vote is introduced.

## What one row means

One row represents one source/email/NPI link. Its key is `link_id`, the SHA256 of source, email and NPI. A reported link is evidence, not proof of ownership.

Each vendor model first groups raw rows into **versions**. Raw rows form one version when every identity field agrees except `day` and the schema's volatile fields. Volatile fields are listed under `volatile` in [record_schemas.json](models/record_schemas.json); Medscape declares `email_address` (raw spelling), `huid`, `ip`, `payer_status`, `practice_setting`, `source` and `validated`. They never split a version and are kept as sorted distinct arrays inside the version payload. Changes to names, addresses, identifiers, other timestamps or other non-volatile fields produce separate versions. Identical rows combine across nonconsecutive dates. No latest-partition selection applies.

Versions are unfolded by email position, then every version reporting the same source, email and NPI is merged into one link.

| Column | Meaning |
|---|---|
| `link_id` | SHA256 of source, email and NPI. Unique. |
| `record_count`, `record_ids` | Number of merged versions and their sorted `record_id` values. A `record_id` is the SHA256 of the source table and one version's identity payload. |
| `latest_record_id` | Version with the unique greatest `last_seen_day`, or the only version. NULL when several undated versions exist or the greatest day is tied. |
| `email_origins` | Sorted source columns or array positions where the email appeared across versions. |
| `attribute_versions` | One entry per version: record ID, first/last seen day, observed day count, observation count, email origins and JSON identity payload. Name and address changes over time are visible here. |
| `observed_days`, `conflict_days` | Exact source dates of the link and the subset with same-day NPI conflicts. Empty for undated vendors. |
| `first_seen_day`, `last_seen_day`, `observed_day_count`, `observation_count` | History across all versions of the link; see [observation counts](docs/metrics/01_observation_counts.md). |

Indicators that depend on one record's own attributes are published twice. The unsuffixed column uses all versions of the link: `email_matches_source_name` and `vendor_name_matches_registry_name` are true when any usable vendor name matches, and `source_state_values` is the union of recognized states. The `_latest` columns (`email_matches_source_name_latest`, `vendor_name_matches_registry_name_latest`, `source_state_values_latest`, `vendor_state_evidence_latest`, `vendor_state_corroborated_latest`, `cookie_vendor_state_evidence_latest`) use only the latest version and are NULL without one.

**Illustrative example:** JOHN SMITH and JANE JONES appear for the same email/NPI in different deliveries. The link keeps both versions in `attribute_versions`; the all-version name indicators consider both names, and the `_latest` indicators use the most recently seen version. An unchanged JOHN SMITH row repeated on two dates is one version with two observations.

Vendor names come from the email-bearing versions. HealthLink uses its separate HCP reference by NPI, so its `_latest` columns equal the all-version columns; registry comparisons also join by NPI. These reference joins use readable name variants without historical date alignment.

Only nonempty cleaned email/NPI keys enter metric outputs. Medscape additionally excludes every NPI present in the cumulative opt-out feed before computing intermediate metrics. [Opt-out policy and validation](docs/medscape_optout.md) describe the exclusion. Missing-key records remain in staging. Malformed nonempty values remain available for indicators. Endato attributes returned person-email slots; provider-input email fields are excluded. RocketReach uses its array plus recommended/current fields; QuantumMedica unfolds pipe-separated values. DRDB merges both input tables at link grain. See the [source map](docs/00_source_map.md).

## Vendor specialty and profession metrics

[Vendor specialty overlap](docs/metrics/23_conflicting_npis_share_vendor_specialty.md) and [vendor profession overlap](docs/metrics/24_conflicting_npis_share_vendor_profession.md) compare exact normalized vendor labels between conflicting NPIs. Metadata joins use the same delivery day and NPI; Medscape also joins by registration `guid`, using each GUID's own days. HealthLink and DRDB contribute specialty fields; DRDB uses the raw `specialty` labels of all versions. Medscape and QuantumMedica read profession fields; only Medscape fills them.

## Metric implementations

[Facility overlap](docs/metrics/15_conflicting_npis_share_facility.md) compares retained facility NPIs between conflicting NPIs.

[NPPES specialty overlap](docs/metrics/16_conflicting_npis_share_specialty.md) uses exact recognized NPPES taxonomy codes across all fifteen slots, with no broad-label fallback. Vendor specialty/profession comparisons are separate metrics.

[NPI registry status](docs/metrics/17_npi_registry_status.md) adds current NPPES lifecycle evidence, preserving deactivation/reactivation dates, replacement values and uncertainty reasons. It does not rewrite links or infer activity on historical vendor dates.

[Vendor/facility state](docs/metrics/18_vendor_facility_state.md) and [cookie-location evidence](docs/metrics/19_cookie_location_evidence.md) are descriptive fields, without filtering links or assigning scores. Vendor/facility state has all-version and `_latest` forms.

[Link freshness](docs/metrics/20_link_freshness.md) separates vendor source age from link lag, using retained vendor observation dates, with no thresholds or scoring. Missing dates stay unknown.

[Link stability](docs/metrics/21_link_stability.md) publishes distinct email/link/conflict day counts, presence and overlap fractions, and an incomplete-date flag. It measures dated history without adding thresholds or scores. One-day histories and undated peers remain visible.

[NPI validity and entity type](docs/metrics/22_npi_identity.md) adds structural checks and registry entity-type consensus.

## Facility claims support and domain evidence

[Facility claims support](docs/metrics/27_facility_claims_support.md) publishes the claim count and data-source labels behind each NPI's rank-1 facility association. [Domain evidence](docs/metrics/28_domain_evidence.md) publishes per-source domain counts and state and facility concentration. Domain fields are computed downstream of stored core, because they need every link of a source. Neither metric filters links or assigns scores.

## Sequential history and registration supersession

[Sequential history](docs/metrics/25_sequential_history.md) adds source/email delivery-version counts, set changes, swaps, flip-backs and ordered daily cumulative evidence. It reads all retained eligible observations through `sequence_as_of_day`, default America/New_York today. HealthLink and QuantumMedica collapse consecutive repeated delivery content. Daily evidence never uses later NPI observations. Unknown dates stay explicit.

[Medscape registration supersession](docs/metrics/26_registration_supersession.md) is evaluated per link and registration GUID, using that GUID's own days; each link reports its most recently observed GUID. It preserves older claims, flags ambiguous latest NPIs and treats missing chronology as unknown. Other vendors receive `not_applicable`.

## Validation

Intermediate contains [eleven SQL models](models/intermediate/README.md): seven vendor pipelines, two shared name lookups, the stored core union and downstream cookie enrichment. Staging and final remain separate.

Email counts overlap across vendors and must not be summed as globally distinct emails.

## Run and test

From this directory, using the repository `.venv` and PulsePoint Trino connection:

```bash
# Build all normal views, stored core and the final table
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

Use `--source all` to apply source, test or report to every vendor separately. The `report` command reads `iceberg.jteixeira_ipa.pii_clean` filtered to the requested vendor. Reports use stored evidence and evaluation dates, so changes to raw data or model code appear only after publication. Report `metric_rows` are table rows, that is, links. Source and candidate validation continue to inspect their respective build inputs. Source commands recreate selected staging/intermediate views and shared name dependencies; they do not refresh the published final table. `build` recreates source dependencies, builds stored core, then publishes cookie-enriched `pii_clean`. `final` reads stored core.

Core builds can use a validated candidate or write directly with `core --direct`. Stage-limit fallback materializes narrow execution inputs before attaching later metrics. The local core contract contains 139 fields and requires all seven sources, unique `link_id` keys and eighteen integrity checks, including stored name-evidence consistency. `final` then computes cookies source by source from stored core, combining enriched batches into final output. It pins cookie inputs and coverage, verifies all 139 core fields including `computed_at`, and checks cookie invariants before completion. Interrupted cookie batches resume automatically after validation. Source snapshots are not pinned by ordinary core builds. Checkpoints are printed without saving local result files.

`test --source <vendor>` runs the local suites, then checks in the warehouse that staging preserves raw row counts, that versions represent every raw row with unique record IDs, and that the vendor model passes all integrity queries. Local tests cover synthetic execution and publication control flow. Local fixtures run translated SQL in DuckDB; they do not replace Trino checks. Install local test dependencies from [requirements-dev.txt](requirements-dev.txt). The runner renders Jinja; dbt itself is not the execution engine, and Spark has not been tested.

Profile SQL files are templates for reusable validation. `tools/pipeline.py` supplies published rows through `render_profile(filename, source=None)` and renders any metric macros. A specific `source` restricts the input before aggregation; omitting it profiles all vendors. Existing `report` commands use this renderer. For the general observation profile, render SQL from the project directory:

```bash
PYTHONPATH=tools ../../.venv/bin/python -c 'import pipeline; print(pipeline.render_profile("profile.sql"))'
```

The facility debug query directly unnests stored peer comparisons from `pii_clean`; it does not rebuild facility reference joins.

Report commands for the remaining metrics are:

```bash
../../.venv/bin/python tools/pipeline.py report --source all --metric conflicting_npis_share_facility
../../.venv/bin/python tools/pipeline.py report --source all --metric conflicting_npis_share_nppes_specialty
../../.venv/bin/python tools/pipeline.py report --source all --metric conflicting_npis_share_vendor_specialty
../../.venv/bin/python tools/pipeline.py report --source all --metric conflicting_npis_share_vendor_profession
../../.venv/bin/python tools/pipeline.py report --source all --metric npi_registry_status
../../.venv/bin/python tools/pipeline.py report --source all --metric vendor_state_evidence
../../.venv/bin/python tools/pipeline.py report --source all --metric cookie_location_status
../../.venv/bin/python tools/pipeline.py report --source all --metric sequential_history
../../.venv/bin/python tools/pipeline.py report --source all --metric registration_supersession
```

The [complete single-email lookup](docs/email_lookup.md) selects all 165 model fields and six helpers from the canonical table. The shorter shortcut selects a subset of the same stored data. The lookup uses stored evaluation dates and does not repeat reference joins.

## Documentation

Execution outputs and validation logs are not retained locally or in Git. Selected findings belong in Markdown, and SQL sources remain available for reruns. Reports and measurement tools display results on stdout. Notebook outputs must be cleared before saving. The nickname reference seed is a model dependency, not an exported dataset.

Email investigation: [Email lookup query and metric reference](docs/email_lookup.md). Enter one email to inspect names, states, NPIs, history, versions and quality indicators per link.

Table reference: [PII Clean data dictionary](docs/data_dictionary.md). All 180 contract columns (the November 2 snapshot stores 165), types, nested evidence structures, null handling and link counting rules.

1. [Source map](docs/00_source_map.md): input tables, name joins and date limitations.
2. [Metrics](docs/metrics/README.md): definitions, examples and source statistics.
3. [Final table](models/final/README.md): grain, refresh and inspection.

See [project instructions](INSTRUCTIONS.md) and [model details](models/README.md).

## Direct core-table builds

`core --direct` writes source batches directly into `iceberg.jteixeira_ipa.pii__int_pii__metrics`, avoiding a separate complete core candidate and copy. The core remains partial until all sources finish. `--resume` retains existing source batches after schema and key checks and assumes those sources are complete.

Medscape builds can use `tools/build_medscape_batches.py` to bound transaction sizes. Each normalized email stays entirely within one of sixteen hash buckets. Expected link keys and observation-history checksums determine whether a bucket is complete before it can be skipped. Do not use source-level resume as proof that partial email batches are complete. [Recovery details](docs/build_recovery.md).

The final table is built from actual cookie-enriched core output. No pending cookie columns are added to core. [Cookie workflow](docs/cookie_stage.md).

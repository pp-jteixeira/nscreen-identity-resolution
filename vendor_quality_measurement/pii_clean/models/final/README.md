# Final table

The [final model](pii_clean.sql) defines the 194-field output of `int_cookie__metrics`. Seven vendor models first define 139 core fields, combined with `UNION ALL` and stored in `int_pii__metrics`. The downstream model computes 10 domain fields, 14 cross-source fields and 31 actual cookie fields (three completed days) for each source independently, then combines the enriched outputs. The runner performs separate source writes using fixed input snapshots and coverage. No placeholder cookie columns or subsequent MERGE are required.

Rows have link grain: one row per source, email and NPI, keyed by the unique `link_id`. Each link merges every version of the source records that report it; `record_ids`, `latest_record_id`, `email_origins` and `attribute_versions` keep those versions and their JSON identity payloads. Observation history, nullable outcomes, reference provenance and comparison evidence remain available. Indicators that depend on one record's attributes are stored for all versions and, with a `_latest` suffix, for the latest version. Publication does not score links or deduplicate them across vendors. See the [data dictionary](../../docs/data_dictionary.md).

## Build and validation

From the project directory:

```bash
../../.venv/bin/python tools/pipeline.py build --direct
../../.venv/bin/python tools/pipeline.py final
```

`build` refreshes source dependencies, builds stored core and publishes cookie-enriched output. `core --direct` writes vendor batches directly into the core table. `core --direct --resume` retains completed source batches after schema and key checks. Default core builds can instead validate a separate candidate before replacement. Stage-limit fallback uses narrow stored execution inputs.

Core requires identical vendor schemas, all seven sources, unique `link_id` keys and eighteen integrity checks. Final enrichment preserves counts, keys and all 139 core-field checksums, including `computed_at`, and validates cookie outcomes. `final` and `cookies` read stored core without recomputing vendor metrics. The first source replaces final output and subsequent sources append. Final is partial during this operation; rerunning the command validates and resumes its checkpoint. [Cookie workflow](../../docs/cookie_stage.md).

Medscape can be built in sixteen email hash batches with link key/history checksums and a fixed full-source freshness date. Ordinary source-level resume does not establish that partial email batches are complete. [Recovery details](../../docs/build_recovery.md).

## Publication status

Published November 3, 2026 at snapshot `985110448175465479`: 26,733,354 links across seven sources, 194 fields. Every source was verified against stored core, and the table comment records completed cookie source batches.

The [complete email lookup](../../docs/email_lookup.md) reads all 194 stored fields and six display/comparison helpers. Source and reference tables remain read-only; build relations stay in `iceberg.jteixeira_ipa`.

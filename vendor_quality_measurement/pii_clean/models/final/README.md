# Final table

The [final model](pii_clean.sql) selects the 154-field output of `int_cookie__metrics`. Seven vendor models first produce 124 non-cookie fields, combined with `UNION ALL` and stored in `int_pii__metrics`. The downstream cookie model computes thirty actual fields over three completed days. No placeholder cookie columns or subsequent MERGE are required.

Rows retain exact source-record/email-position grain, keyed by `source, metric_row_id`. Historical observations, raw `record_payload`, nullable outcomes, reference provenance and comparison evidence remain available. Publication does not score or deduplicate links.

## Build and validation

From the project directory:

```bash
../../.venv/bin/python tools/pipeline.py build --direct
../../.venv/bin/python tools/pipeline.py final
```

`build` refreshes source dependencies, builds stored core and publishes cookie-enriched output. `core --direct` writes vendor batches directly into the core table. `core --direct --resume` retains completed source batches after schema and key checks. Default core builds can instead validate a separate candidate before replacement. Stage-limit fallback uses narrow stored execution inputs.

Core requires identical vendor schemas, all seven sources, unique keys and sixteen integrity checks. Final enrichment preserves counts, keys and all 124 core-field checksums, including `computed_at`, and validates cookie outcomes. `final` and `cookies` read stored core without recomputing vendor metrics. [Cookie workflow](../../docs/cookie_stage.md).

Medscape recovery uses sixteen email hash batches with raw-history checksums and a fixed full-source freshness date. Ordinary source-level resume does not establish that partial email batches are complete. [Recovery details](../../docs/build_recovery.md).

## Publication checkpoints

The October 31, 2026 publication has 154 columns and 75,656,369 records across all seven sources, at snapshot `8811920360682490090`. It preserves all 124 core fields and passes cookie integrity checks. The three-day cookie window is October 28–30; October 30 is missing in both source feeds and remains explicitly flagged.

The earlier direct rebuild stopped with six sources after HDFS allocation failures. Recovery preserved those 28,492,003 core records and built 47,164,366 eligible Medscape records in sixteen email batches. Bounded writers and a reusable exact-record input resolved the build. See [execution evidence](../../docs/build_recovery.md).

The [complete email lookup](../../docs/email_lookup.md) reads all 154 stored fields and six display/comparison helpers. Source and reference tables remain read-only; build relations stay in `iceberg.jteixeira_ipa`.

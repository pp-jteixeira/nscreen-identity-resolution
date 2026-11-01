# Final table

**Published and verified, October 31, 2026:** final snapshot `4233051104478921549` contains 75,656,369 records across seven sources and 158 fields. Source-scoped cookie enrichment preserved all 128 fields from core snapshot `3003274000539755025`, including stored name explanations. Both cookie inputs cover October 28–30 with all three days present. See [stored name evidence](../../docs/name_match_evidence.md) for recovery and validation details.

The [final model](pii_clean.sql) defines the 158-field output of `int_cookie__metrics`. Seven vendor models first define 128 non-cookie fields, combined with `UNION ALL` and stored in `int_pii__metrics`. The downstream cookie model computes thirty actual fields over three completed days for each source independently, then combines the enriched outputs. The runner performs separate source writes using fixed input snapshots and coverage. No placeholder cookie columns or subsequent MERGE are required. The name-evidence upgrade adds four fields to the earlier 154-field publication. [Implementation and rollout status](../../docs/name_match_evidence.md).

Rows retain exact source-record/email-position grain, keyed by `source, metric_row_id`. Historical observations, raw `record_payload`, nullable outcomes, reference provenance and comparison evidence remain available. Publication does not score or deduplicate links.

## Build and validation

From the project directory:

```bash
../../.venv/bin/python tools/pipeline.py build --direct
../../.venv/bin/python tools/pipeline.py final
```

`build` refreshes source dependencies, builds stored core and publishes cookie-enriched output. `core --direct` writes vendor batches directly into the core table. `core --direct --resume` retains completed source batches after schema and key checks. Default core builds can instead validate a separate candidate before replacement. Stage-limit fallback uses narrow stored execution inputs.

Core requires identical vendor schemas, all seven sources, unique keys and seventeen integrity checks. Final enrichment preserves counts, keys and all 128 core-field checksums, including `computed_at`, and validates cookie outcomes. `final` and `cookies` read stored core without recomputing vendor metrics. The first source replaces final output and subsequent sources append. Final is partial during this operation; rerunning the command validates and resumes its checkpoint. [Cookie workflow](../../docs/cookie_stage.md).

Medscape recovery uses sixteen email hash batches with raw-history checksums and a fixed full-source freshness date. Ordinary source-level resume does not establish that partial email batches are complete. [Recovery details](../../docs/build_recovery.md).

## Publication checkpoints

The original October 31, 2026 cookie publication had 154 columns and 75,656,369 records across all seven sources, at snapshot `8811920360682490090`. It preserves all 124 core fields and passes cookie integrity checks. The three-day cookie window is October 28–30; October 30 was missing in both inputs at evaluation and remains explicitly flagged in those stored values.

The earlier direct rebuild stopped with six sources after HDFS allocation failures. Recovery preserved those 28,492,003 core records and built 47,164,366 eligible Medscape records in sixteen email batches. Bounded writers and a reusable exact-record input resolved the build. See [execution evidence](../../docs/build_recovery.md).

The [complete email lookup](../../docs/email_lookup.md) reads all 158 stored fields and six display/comparison helpers. Source and reference tables remain read-only; build relations stay in `iceberg.jteixeira_ipa`.

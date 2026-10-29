# Final table

The local [final model](pii_clean.sql) unions all rows and columns from the seven vendor metric models using `SELECT *` with `UNION ALL`. It does not deduplicate, filter, score or recompute metrics.

As last verified on October 29, 2026, the published Iceberg table `iceberg.jteixeira_ipa.pii_clean` has 41 columns and 75,564,265 rows. Local models declare 103 columns; the five additional metric groups remain unpublished. The [complete email lookup](../../docs/email_lookup.md) computes those groups read-only and returns 109 columns, including six display/comparison fields.

The key remains `source`, `metric_row_id`: one exact source record and email position. Repeated email–NPI links, changed records, duplicate email positions and historical observations remain separate. Upstream combines only otherwise-identical raw records that differ by delivery day.

A publication retains every attribute and metric from the vendor views used for that build. The existing published table retains the earlier 41-column schema. `record_payload` preserves every original field of the email-bearing source record except `day`, represented through `observed_days` and observation counts. Vendor-specific raw attributes remain in that JSON payload; normalized names, states, provenance and comparison details are separate typed columns.

From the project directory:

```bash
# Refresh all dependencies and publish the final table
../../.venv/bin/python tools/pipeline.py build
# Publish from the current vendor views
../../.venv/bin/python tools/pipeline.py final
```

Publication uses atomic `CREATE OR REPLACE TABLE ... AS`. The runner requires identical vendor column names, order and types, validates the execution plan, and checks per-vendor row counts, unique record keys and checksums of every substantive column. `computed_at` is excluded from checksums because source views calculate it at query time. The final schema must match the vendor schema. Validation and executed SQL from the last 41-column publication are recorded in final_build.json (local-only: `../../results/final_build.json`); they are not evidence of publication of the 103-column local schema.

When the combined vendor query exceeds Trino’s stage limit, the local runner builds a uniquely named candidate table in separate vendor batches. It validates that candidate before atomically replacing the final table, then rechecks the published schema and checksums. The candidate remains available for audit. This path has local failure-case tests but has not yet executed in the warehouse. Facility relatedness, specialty relatedness, NPI lifecycle, vendor/facility state comparison and cookie-location evidence remain unpublished. A full local build includes all five additions. The last two passed native fixtures, all vendor plans and full-population read-only measurement on October 29, 2026. These checks do not constitute publication or a full raw-source rebuild.

The destination is Joel’s `jteixeira_ipa` schema. Source/reference tables remain read-only. Source snapshots are not pinned; concurrent upstream changes can fail validation.

[Metric definitions](../../docs/metrics/README.md) · [Name inspection](../../sql/conflicting_names_debug.sql) · [State inspection](../../sql/conflicting_states_debug.sql)

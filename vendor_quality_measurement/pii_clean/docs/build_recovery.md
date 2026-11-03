# Build recovery

This page describes how to build and recover stored core and the final table when a complete build is too large for one write. A storage write error such as `HIVE_WRITER_CLOSE_ERROR` while copying a validated candidate into core can be retried from that candidate. A cookie checkpoint comment on the final table that belongs to a different core snapshot must be replaced before `final` runs.

## Bounded Medscape builds

Medscape is the largest source. Large Medscape writes can fail with HDFS replica-allocation errors. The recovery path bounds both writer concurrency and transaction size while preserving each email's full observation history. It writes directly into the stored core, `iceberg.jteixeira_ipa.pii__int_pii__metrics`, which must already exist with the vendor link contract.

## Email batches

`tools/build_medscape_batches.py` partitions normalized email addresses using the first hexadecimal character of SHA-256, producing sixteen disjoint batches. Filtering occurs before version grouping. All NPIs, registration GUIDs, versions and observation dates for an email remain together. Sequential swaps, flip-backs, opt-out effects and registration supersession therefore retain their full context.

Source-relative freshness needs one extra safeguard: every batch uses the latest eligible observation day from the entire Medscape source. A batch containing older emails cannot redefine the source's latest day. All evaluation dates are fixed for the run.

The runner pins Medscape global, metadata and opt-out Iceberg snapshots. From eligible raw records it computes the expected population per batch at link grain: link count, duplicate `link_id` keys and a checksum over `link_id`, `record_ids`, `email`, `npi`, `observed_days`, first/last seen day, observed day count and the observation counts. It reports these counts as `links`. An existing batch is retained only when it matches that complete expected population. Each INSERT is atomic. Following a write error, committed rows are inspected before retrying, preventing duplicate insertion after an uncertain client result. Mismatched or incomplete existing batches stop the runner. A table-comment marker blocks ordinary core resume and final publication while email batches are incomplete. It is cleared only after complete expected coverage is verified.

Shared external reference tables are read through the normal metric definitions. They are not all snapshot-pinned by this recovery tool. If they change between batches, reference evidence may differ by build time. Stored evaluation dates and provenance remain available.

## Commands

The core table must match the current 139-field schema. From `vendor_quality_measurement/pii_clean`:

```bash
../../.venv/bin/python tools/build_medscape_batches.py --materialize-records
```

`--day YYYY-MM-DD` fixes the evaluation day; the default is today in America/New_York. Repeat the command to resume after inspecting a failure. `--batches 0123` limits execution to selected hash buckets. The runner always checks expected source history before retaining committed buckets. It prints checkpoints and validation results without saving local result files.

After all sixteen Medscape buckets and the six other sources are complete, validate the stored core and publish final cookie enrichment:

```bash
../../.venv/bin/python tools/pipeline.py core --direct --resume
../../.venv/bin/python tools/pipeline.py final
```

The first command retains complete source batches and runs core integrity checks. Run the email-batch tool before this command whenever Medscape is partial. Ordinary source-level resume cannot prove that partial Medscape batches are complete.

Writer settings are eight writer tasks, one writer per task, local writer scaling disabled, and a 64 MB target data-file size. The file-size setting is a target rather than a strict upper bound. Upstream computation remains distributed. These settings reduce write pressure but cannot repair unhealthy HDFS storage.

## Core and final separation

Core holds only non-cookie fields. A failed cookie build leaves core available for retry. Final cookie enrichment uses the default three completed days and produces actual 180-field rows. Cookie values are never copied into core. See [cookie workflow](cookie_stage.md).

## Reusable version input

The raw Medscape global feed is large, and a full metric batch otherwise scans it several times. A stored version input groups those observations once, applies cumulative NPI opt-outs and retains version fields, payloads, volatile-field arrays and exact observation-day arrays. It holds versions, not links, and is an execution input, not a second copy of final enriched metrics.

Use `--materialize-records` to create this execution input during a new run, or pass an existing owned-schema table with `--versioned-input`. Before using it, the batch runner collapses the stored versions to links with the same `link_records` macro and compares every expected key/history checksum with freshly grouped pinned raw inputs. `--materialize-records` also stores grouped professional metadata once; `--metadata-input` reuses an existing table, after comparing its checksum with the pinned metadata. The normal metric model remains available without these optional inputs.

Preservation checks must use ordinary read-session aggregation planning. Forcing `distinct_aggregations_strategy=single_step` on a wide per-source checksum removes distributed partial aggregation and concentrates the check by source. Writer bounds remain query-scoped to writes. The regular `pipeline.py` validation helper uses ordinary read sessions.

## Final publication checks

`final` pins stored core and the cookie inputs, then writes each source separately. Each source must pass 139-field preservation, complete counts, unique `link_id` keys and cookie integrity before the next source starts. Full-population preservation and cookie integrity precede completion marking. Ordinary refresh or interrupted-source recovery uses `tools/pipeline.py cookies`; incomplete checkpoints retain original snapshot pins, window and coverage.

Email counts overlap between sources and must not be summed as globally distinct emails. Registration-grain counts include GUID and are a different unit from links.

The [sequential history statistics](../sql/statistics/25_sequential_history.sql) and [registration supersession statistics](../sql/statistics/26_registration_supersession.sql) read the final table and can be run after publication.

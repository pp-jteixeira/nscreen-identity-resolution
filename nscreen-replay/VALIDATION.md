# Replay validation evidence

Primary validation date: 2026-09-20. Production processing day selected:
2026-09-18.

On 2026-09-25, configurable input profiles were added for experimental source
tables. Offline checks passed for profile loading, immutable input mappings,
DATE-to-VARCHAR input normalization, all eight SQL-stage translations, resume
behavior, and write guards. The bundled `2026-09-16` vendor-activity profile
completed through `remainder` and `geo_counts`. Full replay remains incomplete;
that live run is tracked separately below.

The upload transport was subsequently redesigned. Numeric clustering results
are binary-packed, UIDs are delimiter-packed, requests are distributed across
deterministic Iceberg shards, and independent shards upload concurrently. Local
query construction enforces a 950,000-character ceiling beneath Trino's observed
one-million-character maximum.

Local Parquet clustering was added as an alternative to warehouse uploads.
Each geography is written as atomic, Zstandard-compressed Parquet parts with
per-part hashes and nullable 64-bit identifier columns. DuckDB now performs the
global UID-hash join and final filtering locally after clustering. Offline
validation round-tripped UIDs, negative hashes, nullable identifiers,
cross-geography hash multiplicity, stable prefixes, and final exclusion filters.
Thirty-nine offline tests pass; seven optional Java, Trino, and write tests
remain skipped unless their environment flags are set. All 1,299 geographies
completed local Java clustering and Parquet publication. Local DuckDB downstream
execution remains incomplete.

Local remainder persistence now streams the unchanged Trino SELECT into a
disk-backed DuckDB table and atomically publishes geography-partitioned Parquet.
Offline tests cover multi-batch streaming, partition metadata, edge round trips,
and bypassing the remainder CTAS. Full-scale transfer speed, disk consumption,
and end-to-end completion remain unmeasured.

## Implemented boundary

The replay starts from prepared LiveRamp, Throtle, Experian, daily collocation,
and geographic inputs. It executes source-derived relational stages on Trino
and the unchanged Forge Java calculator locally. Raw ingestion and preparation
are not part of this validation.

## Completed checks

- Offline tests cover all eight SQL-stage translations, write-target restrictions,
  partition-label overrides, REAL-to-DOUBLE aggregation, changed-source rejection,
  checkpoint reuse, and recovery after an upload acknowledgement is lost.
- Read-only Trino fixtures cover provider alignment, propagation, remainder
  extraction, duplicate/null multiset differences, final filters, structural
  membership differences, and the global UID-hash join.
- A Java fixture executes the original calculator without Spark.
- A complete Trino/Java sandbox replay passed on synthetic data. Run ID:
  `smoke_d0b9ef4a1832`. It produced 29 final rows. All six deterministic stages
  had zero extra and zero missing rows. Final strict comparison had two extra
  and two missing rows from generated cluster labels; structural comparison
  had zero differences.

The sandbox run's detailed artifacts are in
`runs/smoke_d0b9ef4a1832/manifest.json` and `report.md`. Its remote objects begin
with `iceberg.jteixeira_ipa.nscreen2_smoke_d0b9ef4a1832_`.

## Vendor-activity checkpoint: 2026-09-29

Run ID: `activity_sample_20260916_v1`. Vendor inputs use the persisted 0.5%
line samples; collocation and geography inputs retain full production tables.
The remainder contains 806,112,246 edges across 1,299 geographies.

Geography `770`, the largest group, contains 8,143,973 edges. The unchanged
Forge calculator produced 5,390,604 UID assignments locally with a 10 GB heap;
observed resident memory stayed near 3 GB. The complete local clustering run
published 510,903,924 mapping rows across all 1,299 geographies. Its compressed
Parquet output occupies 27,519,904,793 bytes.

Local exports contain 14,280,026 `initial` rows, 3,334,890 `stage1` rows, and
3,403,960 `stage2` rows. The first downstream DuckDB attempt exhausted its 8 GB
limit while using DuckDB's ten-thread default. The runner now defaults to two
DuckDB workers and provides a local-only resume command. A two-worker resume is
actively producing Louvain Parquet output; final completion remains unverified.

The legacy 5,000-row serial uploader was stopped after demonstrating excessive
Iceberg commit overhead and intermittent manifest-list failures. Completed
legacy rows remain untouched. Live packed-shard validation decoded an exact
Java-output row, confirmed 10,000 distinct UIDs in its first batch, and persisted
at least 1.2 million mappings without an upload failure. Full-run completion and
sustained throughput across smaller geographies remain unestablished.

Run ID `activity_sample_20260916_0p1_v1` uses the nested 0.1% vendor sample with
full production collocation and geography inputs. Its remainder contains
822,896,617 edges across 1,299 geographies. Geography `770` contains 8,300,961
edges and produced 5,460,544 Java mappings with a 10 GB heap.

The run was interrupted during packed upload after 464 completed batches; eight
batches remained pending in the local checkpoint. Earlier remainder attempts
failed once with `PAGE_TRANSPORT_TIMEOUT` and once with `HIVE_WRITER_DATA_ERROR`;
attempt three completed. Existing warehouse rows remain untouched. Local
Parquet mode reused the completed Java TSV after a reviewed engine migration
for geography `770`. Its 5,460,544 mappings became 22 Parquet parts totaling
307,115,634 bytes in approximately six seconds.
The prior Java TSV was approximately 661 MiB. A full Parquet scan confirmed all
5,460,544 rows, one geography, and zero null UID hashes. The validated Parquet
dataset replaced both the raw Java TSV and the 1.1 GiB exported-edge TSV; the
mapping remains recoverable from Parquet, and edges remain recoverable from the
persisted remainder table.

Run ID `activity_sample_20260916_v1_1pct` uses the persisted 1% vendor sample.
Provider alignment and propagation completed through `stage2`. Six remainder
CTAS attempts failed with `HIVE_WRITER_DATA_ERROR` while HDFS rejected new
Parquet blocks with zero available replication targets. No geography clustering
or local downstream processing had begun at this checkpoint. Completed upstream
artifacts remain available for deterministic resume. Local remainder mode avoids
another HDFS write while retaining Trino execution for the remainder SELECT.

## Production checkpoint: 2026-09-20 13:10 UTC

Run ID: `baseline_20260918`. The latest authoritative state is in
`runs/baseline_20260918/manifest.json`. Fixture results do not establish
production parity.

The production alignment mapping completed: 95,733,260 rows persisted in
`iceberg.jteixeira_ipa.nscreen2_baseline_20260918_lrth_mapping_a1`.
Its Trino query ID was `20260920_115307_32101_h9wg2`.

The aligned vendor output later completed on attempt three. It contains
6,055,694,705 rows in
`iceberg.jteixeira_ipa.nscreen2_baseline_20260918_lrth_a3`. The initial-stage
mapping also completed with 75,636,845 rows. HDFS failures prevented the initial
stage from becoming a table, so attempt four published it as a view.

The following `connected_ns` table attempt failed with
`HIVE_WRITER_DATA_ERROR`: HDFS could not allocate a replica for an output block.
Its query ID was `20260920_131014_34419_h9wg2`. No production table was modified,
and no failed replay artifact was dropped.

At this checkpoint, full production-day equality is **not established**. The
finalizer is blocked because `connected_ns` and all later stages are incomplete.
Its state is recorded in `runs/baseline_20260918/finalizer.json`.

Subsequent completion and parity must be taken from the baseline run's
comparison report, not the synthetic fixture checks above.

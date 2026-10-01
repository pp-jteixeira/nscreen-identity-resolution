# NScreen prepared-source replay

Runs the graph from prepared production inputs using a local Python controller,
server-side Trino SQL, and the original Java clustering calculator. Spark is not
required. All remote writes are restricted to `iceberg.jteixeira_ipa.nscreen2_*`.

## Replay boundary

Inputs are the selected day's `iceberg.crossscreen.liveramp_source`,
`throtle_source`, `experian_source`, `nscreen_ipcollocation_daily_clean`, and
`nscreen_geo_daily_ua`. Input and comparison table snapshots are recorded before
execution. Historical raw ingestion, provider preparation, user-agent parsing,
and hourly evidence are outside this replay's scope.

Stages are `lrth`, `initial`, `connected_ns`, `stage1`, `stage2`, `remainder`,
`louvain`, and `result`. SQL is read directly from the Forge checkout. SQLGlot
translates it, with explicit adapters for Spark array expansion, Boolean MAX,
REAL aggregation, partition-column overrides, and the Java aggregate boundary.
Production `persist_cte` mappings become materialized Trino tables. No provider
deduplication, repaired stage labels, or proposed identity improvements are added.

The Java bridge compiles the original `Screen7IdCalculatorDHMH`, its graph
classes, and `MurmurHash`, with Forge's fastutil 8.1.1. It calls the calculator
once per complete geography. Original UID hashes are retained. Both output modes
retain the final global hash join, including hash-collision multiplicity across
geographies. Trino executes that join in warehouse mode; DuckDB executes it in
local mode.

## Setup and commands

Use the repository-root Python environment. Install the root requirements.
Jinja2 and SQLGlot 27.29.0 translate Forge SQL; DuckDB executes disk-backed local
downstream stages. Existing Spark packages are unchanged. A JDK 17 or newer is
required for local clustering.
`JAVA_HOME` takes precedence; Homebrew JDK 17 and 21 are detected automatically.

Trino credentials and `dbfuncs.py` are loaded from `~/.pulsepoint` using an
absolute path, with interactive password prompts disabled. `PULSEPOINT_HOME`
and `PULSEPOINT_DBFUNCS` can override these locations. Credentials are never
copied into this folder.

From the repository root:

```bash
uv pip install --python .venv/bin/python -r requirements.txt
cd nscreen-replay
../.venv/bin/python -m replay doctor
../.venv/bin/python -m replay build-java
../.venv/bin/python -m replay render --day 2026-09-18
../.venv/bin/python -m replay run --run-id baseline_20260918 --day 2026-09-18
../.venv/bin/python -m replay compare --run-id baseline_20260918
../.venv/bin/python -m replay status --run-id baseline_20260918
```

Run against the persisted `2026-09-16` vendor-activity sample while retaining
production collocation and geography inputs:

```bash
cd nscreen-replay
../.venv/bin/python -m replay run \
  --run-id activity_sample_20260916_v1 \
  --profile profiles/vendor_activity_coverage_20260916.json
```

Sampled provider replays should stop after `stage2`. Full production
collocation makes sampled remainder, clustering, Louvain, and final outputs
misleadingly large. Keep sampled replay outputs in Trino:

```bash
cd nscreen-replay
NSCREEN_TRINO_SESSION='{"max_writer_task_count":"8","task_max_writer_count":"1"}' \
  ../.venv/bin/python -m replay run \
  --run-id activity_sample_20260916_v1_5pct \
  --profile profiles/vendor_activity_coverage_20260916_5pct.json \
  --until stage2
```

Profiles fix the processing day and map logical prepared inputs to qualified
Iceberg tables. The exact mappings and snapshots are stored in `manifest.json`.
Use repeated `--input logical_name=catalog.schema.table` arguments for ad-hoc
overrides. A run ID cannot resume with changed mappings. Start a new run ID
instead. Production prepared tables remain the default when no profile or input
override is supplied.

Input schemas are inspected before execution. Experimental inputs may store
`day` as `DATE`, while Forge prepared sources store it as `VARCHAR`. Snapshot
checks use a type-matched literal, and replay references normalize input `DATE`
values to Forge's `VARCHAR` contract before compiling stage SQL.

The bundled profile samples each vendor independently. Its merge rates therefore
describe sample behavior, not production connectivity. Production collocation
and geography tables still run at full-day scope unless they are overridden too.
Expect server-side warehouse work even though orchestration and clustering are
launched locally.

For an already-running replay, queue its comparison without keeping a terminal
open:

```bash
../.venv/bin/python -m replay.finalize --run-id baseline_20260918 --background
```

The detached finalizer waits for the computation lock, then compares all stages
only if computation completed. It does not retry failed computation or claim
parity from a partial run. Follow `runs/<run-id>/finalizer.json`,
`finalizer.log`, and `report.md`. A `complete` finalizer means comparisons ran;
their individual `exact` and `equivalent` flags determine parity.

`--forge /absolute/path/to/forge` precedes the subcommand. Omitting `--day` on a
new run selects the latest production final-output day. The chosen day is fixed
in that run's manifest. A new source-code revision needs a new run ID.

Use `run --until stage2` to stop at a stage boundary. Repeating `run` resumes
completed stages, committed upload batches, and published local geography
datasets. `compare --stages lrth initial` checks selected completed stages;
`--skip-structural` suppresses the additional final membership comparison, not
the strict row comparison.

Use `--largest-first` when testing whether local memory can handle the largest
complete geography. Processing order does not change clustering semantics.
Upload write errors are reconciled immediately against committed `(geo,batch_id)`
rows. Confirmed commits continue without requiring a process restart.

### Local Parquet clustering

Use local Parquet output to avoid writing hundreds of millions of Java mapping
rows back into Trino:

```bash
../.venv/bin/python -m replay run \
  --run-id activity_sample_20260916_0p1_v1 \
  --profile profiles/vendor_activity_coverage_20260916_0p1pct.json \
  --remainder-output parquet \
  --cluster-output parquet \
  --java-heap 10g \
  --max-geo-edges 9000000 \
  --largest-first
```

`--cluster-output parquet` implies `--remainder-output parquet` and
`--until local-result`. Trino evaluates the unchanged Forge remainder SELECT,
but its result streams into a local DuckDB staging file instead of an Iceberg
CTAS. DuckDB publishes a Zstandard-compressed Parquet dataset partitioned by a
stable geography hash under `runs/<run-id>/local/remainder/`. No remainder rows
are written to HDFS.

Each clustered geography is
stored as a resumable Zstandard-compressed Parquet dataset under
`runs/<run-id>/clustering/parquet/<geo-hash>/`. Files contain `geo`, `uid`,
`uidhash`, `deviceid`, `matchid`, and `householdid`. Nullable identifier values
remain nullable 64-bit integers. `_manifest.json` records aggregate row counts,
compressed bytes, schema, and a `*/part-*.parquet` discovery glob.

Conversion uses 250,000-row parts and atomic directory publication. A completed
dataset records per-part sizes and SHA-256 hashes. Resume validates published
parts, reuses completed geographies, and restarts only an interrupted temporary
conversion. Raw Java TSV files are deleted after successful Parquet publication.

After Java clustering, DuckDB performs the global UID-hash join from the Forge
`louvain` stage and applies the Forge final-result filters locally. It uses an
on-disk temporary directory, an 8 GB memory limit, and two worker threads. The
lower worker count reduces parallel hash-table memory pressure. Override these
controls with `--local-sql-memory` and `--local-sql-threads`. The global join
preserves hash-collision and cross-geography multiplicity. Final output is
written under `runs/<run-id>/local/result/`.

After clustering and stage exports complete, `resume-local` runs only DuckDB
against existing files. It neither reads nor writes Trino:

```bash
../.venv/bin/python -m replay resume-local \
  --run-id RUN_ID \
  --local-sql-threads 2
```

The runner exports completed `initial`, `stage1`, and `stage2` rows through
read-only Trino queries into local Parquet. It writes local Louvain rows under
`local/louvain/` and records downstream datasets in `local/_manifest.json`.
With local remainder output, no Trino table, view, or insert is created for
`remainder`, clustering, Louvain, or final output. Use
`--until local-clusters` to stop after Java mapping publication instead.

Completed local remainder publication is resumable. Interrupted streaming is
not: Trino result order has no stable checkpoint key, so the next invocation
deletes internal `remainder.partial` data and streams the remainder again.
Published local Parquet remains intact. Existing failed Iceberg attempts are
never dropped or modified.

Local final output remains a replay artifact, not proof of production parity.
Comparison against production still requires a separate multiset and structural
comparison workflow.

Runs created before this mode require `--accept-engine-change` once. Existing
Java TSV output is validated, converted, and then removed. Previously committed
upload rows remain untouched, but Parquet mode issues no additional uploads.

Trino output mode uses compact, sharded uploads. Each request delimiter-packs
UIDs and binary-packs the four BIGINT values, then Trino reconstructs ordinary
rows with `split`, `from_base64`, and `from_big_endian_64`. The default is
10,000 mappings per request, 32 independent Iceberg shard tables, and eight
concurrent requests. A union view presents those shards as the single relation
expected by the Forge Louvain SQL. Query text is rejected locally above 950,000
characters, below Trino's configured one-million-character limit.

`--batch-rows`, `--upload-shards`, and `--upload-workers` tune this transport.
Workers cannot exceed shards. Batch size and shard count are fixed once a
geography starts its packed upload; resume uses the recorded configuration.
Pending requests are checked for active Trino queries and committed row counts
before retry. Legacy row-by-row upload checkpoints remain retained but are not
mixed into the packed shard view.

Session-scoped writer limits can reduce write concurrency without changing query
logic: set `NSCREEN_TRINO_SESSION='{"max_writer_task_count":"8","task_max_writer_count":"1"}'`.
Only writer concurrency settings are accepted; overrides are recorded for each
invocation. They cannot repair unavailable HDFS storage. After a reviewed
runner-only fix, `--accept-engine-change` records the migration and retains
completed checkpoints. Use this only when completed results remain valid; source
SQL and Java changes always require a new run ID.

### Initial-stage view fallback

If HDFS cannot write the large `initial` output, publish that stage as an
ordinary view while retaining the completed `lrth` and `initial_mapping` tables:

```bash
NSCREEN_TRINO_SESSION='{"max_writer_task_count":"8","task_max_writer_count":"1"}' \
  ../.venv/bin/python -m replay run --run-id baseline_20260918 --initial-as-view
```

Use `--accept-engine-change` once when migrating a run created with an older
controller, after reviewing the change. The view choice is recorded in
`manifest.json` and remembered on resume. Failed attempts remain untouched;
the view receives the next attempt suffix. Already completed table checkpoints
cannot be converted in place.

The SELECT SQL, day, source snapshots, mappings, and duplicates are unchanged.
Only publication changes from CREATE TABLE AS to CREATE VIEW. A completed view
means its definition exists; it does not mean its full result was computed or
compared. Downstream queries recompute the view and can become slower. Use
`--until initial` to publish the view without starting downstream processing.

This fallback applies only to `initial`, not automatically to other stages.
Trino output mode still requires working storage for later tables, clustering
uploads, comparisons, and final output. Local Parquet mode can stream remainder
results directly into local storage. Views are not a substitute for fixing HDFS
or proving production parity.

## Outputs and recovery

Each run creates separately named tables such as
`iceberg.jteixeira_ipa.nscreen2_baseline_20260918_lrth_a1` and
`nscreen2_baseline_20260918_result_a1`. There is no overwrite or DROP operation.
The manifest lists all table/view names, source snapshots, query IDs, source
hashes, completion states, and failures. `runs/<run-id>/sql/` contains executed
SQL. `report.md` states which comparisons actually completed.

CTAS publishes stage tables atomically. A failed attempt receives a new suffix
on retry and its previous table, if any, is retained. An active previous query
blocks a duplicate retry. Packed uploads use recorded `(geo,batch_id)` values
and deterministic shard assignment to reconcile a response lost after commit.
Unexpected partial/duplicate uploads fail rather than delete data. One local
process may own a run at a time. Artifacts record `kind` as `table` or `view`;
older manifests may omit it.

Local run artifacts contain identifiers and are ignored by Git. Trino mode keeps
Java TSV outputs so random assignments are not regenerated during resume. Local
Parquet mode replaces those TSV outputs with compressed datasets. Exported edge
files are removed after that geography completes; they can be re-exported from
the local partitioned remainder dataset. Local remainder, stage exports,
Louvain output, and final output use atomic directory publication. No remote
cleanup is automatic.

## Capacity and parity

The observed 2026-09-18 final output has 8,655,444,460 rows (approximately
223 GB of compressed files). Trino mode performs the large joins and persists
their results without moving them through the laptop. Local mode exports
remainder edges, completed staged rows, clustering assignments, Louvain rows,
and final results. Runtime, local disk use, network transfer, and warehouse read
cost can be substantial; no full-day speed guarantee is implied.

Default Java heap is 6 GB. The default guard rejects a geography above two
million edges before exporting any groups. This is a conservative operational
limit, not a guaranteed memory bound. `--java-heap` and `--max-geo-edges` can be
raised for a machine with sufficient memory. Splitting a geography would change
production clustering semantics and is not an automatic fallback. Null or
nonfinite clustering inputs currently fail explicitly. Packed uploads default
to 10,000 rows, 32 shard tables, and eight workers. Every generated request is
measured before submission and must remain below the local query-length guard.

Strict validation compares full-row multisets, preserving duplicates and nulls.
Positive `delta` means replay-only rows; negative means production-only rows.
Structural validation replaces matchids and householdids with their full sorted
UID membership arrays and compares resulting row multisets, including reasons.
Empty and null household identifiers remain distinct. Hash checksums alone are
never treated as proof of equality.

Production uses random community IDs and randomized graph traversal. Memberships
can differ too. Floating-point aggregation and tied SQL orderings can also
produce cross-engine differences. The replay preserves production behavior and
reports these differences; it does not silently repair SQL or normalize strict
results to make them pass. Current snapshots pin retained partitions, but do not
prove which snapshots historical production jobs read. Earlier source mutations
or an expired snapshot can prevent reproducible production parity.

## Tests

```bash
# From nscreen-replay/
../.venv/bin/python -m pytest tests -q
NSCREEN_JAVA_TEST=1 ../.venv/bin/python -m pytest tests -q
NSCREEN_LIVE_TEST=1 ../.venv/bin/python -m pytest tests -q
# Optional full integration: creates tiny, isolated nscreen2_smoke_* tables.
NSCREEN_WRITE_TEST=1 ../.venv/bin/python -m pytest tests/test_pipeline_live.py -q -s
```

Live tests execute read-only VALUES fixtures on Trino. They compare translated
SQL against the repository's existing verified provider-alignment fixture.
Java tests execute the original calculator on a small graph. Neither substitutes
for the separate, full production-day comparison report.

The full sandbox integration test executes every stage, the original Java
calculator, the upload path, and both comparison modes. It expects 29 final
fixture rows, exact deterministic stages, and equal final memberships despite
random clustering labels. Its tables are retained for inspection; automatic
cleanup is intentionally absent.

# NScreen matchid flow dashboard

Streamlit dashboard showing daily exact matchid counts across vendor sources, vendor alignment, identity collocation (IC), Louvain leftovers (LU), and final NScreen output.

Interactive requests read small materialized partitions. Heavy exact aggregations run only through a separate command-line materializer.

## Materialized tables

Both tables live inside `iceberg.jteixeira_ipa`:

- `nscreen_matchid_metrics_daily` stores exact metric rows and partitions by `day`.
- `nscreen_matchid_metrics_daily_status` stores refresh state, input coverage, failures, and timestamps.

The materializer creates both tables automatically. Production NScreen tables remain read-only. Production orchestration remains unchanged.

## Materialize data

Corporate network access and `~/.pulsepoint` configuration are required.

Backfill the latest 30 final-output days:

```bash
cd nscreen-graph-exploration/docs/matchid_flow_app
python materialize.py backfill --days 30
```

Refresh one day:

```bash
python materialize.py refresh --day 2026-09-19
```

Replace an already committed day:

```bash
python materialize.py refresh --day 2026-09-19 --force
```

Backfills run oldest-first. Completed days are skipped. Five-second pauses separate processed days. Every aggregation runs sequentially.

Each complete day runs twenty-one sequential aggregation queries:

1. LiveRamp source.
2. Throtle source.
3. Experian source.
4. Vendor alignment.
5. IC stage one.
6. IC stage two.
7. Stage-and-reason breakdown.
8. Final total-and-reason breakdown.
9. LiveRamp source matchid representation in initial output.
10. Throtle source matchid representation in initial output.
11. Experian source matchid representation in initial output.
12. Clean IP-collocation graph size.
13. Unassigned same-geo remainder graph size.
14. Stage assignment publication in final output.
15. LiveRamp distinct UIDs.
16. Throtle distinct UIDs.
17. Experian distinct UIDs.
18. Initial distinct UIDs.
19. Stage/reason distinct UIDs.
20. Final total/reason distinct UIDs.
21. UID membership across the three vendors and filtered initial reasons.

The Matchids and UIDs tabs share the materialized snapshot; switching tabs never
queries the warehouse. Tables below the chart are omitted. UID queries use exact
`COUNT(DISTINCT uid)`, not row counts, and the same publication filters as matchid
queries. Metric types `uid_source`, `uid_flow`, `uid_stage_reason`, and
`uid_final_reason` store the UID count in the legacy `matchids` numeric column;
`rows` remains an exact row count. No schema migration or table reset is needed.
Previously committed dates require `refresh --day YYYY-MM-DD --force` to populate
UID metrics. Until then, the UID tab shows a missing-metrics message.

UID flows add Initial, IC1, IC2, and LU assignments at Final. Seed dependencies
remain dashed. `uid_membership` groups by UID after unioning the three source
partitions and filtered initial partition. Its dimension_1 is the initial reason
or `unrepresented`; dimension_2 is a vendor bitmask (LR=1, TH=2, EX=4).
The legacy `matchids` field holds the exact UID count for this membership atom.
Grouping once per UID makes outgoing source bands disjoint and exhaustive.
The dashboard aggregates atoms into one band per vendor/reason pair. Counts are
exact and outgoing source bands stack. Destination overlaps are schematic:
they do not depict the exact intersection geometry of the underlying UID sets.
The renderer also supports a detailed mode where different membership atoms
stack and vendor bands for the same atom overlap exactly.
Membership is measured regardless of the vendor letters in a
reason. Mask 0 represents initial UIDs absent from all three source partitions.
In detailed mode, adjacent membership ribbons sharing a source and destination are rendered as
one band when their intervals touch at both ends. Counts and hover totals are
summed. Separate ribbons remain where merging would cover a different vendor's
UID slot; underlying membership measurements are unchanged.
UIDs with multiple initial reasons receive `multiple_reasons` and appear once in
a separate "Multiple initial reasons" branch. A warning explains that other reason
branches now count only single-reason UIDs, using membership atoms rather than
overlapping stage/reason aggregates. No reason is chosen arbitrarily.

Measured UID atoms share one scale with a 15px minimum. Reason nodes and their
outgoing bands include the sum of those minimum-height slots. Thus small atoms
can enlarge parent bands beyond strictly proportional height, without changing
count labels. Old UID snapshots without membership atoms require a forced refresh.

Every input uses a literal `day` partition filter. Representation compares one vendor at a time with the `initial` stage, using UNION and UID grouping rather than a many-to-many raw join. Publication compares staged assignments with final assignments using UNION and grouping by UID and canonical matchid. These comparisons require distributed grouping and can be expensive; they run only in the manual materializer. No queries run concurrently.

Additional metric types use the existing schema:

| Metric type | dimension_1 | dimension_2 | matchids | rows |
| --- | --- | --- | --- | --- |
| vendor_representation | Vendor | same_id / reassigned_only / unrepresented | Distinct source matchids | Distinct source UID/matchid combinations, including null UID groups |
| graph_size | graph_clean / graph_remainder | uids / relationships | NULL | Count in the specified unit |
| stage_publication | initial / stage1 / stage2 / louvain | published / not_published | Distinct canonical matchids | Distinct UID/matchid assignments |

Representation classifies each source matchid once. `same_id` means at least one source UID retains the numeric ID; `reassigned_only` means at least one source UID appears in initial output but none retain that ID; `unrepresented` means none of its UIDs appear there. Null UIDs cannot establish representation. These measurements do not establish a causal vendor merge or an exclusion reason. Representation uses unfiltered initial output; the existing stage totals apply final-output filters.

Publication compares exact `(uid, matchid)` membership and applies the `S_` prefix for stable staged IDs. A matchid can be both published and not published when different UID assignments have different outcomes. It can also appear in multiple stages. Those matchid counts are non-additive.

Graph counts measure distinct endpoint UIDs and relationship rows, not matchids. Process dependencies between IC stages remain schematic: aggregate counts do not determine which seed or relationship caused an assignment.

Previously committed days need `refresh --day YYYY-MM-DD --force` to populate the additional metrics. Until refreshed, the dashboard shows an explicit missing-metrics warning and unmeasured labels. No counts are filled in from subtraction.

Input availability comes from Iceberg partition metadata. Current retention differs across source tables. Older backfill days can therefore commit as `partial`. Missing groups remain recorded in the status table.

Refresh state progresses through `refreshing`, then `complete` or `partial`. Failures commit `failed` plus the error message. A retry with `--force` replaces failed or committed rows safely.

## Run dashboard

From repository root:

```bash
.venv/bin/streamlit run nscreen-graph-exploration/docs/matchid_flow_app/streamlit_app.py
```

Dashboard starts without running queries. Choose a pipeline day and click **Load snapshot**. Day changes never execute warehouse queries automatically. The first load retrieves committed dates for the day selector.

Complete days show one connected pipeline: vendors, all seven initial reasons, initial assignments, IC1, IC2, the same-geo remainder after IC2, Louvain, and one final output node. In Matchids mode, Initial, IC1, IC2, and LU use measured bands that stack at Final for comparison; their stage counts are not additive. Seed dependencies use dashed arrows. Clean IP-collocation feeds the propagation and remainder stages through schematic bands. Only unrepresented source branches appear in the diagram; detailed tables are not displayed. Graph boxes report UIDs and relationships without using the matchid scale. In UIDs mode, all four assignment stages contribute to Final; a warning identifies totals that do not reconcile with its distinct UID count.

Partial days show available vendor, stage, or final fallback charts. Sankey flow stays hidden unless every metric group exists.

Dashboard queries only the two Trino summary tables. Results cache for ten minutes.

Measured bands use a shared linear scale with a 15px minimum width. Small
measured bands are enlarged to that floor. Unmeasured dependencies use schematic
15px bands, and zero measured flows have no band. Matchid node heights use
the same scale, with room for incoming ribbons enlarged by the minimum rule.
The renderer uses Plotly paths and traces: semantic stage columns are fixed,
while source and reason rows are packed from their scaled heights and label
spacing. Unmeasured dependencies do not influence the matchid scale.
Exact labels and hover counts are unchanged by visual scaling.
The Initial-to-Final ribbon carries forward the display padding introduced by
minimum-height reason bands, filling Initial and stacking with IC1, IC2, and LU at Final.
This padding affects geometry only, not the reported distinct counts.
On the UID tab, Clean IP-collocation uses its measured distinct endpoint UID
count and the common UID scale (15px minimum for positive counts). The canvas
expands when needed to keep graph nodes visible. Clean-to-IC1/IC2 bands use each
stage's distinct newly assigned UID count after publication filters. Clean-to-remainder
uses measured distinct endpoints of the same-geo remainder graph, never subtraction.
These branches do not exhaust Clean UIDs: Initial seeds, publication filtering,
and graph edge/geography filtering also affect coverage. The remainder contains
same-geo edges whose endpoints remain unassigned after Initial, IC1, and IC2.
Unknown graph counts remain schematic. On the Matchids tab graph nodes remain
fixed-height.

Vendor-to-reason bands show shared attribution of initial output identities.
For LRTH, both LR and TH bands carry the LRTH count, retain the same thickness
at both ends, and overlap fully at the destination. LRTHEX has three such
bands. The destination height uses the count once, not the sum of vendor
contributions. This represents reason membership, not a measured one-to-one
mapping of original source matchids after alignment.

## Test

```bash
.venv/bin/ruff check nscreen-graph-exploration/docs/matchid_flow_app
.venv/bin/pytest -q nscreen-graph-exploration/docs/matchid_flow_app
```

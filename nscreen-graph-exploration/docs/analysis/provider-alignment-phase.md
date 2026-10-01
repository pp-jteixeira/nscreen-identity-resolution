# NScreen Provider Alignment (Phase 4)

Provider alignment merges the person-group identifiers (`matchid`) that LiveRamp, Throtle, and Experian each assign independently. The same real person can be group `t1` in Throtle's data and group `l1` in LiveRamp's data; UIDs present in both feeds are the translation evidence that links the two namespaces.

Everything in this page can be executed against toy tables with [`provider-alignment-toy.ipynb`](../../provider-alignment-toy.ipynb).

## Overview

Two Spark SQL jobs run in sequence and write into one table, `iceberg.crossscreen.nscreen_liveramp_throtle_ex_reason_staged`, partitioned by `day` and `stage`:

| Order | Job | SQL file | Reads | Writes stage |
| --- | --- | --- | --- | --- |
| 1 | Align LiveRamp and Throtle | [`NScreenLiverampThrotleOnlyStage.sql`](../../src/nscreen_graph/spark/sparksql/NScreenLiverampThrotleOnlyStage.sql) | `throtle_source`, `liveramp_source` (raw only) | `lrth` — **everything**, LiveRamp-rooted rows included (see below) |
| 2 | Add Experian | [`NScreenLiverampThrotleExInitialStage.sql`](../../src/nscreen_graph/spark/sparksql/NScreenLiverampThrotleExInitialStage.sql) | `experian_source` + staged `stage = 'lrth'` | `initial` |

> **The SQL's `stage` literals are discarded at write time — read this before trusting either SQL file.**
>
> Job 1's SQL ends in a union that labels `lr_out` as `'initial'` and `th_out` as `'lrth'`, so it *reads* as though it writes two stages. It does not. [`common.py:49-51`](../../src/nscreen_graph/spark/common.py#L49-L51) overwrites the column for every partition key:
>
> ```python
> for col_name, col_value in args.partition_columns:
>     df = df.withColumn(col_name, F.lit(col_value))
> ```
>
> and Job 1's task passes `partition_columns=[("day", self.day), ("stage", "lrth")]` ([`daily.py:299`](../../src/nscreen_graph/tasks/daily.py#L299)). So the `'initial'` literal on `lr_out` is thrown away and **Job 1's entire output — LiveRamp-rooted rows and Throtle leftovers alike — lands in `stage = 'lrth'`**. Job 2 passes `("stage", "initial")` and is the only writer of `initial`.
>
> Verified on day `2026-09-01`: `stage = 'lrth'` holds 3,761,176,262 rows with reason `LR` — rows the SQL text says should have gone to `initial`. Totals reconcile exactly: `lrth` = 6,136,216,738, and `initial` − `lrth` = 2,192,173,464, precisely Job 2's `ex_out` contribution.
>
> Consequence: **Experian *is* compared against LiveRamp-rooted rows**, producing the `LREX` reason (1,597,768,916 rows). Everything below reflects this real behaviour. The toy notebook explicitly reproduces the writer's partition overwrite, so its stage assignments match production rather than the discarded SQL literals.
>
> Full write-up, proofs and suggested fixes: [`provider-alignment-defects.md`](provider-alignment-defects.md).

Key structural facts:

- **All of Job 1's output is parked at `stage = 'lrth'`**, and Job 2 reads that whole partition — so every LiveRamp, Throtle and merged group gets an Experian check, not just the Throtle-only leftovers.
- The `initial` partition holds **only Job 2's** output: every `lrth` row rewritten (gaining an `EX` suffix where Experian matched), plus the Experian-only leftovers.
- Later pipeline phases append more stages to the same table: `connected_ns` (graph-connected copies of `initial`), `stage1`/`stage2` (propagation), `louvain` (clustering of the unresolved remainder).
- The final table, `nscreen_lr_throtle_ex_reason_result`, is a pure filter over `stage in ('initial', 'stage1', 'stage2', 'louvain')` — `lrth` and `connected_ns` are intermediate scratch stages ([`NScreenLrThrotleExReasonResult.sql`](../../src/nscreen_graph/spark/sparksql/NScreenLrThrotleExReasonResult.sql)).

## How a merge is decided: mutual-best rank

Both jobs use the same algorithm to decide whether two provider groups describe the same person:

1. Inner-join the two sources on `uid` — only UIDs present in both feeds count as evidence.
2. Group by the pair of matchids and count shared UIDs per candidate pairing.
3. `rank()` each pairing twice: within the first provider's matchid (by count, descending) and within the second's.
4. Keep only pairings ranked #1 in **both** directions.
5. Reject any matchid that still has more than one surviving pairing, checked independently on **both** sides via `count1` and `count2` (below) — **ties are rejected, not broken**.

An accepted pairing translates the whole losing-side group into the winning namespace. Precedence is fixed: **LiveRamp matchids always win** — an accepted merge relabels Throtle members with the LiveRamp id (`coalesce(m.lrmatchid, t.matchid)`), and a LiveRamp matchid itself is never rewritten, dropped, or merged into another LiveRamp matchid anywhere in the pipeline.

### The two uniqueness counters: `count1` and `count2`

Step 5 is where most rejected merges die, and it is two checks, not one. Both counters live in the `limited` CTE and are computed **after** the mutual-best filter has already run:

```sql
limited as (
    select throtmatchid, lrmatchid, ...,
        count(*) over (partition by throtmatchid) as count1,
        count(*) over (partition by lrmatchid)    as count2
    from ranked
    where rnk_1 = 1 and rnk_2 = 1     -- the counters only ever see survivors of this
),
mapping as (
    select ... from limited where count1 = 1 and count2 = 1
)
```

Each answers "how many surviving pairings does this one matchid still have?", once per side of the join:

| Counter | Partitioned by | Answers | `> 1` means | Case |
| --- | --- | --- | --- | --- |
| `count1` | `throtmatchid` | how many LiveRamp groups this Throtle group is still mutual-best with | one Throtle group tied between LiveRamp groups | [B1](#b1-count1--1-one-throtle-group-tied-between-two-liveramp-groups-t6-vs-l4l5) |
| `count2` | `lrmatchid` | how many Throtle groups are still mutual-best with this LiveRamp group | rival Throtle groups tie over one LiveRamp group | [B2](#b2-count2--1-an-unambiguous-throtle-group-killed-by-a-rival) |

`mapping` requires **both** to be 1, so a tie on either side discards *every* pairing involved rather than picking a winner. Two consequences that are easy to get wrong:

- **The counters count post-ranking survivors, not raw candidates.** A matchid may have many candidate pairings and still reach `count = 1`, because the weaker ones were already eliminated by `rnk_1 = 1 and rnk_2 = 1`. Having competition is not the same as having a tie.
- **The names are positional, so they mean different things in each job.** Job 2 reuses this exact structure but partitions by `exmatchid` (`count1`) and `lrthmatchid` (`count2`) — so there, `count1` is the *Experian* side, not the Throtle side. See [B4](#b4-the-same-filter-in-job-2--the-only-way-experian-evidence-is-lost).

### Reason codes

Row counts are the real `stage = 'initial'` distribution for day `2026-09-01` (8,328,390,202 rows total), which is the authoritative list — every reason the pipeline can emit into the final result appears here:

| Code | Meaning | Rows at `initial` |
| --- | --- | --- |
| `LR` | LiveRamp-only; no Throtle mutual-best match | 2,686,910,306 |
| `LREX` | LiveRamp-only group that aligned with Experian — **only possible because Job 1's rows all land in `lrth`** | 1,597,768,916 |
| `EX` | Experian-only | 1,380,675,882 |
| `LRTH` | LiveRamp and Throtle mutually aligned | 1,118,224,917 |
| `LRTHEX` | The merged group also aligned with Experian | 1,072,718,517 |
| `TH` | Throtle-only; no LiveRamp mutual-best match | 462,350,504 |
| `THEX` | Throtle-only group that also aligned with Experian | 9,741,160 |
| `NA` | Placeholder written by the `connected_ns` copy stage (never reaches the final result) | — (other stages) |
| `IC` | Assigned by IP-collocation propagation (`stage1`/`stage2`) | — (other stages) |
| `LU` | Assigned by Louvain clustering | — (other stages) |

## Vendor sources are not one-matchid-per-UID

A single UID can arrive from a vendor already assigned to **several** matchids on the same day. This is a property of the raw source data, measured directly per vendor:

```sql
select max(dm)                                as max_distinct_matchid,
       sum(case when dm > 1 then 1 else 0 end) as uids_with_multiple,
       count(*)                                as total_uids
from (
    select uid, count(distinct matchid) as dm
    from iceberg.crossscreen.<vendor>_source
    where day = '2026-09-01'
    group by uid
)
```

Results for day `2026-09-01`:

| Vendor | Source table | Max matchids for one UID | UIDs with more than one | Total UIDs | Share |
| --- | --- | --- | --- | --- | --- |
| Throtle | `throtle_source` | 34 | 4,554,945 | 1,107,933,029 | 0.41% |
| **LiveRamp** | `liveramp_source` | 9 | **449,232,710** | 4,851,683,059 | **9.26%** |
| Experian | `experian_source` | 1 | 0 | 2,937,977,238 | 0.00% |

So Throtle and LiveRamp both do it; Experian never does. Counter-intuitively, LiveRamp — the vendor whose matchid the pipeline treats as the anchor — is by far the most ambiguous by volume.

**Why LiveRamp can do this:** [`NScreenLiverampSource.sql`](../../src/nscreen_graph/spark/sparksql/NScreenLiverampSource.sql) reads the raw `iceberg.liveramp.ramp_id_mapping_flat` and groups by the **`(uid, ramp_id)` pair**, with `matchid = murmur3(ramp_id)`. If LiveRamp's raw file links one cookie to several `ramp_id` values on the same day (a mid-day re-link, a shared device, a correction), every pair survives as its own row with its own matchid. Nothing collapses them.

**A concrete production case:** UID `GvT54vuou0s4` on that day has 10 rows in `throtle_source` under 10 different matchids, zero rows in `liveramp_source`, and exactly one row in `experian_source`. All 10 Throtle claims flow through alignment as independent rows (6 stay `TH`, 4 mutual-best-matched into `LRTH`/`LRTHEX`) and all 10 reach the final result table.

The 4 translated ones are not a contradiction of "zero rows in `liveramp_source`" — the merge happens at the matchid level, not the UID level. `GvT54vuou0s4` never shows up in LiveRamp itself, but *other* cookies inside its Throtle groups do: e.g. Throtle matchid `-8004938733334738496` (one of `GvT54vuou0s4`'s 10) shares members `956784d1-41c0-4926-be69-9593f4adc6aa` and `gU7vY05WIWSw` with LiveRamp matchid `3832057527371444281`, so the whole Throtle group — `GvT54vuou0s4` included — gets translated to that LiveRamp id and reasoned `LRTHEX`. Same story for the other 3.

What each vendor source holds for this UID:

```sql
select 'throtle' as vendor, count(*) as rows, count(distinct matchid) as distinct_matchids
from iceberg.crossscreen.throtle_source where day = '2026-09-01' and uid = 'GvT54vuou0s4'
union all
select 'liveramp', count(*), count(distinct matchid)
from iceberg.crossscreen.liveramp_source where day = '2026-09-01' and uid = 'GvT54vuou0s4'
union all
select 'experian', count(*), count(distinct matchid)
from iceberg.crossscreen.experian_source where day = '2026-09-01' and uid = 'GvT54vuou0s4'
```

```text
  vendor  rows  distinct_matchids
 throtle    10                 10
liveramp     0                  0
experian     1                  1
```

How those claims land in the staged table, one row per stage and matchid:

```sql
select stage, matchid, reason, count(*) as n
from iceberg.crossscreen.nscreen_liveramp_throtle_ex_reason_staged
where day = '2026-09-01' and uid = 'GvT54vuou0s4'
group by stage, matchid, reason
order by stage, matchid
```

```text
  stage              matchid reason  n
initial -8490481450862571767   LRTH  1
initial -5887382878854291301     TH  1
initial -5450918708626096654     TH  1
initial -2182241775974019621     TH  1
initial -1283334461189994691     TH  1
initial -1216705581522890552     TH  1
initial  -813781276054845002     TH  1
initial  1118326471835818515   LRTH  1
initial  3832057527371444281 LRTHEX  1
initial  8127405688148854093 LRTHEX  1
   lrth -8490481450862571767   LRTH  1
   lrth -5887382878854291301     TH  1
   lrth -5450918708626096654     TH  1
   lrth -2182241775974019621     TH  1
   lrth -1283334461189994691     TH  1
   lrth -1216705581522890552     TH  1
   lrth  -813781276054845002     TH  1
   lrth  1118326471835818515   LRTH  1
   lrth  3832057527371444281   LRTH  1
   lrth  8127405688148854093   LRTH  1
```

The same 10 matchids appear at both stages; the only difference is the reason on the two Experian-matched groups (`LRTH` at `lrth`, bumped to `LRTHEX` at `initial`).

And all of them surviving into the final result table:

```sql
select uid, matchid, reason
from iceberg.crossscreen.nscreen_lr_throtle_ex_reason_result
where day = '2026-09-01' and uid = 'GvT54vuou0s4'
```

```text
         uid                matchid reason
GvT54vuou0s4  S_8127405688148854093 LRTHEX
GvT54vuou0s4 S_-1283334461189994691     TH
GvT54vuou0s4 S_-5887382878854291301     TH
GvT54vuou0s4 S_-1216705581522890552     TH
GvT54vuou0s4  S_1118326471835818515   LRTH
GvT54vuou0s4  S_3832057527371444281 LRTHEX
GvT54vuou0s4 S_-2182241775974019621     TH
GvT54vuou0s4 S_-8490481450862571767   LRTH
GvT54vuou0s4 S_-5450918708626096654     TH
GvT54vuou0s4  S_-813781276054845002     TH
```

All 10 matchids survive, `S_`-prefixed (stable) by the final job.

These source-level ambiguities are the raw material the toy example below reproduces with `v6` (Throtle side) and `v13` (LiveRamp side).

## Toy example: every case in one dataset

One small dataset produces every pattern the alignment phase can exhibit. Symbolic ids replace production values: `T*` for Throtle matchids, `L*` for LiveRamp, `E*` for Experian, `v*` for UIDs. (Production matchids are `bigint` murmur3 hashes; the toy uses `varchar`, so matchid tie-breaks sort lexicographically instead of numerically — same code path, different collation.)

### Cast of UIDs

| uid | Story |
| --- | --- |
| `v1` | Clean, direct LiveRamp member; group merges with Throtle; IP-graph connected |
| `v2` | Same merged group, not graph-connected |
| `v4`, `v10` | Clean members of a second merged group |
| `v9` | LiveRamp member of `L1` with no Throtle row of its own — inherits the group's merge anyway; also graph-connected to `v24`/`v25`/`v26` by an IP-collocation edge each, which makes all four graph-connected without changing anyone's matchid |
| `v3` | Throtle-leftover whose group merges with LiveRamp, later also matched by Experian |
| `v5` | Throtle-leftover whose group never merges with anything |
| `v6` | **Throtle-side ambiguous** — one UID claimed by three Throtle groups; graph-connected |
| `v13` | **LiveRamp-side ambiguous** — one UID claimed by two LiveRamp groups |
| `v14` | Member of the unmerged group `v13` also belongs to |
| `v15` | Experian-only UID that inherits a LiveRamp matchid through its group's alignment |
| `v16` | Experian-only UID with no alignment at all |
| `v17` | Reached by propagation, one hop from `v1` |
| `v18` | Reached by propagation, two hops (via `v17`) |
| `v20` | Reached by propagation from the ambiguous seed `v6` |
| `v19`, `v21` | Never resolved by providers or propagation; clustered together by Louvain |
| `v22`…`v27` | **Tie edge case** — one Throtle group (`T6`) overlapping two LiveRamp groups equally (`v22` in `L4`, `v23` in `L5`). `v24`/`v25`/`v26` are the three of `T6`'s tie-rejected members wired to `v9` (see above) |
| `v30`, `v31` | LiveRamp-only group (`L6`) with no Throtle overlap at all, that independently aligns with Experian (`E3`) — demonstrates `LREX` without ever touching Throtle |
| `v32` | Experian-only UID that inherits `L6` through that same `E3` alignment |
| `v33`, `v34` | **Geo-mismatch edge case** — an IP-collocation edge with the same weight as `v19`↔`v21`, but `v33` sits in geo `G3` and `v34` in `G4`. Never resolved by anything, ever — not even the `NA` placeholder, since neither UID has any vendor row to seed `connected_ns` |

### Source tables

**`throtle_source`**

| uid | matchid |
| --- | --- |
| v1 | T1 |
| v2 | T1 |
| v3 | T1 |
| v4 | T2 |
| v5 | T9 |
| v6 | T3 |
| v6 | T4 |
| v6 | T5 |
| v22 | T6 |
| v23 | T6 |
| v24 | T6 |
| v25 | T6 |
| v26 | T6 |
| v27 | T6 |

`v6` has three rows, one per matchid — Throtle handing the same UID to three groups, the same shape as the production case above. `T6` is one well-formed group of six cookies; its trouble comes from the LiveRamp side.

**`liveramp_source`**

| uid | matchid |
| --- | --- |
| v1 | L1 |
| v2 | L1 |
| v9 | L1 |
| v4 | L2 |
| v10 | L2 |
| v13 | L2 |
| v13 | L3 |
| v14 | L3 |
| v22 | L4 |
| v23 | L5 |
| v30 | L6 |
| v31 | L6 |

`v13` has two rows, under `L2` and `L3` — LiveRamp-side ambiguity. Two members of Throtle's `T6` sit in two *different* LiveRamp groups (`v22`→`L4`, `v23`→`L5`), setting up a tie. `L6` (`v30`, `v31`) has no Throtle overlap at all — it only ever aligns with Experian.

**`experian_source`**

| uid | matchid |
| --- | --- |
| v3 | E1 |
| v15 | E1 |
| v16 | E2 |
| v30 | E3 |
| v32 | E3 |

**IP-collocation graph** (`nscreen_ipcollocation_daily_clean` — one row per edge; sourced from `iceberg.fact.visitorlogevent` / `recordingpixellogevent` activity logs, never from vendor tables):

| uid1 | uid2 | weight |
| --- | --- | --- |
| v1 | v17 | 5 |
| v17 | v18 | 3 |
| v6 | v20 | 2 |
| v19 | v21 | 4 |
| v33 | v34 | 3 |
| v9 | v24 | 4 |
| v9 | v25 | 4 |
| v9 | v26 | 4 |

`v20` and `v21` exist only as neighbors: `v20`'s edge makes `v6` graph-connected and makes `v20` itself reachable by propagation; `v21` gives `v19` the edge required to reach Louvain at all (the remainder step only keeps edges whose endpoints share a geo bucket — an edge-less UID never gets a Louvain assignment). `v33`↔`v34` demonstrates a geo-mismatched edge being excluded exactly like no edge at all. `v9`↔`v24`/`v25`/`v26` links a resolved LiveRamp-only UID to three tie-rejected Throtle leftovers — all four already have a matchid by the time `connected_ns` runs, so the edges make them graph-connected without making any of them a propagation candidate (see Phase 5 below).

### Job 1 — Align LiveRamp and Throtle

Candidate pairings from the UID join (`grouped` CTE):

| throtmatchid | lrmatchid | shared UIDs |
| --- | --- | --- |
| T1 | L1 | 2 (v1, v2) |
| T2 | L2 | 1 (v4) |
| T6 | L4 | 1 (v22) |
| T6 | L5 | 1 (v23) |

`L6` has no Throtle overlap, so it never appears in this join at all — it only becomes reachable through Job 2's Experian comparison. `T1→L1` and `T2→L2` are the only candidate on each side → mutual-best → accepted. `T6` ties: `rank()` gives both its pairings `rnk_1 = 1`, both survive into `limited`, `count1 = 2` for `T6` fails the uniqueness filter — **both rejected** (see B1).

**Accepted mapping:** `T1 → L1`, `T2 → L2`.

`lr_out` — every LiveRamp row, matchid kept verbatim, reason `LRTH` where the matchid is in the accepted mapping, else `LR`:

| uid | matchid | reason |
| --- | --- | --- |
| v1 | L1 | LRTH |
| v2 | L1 | LRTH |
| v9 | L1 | LRTH |
| v4 | L2 | LRTH |
| v10 | L2 | LRTH |
| v13 | L2 | LRTH |
| v13 | L3 | LR |
| v14 | L3 | LR |
| v22 | L4 | LR |
| v23 | L5 | LR |
| v30 | L6 | LR |
| v31 | L6 | LR |

`th_out` — Throtle rows whose UID never appears in `liveramp_source` (`th_only` is a per-UID existence check, so `v1`/`v2`/`v22`/`v23` drop out here even though they belong to Throtle groups), matchid translated via `coalesce(m.lrmatchid, t.matchid)`:

| uid | matchid | reason |
| --- | --- | --- |
| v3 | L1 | LRTH (inherits T1's merge) |
| v5 | T9 | TH |
| v6 | T3 | TH |
| v6 | T4 | TH |
| v6 | T5 | TH |
| v24 | T6 | TH (tie-rejected, keeps its own id) |
| v25 | T6 | TH |
| v26 | T6 | TH |
| v27 | T6 | TH |

The SQL text labels `lr_out` as `stage = 'initial'` and `th_out` as `stage = 'lrth'`, but the writer overwrites both with the literal the task passes (see the Overview warning), so — production-faithfully — **all 21 rows of both tables land in `stage = 'lrth'`**. The toy notebook reproduces this exactly; there is no toy-vs-production divergence left at this step.

### Job 2 — Add Experian

Reads `stage = 'lrth'` (all 21 rows above) plus `experian_source` (5 rows). Two shared UIDs each give one candidate pairing: `v3` gives `(E1, L1)`, `v30` gives `(E3, L6)` — both mutual-best by default, since neither has a rival.

**Accepted mapping:** `E1 → L1`, `E3 → L6`.

Every `lrth` row is rewritten to `stage = 'initial'`; the matchid never changes, only the reason gains `EX` where its matchid matched. Experian-only leftovers (`ex_only`/`ex_out`) follow the same translate-or-keep pattern:

| uid | matchid | reason |
| --- | --- | --- |
| v1, v2, v9, v3 | L1 | LRTHEX (L1 matched via E1) |
| v4, v10, v13 | L2 | LRTH (unchanged — L2 never reached Experian) |
| v13, v14 | L3 | LR (unchanged) |
| v22 | L4 | LR (unchanged) |
| v23 | L5 | LR (unchanged) |
| v5 | T9 | TH (unchanged) |
| v6 | T3 / T4 / T5 | TH (three rows, unchanged) |
| v24…v27 | T6 | TH (unchanged) |
| v30, v31 | L6 | LREX (L6 matched via E3) |
| v15 | L1 | LRTHEX (Experian-only, inherits L1 via E1's alignment) |
| v16 | E2 | EX |
| v32 | L6 | LREX (Experian-only, inherits L6 via E3's alignment) |

24 rows in total. `L6`'s merge shows that `LREX` needs no Throtle involvement whatsoever — it is purely a LiveRamp↔Experian alignment, reachable only because Job 1 parks `lr_out` in `lrth` alongside everything else.

### Phase 5 — connected seeds and propagation

`connected_ns` ([`NScreenLiverampThrotleExConnectedNsStage.sql`](../../src/nscreen_graph/spark/sparksql/NScreenLiverampThrotleExConnectedNsStage.sql)) copies each `initial` row whose UID appears anywhere in the edge table, with `reason` hardcoded to `'NA'`. The join is on UID, so an ambiguous UID's rows are all copied:

| uid | matchid | reason |
| --- | --- | --- |
| v1 | L1 | NA |
| v6 | T3 | NA |
| v6 | T4 | NA |
| v6 | T5 | NA |
| v9 | L1 | NA |
| v24 | T6 | NA |
| v25 | T6 | NA |
| v26 | T6 | NA |

`v9`, `v24`, `v25` and `v26` are new here: the `v9`↔`v24`/`v25`/`v26` edges make all four graph-connected, but every one of them already had a matchid from provider alignment, so this step only adds a stage and an `NA` reason — it assigns nothing new. `v22`, `v23`, `v30`, `v31` and `v32` are not touched by any edge, so despite being merged or LiveRamp-only, none of them ever appears in `connected_ns`.

Propagation ([`NScreenLiverampThrotleExNStage.sql`](../../src/nscreen_graph/spark/sparksql/NScreenLiverampThrotleExNStage.sql), run twice) doubles every edge, sums edge weight per `(uid, matchid)` candidate, drops UIDs that already have a matchid, keeps one winner per UID (`row_number() … order by weight desc, matchid desc`), and caps each matchid at ten new UIDs per round:

| stage | uid | matchid | reason | note |
| --- | --- | --- | --- | --- |
| stage1 | v17 | L1 | IC | one hop from v1 |
| stage1 | v20 | T5 | IC | three-way tie (T3/T4/T5, weight 2 each) broken by `matchid desc` |
| stage2 | v18 | L1 | IC | one hop from v17, which joined the seed set after stage1 |

An ambiguous seed stays ambiguous itself, but anything reached *from* it gets exactly one matchid — picked by a tie-break, not by evidence. `v1` and `v6` are re-reached as candidates in stage2 and dropped by `filter_out_having_matchid`. The `v9`↔`v24`/`v25`/`v26` edges never even produce a propagation candidate in either round, for the same reason `connected_ns` assigned nothing: all four endpoints already have a matchid before propagation starts, so `filter_out_having_matchid` drops every candidate row they would otherwise generate.

#### Observed versus expected result

Observed behavior is `v9`→`L1` and `v24`/`v25`/`v26`→`T6`. Their graph connections only create `connected_ns` copies with reason `NA`; `filter_out_having_matchid` then removes every endpoint before propagation ranking. No new matchid is assigned.

Expected behavior is not tied to LiveRamp precedence. Strong IP-collocation or first-party evidence, supported by compatible device signals, should reconcile already-assigned matchids across any provider combination. In this case, sufficiently strong evidence should place `v9`, `v24`, `v25`, and `v26` under one canonical matchid; the canonical value need not be `L1` or `T6`.

The same expectation applies inside one vendor namespace. A UID such as `v6`, claimed by `T3`, `T4`, and `T5`, or `v13`, claimed by `L2` and `L3`, should not reach the published graph with several matchids. Every published UID should map to exactly one canonical matchid, while each canonical matchid may contain many UIDs.

This expected behavior is not implemented. Source-level ambiguity is covered by [`provider-source-multi-assignment-plan.md`](../plans/provider-source-multi-assignment-plan.md). Reconciliation between already-assigned groups using graph evidence remains separate.

### Phase 6 — remainder and Louvain

The remainder step ([`NScreenIpCollocationDailyExRemainder.sql`](../../src/nscreen_graph/spark/sparksql/NScreenIpCollocationDailyExRemainder.sql)) keeps an edge only when **both** endpoints are unassigned (`stage in ('initial','stage1','stage2')`) and share a geo bucket. Only `v19`↔`v21` survives — `v33`↔`v34` has two unassigned endpoints too, but `v33` sits in geo `G3` and `v34` in `G4`, so `where g1.geo = g2.geo` drops it. The clustering step ([`NScreenExRemainderLouvainStage.sql`](../../src/nscreen_graph/spark/sparksql/NScreenExRemainderLouvainStage.sql)) feeds surviving edges per geo into the [`hudf_calc_screen7_ids_udaf` UDAF](../udaf-calc-screen7-ids-evaluator.md) and emits a row for **both** endpoints of every edge, stamped `stable = false, reason = 'LU'`:

| stage | uid | matchid | reason |
| --- | --- | --- | --- |
| louvain | v19 | C1 | LU |
| louvain | v21 | C1 | LU |

`C1` is a placeholder for the synthetic numeric community id the UDAF computes. `v33` and `v34` end the pipeline with zero rows anywhere in the staged table — not even the `NA` placeholder, since neither ever had a vendor row for `connected_ns` to copy.

### Full staged table

58 rows for the toy day:

| stage | rows |
| --- | --- |
| initial | 24 — v1, v2, v9, v3 (L1, LRTHEX); v4, v10, v13 (L2, LRTH); v13, v14 (L3, LR); v22 (L4, LR); v23 (L5, LR); v5 (T9, TH); v6 ×3 (T3/T4/T5, TH); v24…v27 (T6, TH); v30, v31 (L6, LREX); v15 (L1, LRTHEX); v16 (E2, EX); v32 (L6, LREX) |
| lrth | 21 — every row above except v15/v16/v32 (Experian-only leftovers, which only ever reach `initial`), with reasons as Job 1 left them (`LRTH`/`LR`/`TH` — no `EX`/`LREX` yet) |
| connected_ns | 8 — v1, v6 ×3 (L1/T3/T4/T5); v9, v24, v25, v26 (L1/T6 ×3, newly graph-connected) |
| stage1 | 2 — v17 (L1); v20 (T5) |
| stage2 | 1 — v18 (L1) |
| louvain | 2 — v19, v21 (C1) |

### The diagnostic query

```sql
select uid,
       count(distinct stage)   as distinct_stage,
       count(distinct matchid) as distinct_matchid,
       count(distinct reason)  as distinct_reason
from nscreen_liveramp_throtle_ex_reason_staged
where day = :day
group by uid
```

| uid | distinct_stage | distinct_matchid | distinct_reason | why |
| --- | --- | --- | --- | --- |
| v15, v16, v17, v18, v19, v20, v21, v32 | 1 | 1 | 1 | Each assigned exactly once — Experian-inherit, no-alignment, propagation, and Louvain all write a single row |
| v4, v5, v10, v14, v22, v23, v27 | 2 | 1 | 1 | Ordinary lineage: identical matchid and reason carried unchanged from `lrth` to `initial` |
| v2, v3, v30, v31 | 2 | **1** | **2** | Same matchid both stages; only the reason gained `EX`. Multi-stage ≠ ambiguous |
| **v13** | **2** | **2** | 2 | LiveRamp-side ambiguity — `L2` and `L3` both carried from `lrth` to `initial`. Two distinct matchids, not resolved by the extra stage |
| v24, v25, v26 | **3** | 1 | 2 | Newly graph-connected Throtle leftovers: `lrth` → `initial` (unchanged `TH`) → `connected_ns` (`NA`). One matchid throughout — being graph-connected added a stage and a reason, never a second matchid |
| v1, v9 | **3** | 1 | **3** | Same shape as v24-26, but the matchid itself changed reason along the way: `LRTH` (`lrth`) → `LRTHEX` (`initial`) → `NA` (`connected_ns`) |
| **v6** | **3** | **3** | 2 | Throtle-side ambiguity at maximum fan-out: 3 matchids × 3 stages = 9 rows |

`v33` and `v34` never appear in this table at all — the staged-table diagnostic query only sees UIDs with at least one row, and they have none. Reading the rest: `distinct_reason > 1` is usually harmless (an `EX` suffix or `NA` placeholder picked up between stages). **`distinct_matchid > 1` is the real ambiguity signal**, and it can occur at any stage count.

### Final result

`nscreen_lr_throtle_ex_reason_result` filters `stage in ('initial','stage1','stage2','louvain')` with **no per-UID deduplication**: 29 rows for 26 UIDs. `v6` keeps three matchids, `v13` keeps two, and everyone else keeps exactly one — including `v30`/`v31`/`v32`, which surface here as ordinary `LREX` rows despite never touching Throtle. `v33` and `v34` are excluded entirely: they have no rows in `initial`/`stage1`/`stage2`/`louvain` to filter in the first place, so they leave no trace in the final result even though their rejected edge is visible further upstream in the IP-collocation graph. See the no-per-UID-deduplication invariant below.

## Edge cases in detail

The cases below are grouped by *mechanism*, because they are not independent surprises — they are four distinct ways the same design produces more matchids than people:

| Family | What goes wrong | Cases |
| --- | --- | --- |
| **A. Source-level ambiguity** | A vendor hands one UID to several groups; nothing collapses them | A1, A2, A3 |
| **B. Arbitration failure** | Mutual-best-rank refuses to merge, or merges only half | B1, B2, B3, B4 |
| **C. Reason-code fidelity** | A lexicographic `max()` that *would* mislabel lineage — currently unreachable | C1 (latent) |
| **D. Assignment loss in propagation** | A UID that had a valid candidate matchid ends up with none | D1, D2 |

### The invariant behind all of them: no per-UID deduplication

Every case in families A and B survives to the final result for one reason — no step in provider alignment groups or ranks by UID:

- `th_only` filters rows by UID *existence* in LiveRamp (`left join … where lr.uid is null`) — a pass-through, not a `group by uid`.
- `th_out`, `lr_out`, `lrth_out`, `ex_out` all join **by matchid**, translating each row independently.
- `connected_ns` joins on UID with an inner join that *multiplies* rows.
- The final result job is a pure filter: no `group by`, no window function.

The only one-matchid-per-UID guarantees live in the propagation stages (`row_number() over (partition by uid …) where rnk = 1`) and the remainder/Louvain path (already-assigned UIDs excluded before clustering) — which is exactly why family D, alone among the four, loses UIDs instead of duplicating them. The mutual-best-rank logic arbitrates between *group pairings*, never between multiple group claims on one UID. Consequently the final result table carries every surviving vendor ambiguity: 3 rows for `v6`, 2 for `v13` — and, in production, 10 rows for `GvT54vuou0s4` and 16 for `ZdliXvA3mN7G` (the same matchids as their staged rows, `S_`-prefixed as stable).

## A. Source-level ambiguity

### A1. One UID claimed by several Throtle groups, no vendor overlap (`v6`)

Raw `throtle_source` lists `v6` under `T3`, `T4`, and `T5`. Because `v6` never appears in `liveramp_source`, all three rows pass the `th_only` existence check, each is translated (or not) independently against the mapping, and each becomes its own row — first in `lrth`, then in `initial`, then (being graph-connected) in `connected_ns`: 9 rows, 3 matchids, all the way through. This is the toy version of the production UID with 10 Throtle matchids (`GvT54vuou0s4`, above).

Had `v6` appeared in `liveramp_source` even once, the picture flips completely: `th_only` excludes by UID, so *all* of its Throtle rows would vanish from `th_out`, and `v6` would carry only its LiveRamp row(s). Throtle-side ambiguity only surfaces for UIDs LiveRamp has never seen.

**A purer production case, at higher fan-out:** UID `ZdliXvA3mN7G` on day `2026-09-01` has 16 rows in `throtle_source` under 16 distinct matchids, and — unlike `GvT54vuou0s4` — zero rows in *both* `liveramp_source` and `experian_source`. No vendor overlap at all; the ambiguity is 100% Throtle-internal.

```text
  vendor  rows  distinct_matchids
 throtle    16                 16
liveramp     0                  0
experian     0                  0
```

All 16 land in `lrth` as independent rows, carry through to `initial` unchanged, and all 16 reach the final result — 13 stay `TH`, and 3 of the raw Throtle matchids get translated to LiveRamp ids via shared cookies with those LiveRamp groups (same matchid-level mechanism as `GvT54vuou0s4` above, not UID-level): two become `LRTH`, and one — the group whose translated LiveRamp id also shares 8 UIDs with an Experian matchid — becomes `LRTHEX`:

```text
  stage              matchid reason  n
initial -8379506257431031256     TH  1
initial -7619694079636983908     TH  1
initial -7591772382519868254   LRTH  1
initial -6605006532602649816     TH  1
initial -4828076046841646713     TH  1
initial -3179560937358015080     TH  1
initial -2818080785267229724     TH  1
initial -2468119499862414841     TH  1
initial -1885860920421079378     TH  1
initial -1800687985291331787   LRTH  1
initial   685853806811518432     TH  1
initial  1461464589168785724     TH  1
initial  5241510650893920708     TH  1
initial  6120408918303370660     TH  1
initial  6370961600017075680 LRTHEX  1
initial  8655272518321050211     TH  1
   lrth  ... (same 16 matchids, LRTHEX row shows as LRTH pre-Experian bump)
```

32 staged rows (16 matchids × 2 stages), all 16 matchids surviving `S_`-prefixed into `nscreen_lr_throtle_ex_reason_result`. Queried the same way as the `GvT54vuou0s4` trace above, swapping in `uid = 'ZdliXvA3mN7G'`.

### A2. Same, but the UID also has its own row in another vendor (`GvT54vuou0s4`)

`ZdliXvA3mN7G` above has zero rows of its own in `liveramp_source` *and* `experian_source`. `GvT54vuou0s4` (walked through in full [earlier](#vendor-sources-are-not-one-matchid-per-uid)) differs in exactly one respect: it has one row of its own in `experian_source`. The distinction matters less than it looks, and understanding why pins down where vendor evidence actually enters.

That Experian row never becomes a row in the output. `ex_only` selects Experian rows *whose UID never appears in the `lrth` stage*, and `GvT54vuou0s4` is all over `lrth` (10 rows) — so its Experian row is filtered out of `ex_only` entirely. Its only effect is upstream, inside Job 2's `joined` CTE, where it is one shared UID contributing to a `(exmatchid, lrthmatchid)` pairing count.

So a UID's own row in a secondary vendor is **evidence, never output**. What reaches the result is decided entirely at matchid level: 6 of its 10 Throtle matchids stayed `TH`, 4 were translated to LiveRamp ids by merges its *group peers* earned. Identical mechanism to `ZdliXvA3mN7G`'s 13/3 split — the UID's own cross-vendor presence changes nothing about its fan-out.

### A3. One UID claimed by several LiveRamp groups (`v13`)

`lr_out` has no per-UID filter at all — it is a pure pass-through of every `liveramp_source` row, each independently checked against the mapping. `v13`'s two rows (`L2`/LRTH, `L3`/LR) both reach the final result. In both the production-faithful toy and production, LiveRamp-rooted rows pass through `lrth` before `initial`, so `v13` has `distinct_matchid = 2` and `distinct_stage = 2`. The ambiguity signal is the two matchids, not the stage count.

At production scale this is the dominant ambiguity channel: ~9.26% of LiveRamp UIDs carry more than one matchid per day, and that population accounts for nearly all multi-matchid UIDs observed in the staged table.

### The non-case: A1 and A3 cannot compound

The intuitive worst case — one UID that is multi-matchid in Throtle **and** multi-matchid in LiveRamp — does not exist. `th_only` excludes by UID, so the moment a UID appears anywhere in `liveramp_source`, *all* of its Throtle rows drop out of `th_out` (the mechanism spelled out at the end of A1). Throtle-side fan-out and LiveRamp-side fan-out are therefore mutually exclusive per UID, and the combined case collapses into a plain A3. Worst-case fan-out for one UID is `max(throtle_matchids, liveramp_matchids)`, never the product.

## B. Arbitration failure

All four cases in this family come from one filter — `mapping`'s `where count1 = 1 and count2 = 1` — and differ only in which side fails and what is left behind.

### B1. `count1 > 1`: one Throtle group tied between two LiveRamp groups (`T6` vs `L4`/`L5`)

`(T6, L4)` and `(T6, L5)` tie at 1 shared UID. `rank()` (not `row_number()`) gives *both* pairings `rnk_1 = 1`; both also rank #1 in their LiveRamp partitions; both survive into `limited` — where `count1 = 2` for `T6` fails the `count1 = 1` uniqueness filter and **both pairings are rejected**. Which LiveRamp id does the group keep? **Both — as separate, unmerged identities:**

| uid | matchid | reason |
| --- | --- | --- |
| v22 | L4 | LR |
| v23 | L5 | LR |
| v24…v27 | T6 | TH |

One person-group fractures into **three** matchids, and nothing downstream re-links them. The rejection also leaves no trace: `v22` and `v23` are indistinguishable from ordinary clean LiveRamp-only UIDs.

### B2. `count2 > 1`: an unambiguous Throtle group killed by a rival

B1 is the `count1` failure. The `count2` failure (both counters are defined [above](#the-two-uniqueness-counters-count1-and-count2)) is a different animal: a Throtle group can have **exactly one** candidate LiveRamp partner in the entire day — no ambiguity whatsoever, `count1 = 1` — and still lose its merge, because some *other* Throtle group also ranks #1 against that same LiveRamp group. The rejection is caused entirely by a third party the group has no connection to.

**Production instance** (day `2026-09-01`). LiveRamp matchid `1672929395374000007` (9 UIDs) is contested by two Throtle groups of 3 UIDs each:

| throtmatchid | shared UIDs with `1672929395374000007` | its other pairings | `rnk_1` | `rnk_2` | `count1` | `count2` |
| --- | --- | --- | --- | --- | --- | --- |
| `-6863688456848774365` | 2 | none | 1 | 1 | **1** | 2 |
| `7165122047246051412` | 2 | none | 1 | 1 | **1** | 2 |

Both Throtle groups are individually unambiguous. Both tie at 2 shared UIDs, so both clear `rnk_1 = 1` *and* `rnk_2 = 1` and enter `limited` — where `count2 = 2` for the LiveRamp group fails the filter and **both pairings are dropped**. Confirmed in the staged table (`initial` and `lrth` identical):

```text
matchid                reason  uids
1672929395374000007    LR         9
-6863688456848774365   TH         1
7165122047246051412    TH         1
```

Three matchids where there should have been one. Each Throtle group shows only 1 UID because `th_only` drops the 2 shared UIDs — those survive under the LiveRamp matchid as `LR`.

**A `rnk_2` tie alone is not enough.** Two pairings ranking #1 within the same `lrmatchid` partition is harmless if one of them fails `rnk_1 = 1` — it never reaches `limited`, so `count2` stays 1 and the surviving merge goes through (observed on `429814633434400007`, where the loser had `rnk_1 = 2`). `count2 > 1` requires **both** competitors to be mutual-best simultaneously.

### B3. Merge accepted, losing LiveRamp group stranded

The mirror of B1: here the filter *passes* and a merge happens — yet a fragment is still left behind. Same setup as B1, plus an extra shared UID `v28` in both `T6` and `L4`, so `(T6, L4)` has 2 shared UIDs against `(T6, L5)`'s 1. Now `(T6, L4)` is the unique rank-1 on both sides → `count1 = 1` → **accepted**: `T6 → L4`.

| uid | matchid | reason |
| --- | --- | --- |
| v22, v28 | L4 | LRTH |
| v24…v27 | L4 | LRTH (translated from T6) |
| v23 | **L5** | **LR — stranded** |

Winning the rank pulls in the Throtle-side leftovers, but the **losing LiveRamp group is never folded in** — there is no LiveRamp-to-LiveRamp merge mechanism anywhere in the pipeline. However strong the evidence, a person whose UIDs span *n* LiveRamp groups ends up under at least *n* matchids. Three identities in the tie case, two in this one; one is unreachable.

### B4. The same filter in Job 2 — the only way Experian evidence is lost

Job 2 reuses the identical structure on `(exmatchid, lrthmatchid)`: `rank()` on both sides, `where rnk_1 = 1 and rnk_2 = 1`, then `where count1 = 1 and count2 = 1`. Because `experian_source` carries exactly one matchid per UID (0% ambiguity — see the vendor table above), Experian contributes no A-family fan-out at all. **Tie rejection is therefore the only channel through which Experian evidence gets discarded.**

**Production instance** (day `2026-09-01`, a `count2 = 2` rejection). The `lrth` group `-7674333472984662009` (11 UIDs, reason `LRTH`) has exactly two Experian pairings:

| exmatchid | its group size | shared UIDs | its other pairings | `rnk_1` | `rnk_2` |
| --- | --- | --- | --- | --- | --- |
| `-5418077641914570113` | 2 | 1 | none | 1 | 1 |
| `1062570833093543237` | 4 | 1 | none | 1 | 1 |

Both Experian groups pair *only* with this one group, so both take `rnk_1 = 1`; the group's best pairing count is 1, which both achieve, so both take `rnk_2 = 1`. Both enter `limited`, `count2 = 2`, and both are rejected. The consequence, confirmed exactly:

```text
stage    reason  rows
lrth     LRTH      11
initial  LRTH      11
```

Identical at both stages — the group never gains its `EX` suffix, though two independent Experian groups pointed at it. The unmatched Experian UIDs land under their own Experian matchids with reason `EX` instead.

As in B2, ranking happens *before* counting, so simply having several candidate pairings is not a tie: `8340902630477996039` has multiple pairings but a clear winner, and it does receive `LREX` (20 `lrth` rows plus 5 absorbed Experian-only UIDs).

**There is no LiveRamp blind spot.** An earlier reading of this pipeline — that Experian is never compared against LiveRamp-rooted rows, since Job 2 reads only `lrth` — is wrong, for the reason set out in the Overview: Job 1 writes *everything* to `lrth`. LiveRamp-rooted groups get a full Experian check, and 1,597,768,916 rows carry the resulting `LREX`. What remains is not a skipped comparison but a *rejected* one: on a 1/1024 UID-hash slice, ≈412M UIDs carry reason `LR` at `initial` while also having a row in `experian_source` (sampled; the slice reproduces both partition totals when scaled). For those, Experian evidence existed, was examined, and lost to a rank or tie failure.

## C. Reason-code fidelity

### C1. `max(reason)` is a latent mislabel, disarmed by B2's filter

Job 2's `grouped` CTE aggregates the reason string:

```sql
select exmatchid, lrthmatchid, max(reason) as reason, count(*) as cnt
from joined group by exmatchid, lrthmatchid
```

and `ex_out` stamps Experian-only UIDs with `concat(m.reason, 'EX')`. That `max()` is **lexicographic**, and `'TH' > 'LRTH'` because `T > L`. So if any `(exmatchid, lrthmatchid)` group ever contained a mix of `LRTH` and `TH` rows, `max()` would return `TH` and the inherited row would be stamped `THEX` — even though the matchid it inherits is a LiveRamp id with an `LRTH` lineage. `LRTHEX` would silently become `THEX`.

**This does not happen in production, and cannot.** Reason is functionally determined by matchid at the `lrth` stage, which carries exactly three reasons (`LR`, `LRTH`, `TH`). Take any matchid there:

- A **Throtle** matchid appears only via `th_out` and only when unmerged → always `TH`.
- A **LiveRamp** matchid that is in `mapping` gets `LRTH` from `lr_out` (its own UIDs) *and* `LRTH` from `th_out` (the absorbed group) → still homogeneous.
- A **LiveRamp** matchid not in `mapping` appears only via `lr_out` → always `LR`.

There is no arrangement that mixes two reasons under one matchid, and B2's `count2 = 1` filter is what closes the last door: at most one Throtle group can ever translate into a given LiveRamp matchid. Every `grouped` partition is therefore reason-homogeneous and `max()` is a no-op. Verified across the full `lrth` partition for `2026-09-01` — of its 741,332,855 distinct matchids, **zero** carry more than one distinct reason:

```sql
select matchid, count(distinct reason) as distinct_reasons
from iceberg.crossscreen.nscreen_liveramp_throtle_ex_reason_staged
where day = '2026-09-01' and stage = 'lrth'
group by matchid
having count(distinct reason) > 1
-- (0 rows)
```

Corroborating from the other direction, `THEX` never labels a LiveRamp matchid: all 9,741,160 `THEX` rows at `stage = 'initial'` (844,609 distinct matchids) carry matchids absent from `liveramp_source`, while `LRTH` and `LRTHEX` matchids are present in it 100% of the time. Every `THEX` in production is correctly describing a Throtle-only lineage.

Worth recording because the protection is **structural, not enforced**: nothing in Job 2 asserts reason-homogeneity. Any future stage that emits two reasons under one matchid would activate the mislabel immediately, with no error. A cheap guard is the query above asserting 0 rows.

## D. Assignment loss in propagation

Families A–C all *duplicate* — one person ends up under several matchids. Family D is the only one that goes the other way: a UID that had a perfectly good candidate matchid ends up with **none**.

### D1. The per-matchid cap of ten binds hard

Propagation's last step caps how many new UIDs one matchid may absorb per round:

```sql
ranked_by_matchid = row_number() over (partition by matchid order by weight desc, uid desc)
...
where rnk <= 10
```

The per-matchid UID-count distribution in `stage1` for `2026-09-01` shows this is not a theoretical ceiling — the counts decay smoothly from 1 to 9 and then spike at exactly 10:

| UIDs absorbed | `stage1` matchids | `stage2` matchids |
| --- | --- | --- |
| 1 | 32,747,179 | 6,932,900 |
| 2 | 17,623,418 | 3,106,840 |
| 3 | 11,280,342 | 1,700,062 |
| 4 | 7,201,826 | 973,197 |
| 5 | 4,809,080 | 606,180 |
| 6 | 3,304,628 | 402,395 |
| 7 | 2,320,960 | 277,995 |
| 8 | 1,657,952 | 200,142 |
| 9 | 1,185,747 | 146,716 |
| **10** | **3,107,561** | **474,251** |

Extrapolating the 1→9 decay predicts ~0.85M matchids at 10; the observed 3.11M (3.6% of all `stage1` matchids) is a truncation pile-up. Those 3.11M matchids each had *more* than ten candidates and discarded the surplus.

### D2. The cap is applied after the per-UID winner is chosen

The surplus is not merely deferred — it can be lost outright, because of the order the two `row_number()` steps run in:

```sql
ranked_by_uid     = row_number() over (partition by uid     order by weight desc, matchid desc)  -- keep rnk = 1
ranked_by_matchid = row_number() over (partition by matchid order by weight desc, uid desc)      -- keep rnk <= 10
```

`ranked_by_uid` reduces each UID to its single highest-weight candidate matchid and **throws the rest away**. Only then does the per-matchid cap apply. So a UID whose top choice happens to be a popular matchid gets cut by `rnk <= 10` — and its other candidates, discarded one step earlier, are never reconsidered. It receives no matchid at all.

**Production instance** (day `2026-09-01`). UID `PC_f5e3caf2-3873-4ae3-b579-9f4e5f35693f` had two candidates:

| candidate matchid | weight | `rnk_by_uid` | UIDs it absorbed in `stage1` | outcome |
| --- | --- | --- | --- | --- |
| `-9200925499677856902` | 3.619048 | **1** | **10 — capped** | UID ranked 11th, cut |
| `-5765204961259389485` | 1.119048 | 2 | 2 — **8 slots free** | discarded before the cap ran |

The winning matchid's ten actual winners all had weight above 3.619048 (lowest 5.692857), so this UID was genuinely 11th in line. It appears in **zero** staged rows at any stage — no `stage1`, no `stage2`, no `louvain`. Meanwhile its second-choice matchid finished the round with eight unused slots. The UID was dropped while a home sat empty.

This is not a lone case: `I5_ID5-56a2sxwECdCgt5lsfAbi3z-dMPcebVTBRHhpG4mGOQ` shows the same pattern (top choice capped, alternative took 1 UID leaving 9 free, absent from all stages), as do `PC_9233d5aa-…`, `PC_7aed7f00-…` and `LT_7367c19d…`. On a non-random sample of 5,000 capped `stage1` matchids, 1,174 of the 125,402 candidate UIDs in their pools (~0.94%) appear in no stage at all. Scaling that to all 3.11M capped matchids suggests losses in the hundreds of thousands of UIDs per day — order of magnitude only, since candidate pools overlap and the sample was biased toward one matchid range.

Reordering the two steps (cap first, then let displaced UIDs fall through to their next-best candidate) would recover most of these, but that is a design change, not a bug fix — the current behaviour is what the SQL specifies.

### The four result stages are UID-disjoint

A natural worry, given no per-UID deduplication anywhere: can one UID be assigned by two *different* mechanisms — provider alignment and propagation, or propagation and Louvain — and so appear twice in the final result with unrelated matchids? **No.** The four stages the final result draws on are mutually exclusive by UID, and this is enforced structurally:

- `connected_ns` copies exactly those `initial` rows whose UID appears in `nscreen_ipcollocation_daily_clean`, and propagation's `filter_out_having_matchid` drops any candidate already in that seed set. Since propagation candidates are by definition edge endpoints, any `initial` UID that could be a candidate is already excluded.
- For `stage2`, the seed set is `stage = 'connected_ns'` **or** `stage > 'stage0' and stage < 'stage2'`, which picks up `stage1` — so `stage1` winners are excluded from `stage2`.
- The remainder step keeps an edge only when *neither* endpoint appears in `stage in ('initial','stage1','stage2')`, so Louvain can only assign UIDs none of the earlier stages touched.

Measured on a uniform 1% UID hash slice (exact within the slice, since equal UIDs hash to the same bucket) for `2026-09-01`:

```text
slice_initial_uids   77,028,850
slice_stage1_uids     2,459,016
slice_stage2_uids       371,549
slice_louvain_uids      443,533

initial_INT_stage1            0
initial_INT_stage2            0
initial_INT_louvain           0
```

and across the full (unsampled) small stages, `stage1 ∩ stage2`, `stage1 ∩ louvain` and `stage2 ∩ louvain` are all exactly **0**.

The consequence is a useful narrowing: since `stage1`, `stage2` and `louvain` are each exactly 1 row per UID, **every duplicate row in the final result originates in `initial`** — i.e. from family A vendor ambiguity, never from two mechanisms disagreeing. A UID with several rows always has several *vendor* claims behind it.

## Matchid cardinality after alignment

Alignment never creates a LiveRamp matchid and never merges one LiveRamp matchid into another — `lr_out` keeps `lr.matchid` unconditionally, so **every LiveRamp id in the source survives to the result verbatim**. The only lever alignment has on total cardinality is *reduction*: translating Throtle ids, and then Experian ids, into LiveRamp's namespace. Every rejected merge — a `count1` tie (B1), a `count2` collateral rejection (B2), an Experian tie (B4) or a plain non-mutual-best pairing — leaves that reduction undone.

```text
result cardinality =   all LiveRamp matchids
                     + unmerged Throtle matchids
                     + unmerged Experian matchids
                     + Louvain communities
```

Alignment therefore cannot inflate LiveRamp id cardinality; it *preserves* whatever fragmentation the vendors deliver. LiveRamp's own source-level ambiguity (9.26% of UIDs) is a floor no downstream step reduces, and each rejected merge is one missed consolidation — which is why the result's matchid space stays much larger than a fully-consolidated person count would be.

## Production observations (day 2026-09-01)

Per-stage row counts vs distinct-UID counts in the staged table:

| stage | rows | distinct uid | rows ÷ uid |
| --- | --- | --- | --- |
| initial | 8.33B | 7.70B | 1.08 |
| lrth | 6.14B | 5.51B | 1.11 |
| connected_ns | 351M | 282M | 1.24 |
| stage1 | 245.77M | 245.77M | 1.00 |
| stage2 | 37.19M | 37.19M | 1.00 |
| louvain | 44.37M | 44.37M | 1.00 |

`stage1`/`stage2`/`louvain` are exactly 1:1 by construction. The over-1 ratios in `initial`/`lrth`/`connected_ns` are the vendor ambiguities passing through: ~449.9M UIDs carry more than one matchid in the staged table, and ~449.2M UIDs carry more than one matchid in raw `liveramp_source` alone — LiveRamp accounts for nearly the entire effect, with Throtle's 4.6M a small addition.

A per-UID `distinct_matchid` histogram over the staged table ranges from 1 (≈94% of UIDs) up to the mid-teens for the worst UIDs; `distinct_stage` never exceeds 3 (the `lrth` → `initial` → `connected_ns` lineage), confirming the propagation stages' mutual exclusivity.

Note: a day's staged partition is written incrementally while the pipeline runs; querying the current day mid-run returns a moving target. Use a completed day for reproducible counts.

## Source files

| File | Role |
| --- | --- |
| [`NScreenLiverampThrotleOnlyStage.sql`](../../src/nscreen_graph/spark/sparksql/NScreenLiverampThrotleOnlyStage.sql) | Job 1: LiveRamp/Throtle alignment |
| [`NScreenLiverampThrotleExInitialStage.sql`](../../src/nscreen_graph/spark/sparksql/NScreenLiverampThrotleExInitialStage.sql) | Job 2: Experian alignment |
| [`NScreenLiverampThrotleExConnectedNsStage.sql`](../../src/nscreen_graph/spark/sparksql/NScreenLiverampThrotleExConnectedNsStage.sql) | Graph-connected seed selection |
| [`NScreenLiverampThrotleExNStage.sql`](../../src/nscreen_graph/spark/sparksql/NScreenLiverampThrotleExNStage.sql) | Propagation (stage1, stage2) |
| [`NScreenIpCollocationDailyExRemainder.sql`](../../src/nscreen_graph/spark/sparksql/NScreenIpCollocationDailyExRemainder.sql) | Unresolved-edge selection |
| [`NScreenExRemainderLouvainStage.sql`](../../src/nscreen_graph/spark/sparksql/NScreenExRemainderLouvainStage.sql) | Louvain clustering |
| [`NScreenLrThrotleExReasonResult.sql`](../../src/nscreen_graph/spark/sparksql/NScreenLrThrotleExReasonResult.sql) | Final result filter |
| [`NScreenLiverampSource.sql`](../../src/nscreen_graph/spark/sparksql/NScreenLiverampSource.sql) | LiveRamp source normalization (origin of LiveRamp-side ambiguity) |
| [`provider-alignment-toy.ipynb`](../../provider-alignment-toy.ipynb) | Executable replication of this page against toy tables |
| [`provider-alignment-defects.md`](provider-alignment-defects.md) | The two defects found while writing this page: the discarded `stage` literals and propagation's cap ordering (D2) |

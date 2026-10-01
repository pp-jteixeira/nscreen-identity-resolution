# Two Defects in the NScreen Graph Pipeline

Both were found while documenting provider alignment (see [`provider-alignment-phase.md`](provider-alignment-phase.md)). Every figure below was produced by running the stated query against production Trino on day `2026-09-01` — a completed day, since a day's partitions are written incrementally and querying the current day returns a moving target.

| # | Defect | Kind | Impact today |
| --- | --- | --- | --- |
| 1 | Job 1's `stage` literals are discarded at write time | Correctness of intent; maintainability hazard | No data loss. Behaviour is arguably *better* than the SQL specifies, but neither SQL file can be read at face value |
| 2 | Propagation's per-matchid cap is applied *after* per-UID winner selection | Data loss | UIDs are dropped from every stage while a viable alternative matchid sits unused |

---

## Defect 1 — Job 1's `stage` literals are silently discarded

### What the SQL says

[`NScreenLiverampThrotleOnlyStage.sql`](../../src/nscreen_graph/spark/sparksql/NScreenLiverampThrotleOnlyStage.sql) ends in a union that assigns two different stages, so it reads as though the job writes both:

```sql
select '{{ var('day') }}' as day, 'initial' as stage, uid, matchid, householdid, stable, reason
from lr_out                    -- LiveRamp-rooted rows
union all
select '{{ var('day') }}' as day, 'lrth' as stage, uid, matchid, householdid, stable, reason
from th_out                    -- Throtle-only leftovers
```

The intent is clear: LiveRamp-rooted rows go straight to `initial`, only Throtle leftovers park at `lrth`. Job 2 reads `stage = 'lrth'`, so under this reading Experian would never be compared against LiveRamp-rooted groups.

### What actually happens

[`common.py:49-51`](../../src/nscreen_graph/spark/common.py#L49-L51) overwrites every partition column with the literal supplied by the Luigi task, after the SQL has run:

```python
df = run_sql(query, spark)
for col_name, col_value in args.partition_columns:
    df = df.withColumn(col_name, F.lit(col_value))
df.writeTo(args.destination_table).overwritePartitions()
```

and Job 1's task supplies exactly one stage value ([`daily.py:295-300`](../../src/nscreen_graph/tasks/daily.py#L295-L300)):

```python
return Args(
    sql_file_name="NScreenLiverampThrotleOnlyStage.sql",
    destination_table="iceberg.crossscreen.nscreen_liveramp_throtle_ex_reason_staged",
    partition_columns=[("day", self.day), ("stage", "lrth")],
)
```

So the `'initial'` literal on `lr_out` is thrown away and **Job 1's entire output — LiveRamp-rooted rows included — lands in `stage = 'lrth'`**. Job 2 ([`daily.py:326-328`](../../src/nscreen_graph/tasks/daily.py#L326-L328)) passes `("stage", "initial")` and is the sole writer of `initial`.

The `stage` column in the SQL is dead code. The same is true of `day`, which is also a partition column, though there the literal happens to agree.

### Proof

```sql
select stage, reason, count(*) as rows
from iceberg.crossscreen.nscreen_liveramp_throtle_ex_reason_staged
where day = '2026-09-01' and stage in ('initial', 'lrth')
group by stage, reason
order by stage, rows desc
```

```text
  stage reason       rows
initial     LR 2686910306
initial   LREX 1597768916
initial     EX 1380675882
initial   LRTH 1118224917
initial LRTHEX 1072718517
initial     TH  462350504
initial   THEX    9741160
   lrth     LR 3761176262
   lrth   LRTH 1909957827
   lrth     TH  465082649
```

Two independent contradictions of the SQL's stated intent:

1. **`stage = 'lrth'` holds 3,761,176,262 rows with reason `LR`.** Reason `LR` is produced only by `lr_out`, whose rows the SQL labels `'initial'`. They are in `lrth`.
2. **Reason `LREX` exists, at 1,597,768,916 rows.** `LREX` can only be built by Job 2's `concat(lrth.reason, 'EX')` acting on a row whose reason was `LR`. That requires an `LR` row to be present in the `lrth` partition Job 2 reads. Under the SQL's intent this reason is unreachable.

The totals reconcile exactly, confirming the mechanism rather than some partial backfill:

| Quantity | Rows |
| --- | --- |
| `lrth` (all of Job 1's output) | 6,136,216,738 |
| `initial` (all of Job 2's output) | 8,328,390,202 |
| `initial` − `lrth` | 2,192,173,464 |

Job 2 rewrites every `lrth` row into `initial` and adds its Experian-only leftovers, so the difference is precisely `ex_out`'s contribution.

### Why it matters

- **Nobody can reason about these two SQL files correctly by reading them.** The doc for this phase asserted the opposite behaviour — that Experian is never compared against LiveRamp groups — and that claim survived review because it is exactly what the SQL says.
- **The current behaviour is probably the desirable one.** Experian gets compared against every group, not just Throtle leftovers, which yields 1.6B `LREX` rows worth of extra alignment. Changing the code to honour the SQL would *delete* that alignment.
- **`ex_only` semantics shift with it.** `ex_only` selects Experian rows whose UID is absent from `lrth`. Because `lrth` actually contains every LiveRamp and Throtle-only UID, far fewer Experian UIDs qualify than the SQL implies — Experian UIDs overlapping LiveRamp are absorbed into an existing group instead of getting their own `EX` row.
- **It is fragile in a dangerous direction.** Someone "tidying" `partition_columns`, or adding a second stage value, would silently and massively change output semantics with no error and no test failure.

### Suggested resolution

Pick one and make it explicit — the current state is the only option that is *not* self-documenting:

1. **Ratify current behaviour.** Delete the `stage` literals from the SQL (or replace them with a comment pointing at `partition_columns`), and rename the `lrth` stage to something honest like `job1_out`. Zero behaviour change.
2. **Honour the SQL.** Have `common.py` respect a `stage` column that the query already produced, writing to multiple partitions. This *reduces* alignment (drops `LREX`) and needs a deliberate product decision, not a refactor.

Option 1 is the low-risk fix. Either way, a test asserting the reason distribution — specifically that `LREX` is non-empty — would pin the intended behaviour down.

---

## Defect 2 — the propagation cap is applied after the per-UID winner is chosen

### The code

[`NScreenLiverampThrotleExNStage.sql`](../../src/nscreen_graph/spark/sparksql/NScreenLiverampThrotleExNStage.sql) (run twice, producing `stage1` then `stage2`) ends with two `row_number()` passes in this order:

```sql
ranked_by_uid as (
    select ..., row_number() over (partition by uid order by weight desc, matchid desc) as rnk
    from filter_out_having_matchid
),
filtered_by_uid_rnk as (
    select ... from ranked_by_uid where rnk = 1          -- (1) keep ONE candidate per UID
),
ranked_by_matchid as (
    select ..., row_number() over (partition by matchid order by weight desc, uid desc) as rnk
    from filtered_by_uid_rnk
)
select uid, matchid, householdid, stable, 'IC' as reason
from ranked_by_matchid
where rnk <= 10                                          -- (2) cap each matchid at 10 UIDs
```

Step (1) reduces each UID to its single highest-weight candidate matchid and discards the alternatives. Step (2) then caps each matchid at ten UIDs. A UID cut by the cap has already had its other candidates thrown away, and they are never reconsidered — so it receives **no matchid at all**, even when another candidate matchid had spare capacity in the very same round.

The two steps are independently reasonable; only their order causes the loss.

### Proof 1 — the cap binds, at scale

```sql
with per_matchid as (
    select stage, matchid, count(*) as n_uids
    from iceberg.crossscreen.nscreen_liveramp_throtle_ex_reason_staged
    where day = '2026-09-01' and stage in ('stage1', 'stage2')
    group by stage, matchid
)
select n_uids,
       sum(case when stage = 'stage1' then 1 else 0 end) as stage1_matchids,
       sum(case when stage = 'stage2' then 1 else 0 end) as stage2_matchids
from per_matchid
group by n_uids
order by n_uids
```

```text
 n_uids  stage1_matchids  stage2_matchids
      1         32747179          6932900
      2         17623418          3106840
      3         11280342          1700062
      4          7201826           973197
      5          4809080           606180
      6          3304628           402395
      7          2320960           277995
      8          1657952           200142
      9          1185747           146716
     10          3107561           474251
```

Counts decay smoothly from 1 to 9 and then jump at exactly 10. Extrapolating the decay predicts roughly 0.85M matchids at 10; the observed 3,107,561 (3.6% of all `stage1` matchids) is a truncation pile-up. Each of those matchids had more than ten candidates and discarded the surplus.

### Proof 2 — a UID lost while capacity sat unused

Take UID `PC_f5e3caf2-3873-4ae3-b579-9f4e5f35693f`.

**(a) It had two candidate matchids.** Reconstructing `grouped` → `ranked_by_uid` for this UID (edges doubled both directions, joined to the `connected_ns` seed set, `stable` candidates double-weighted exactly as the job does):

```sql
with target as (select 'PC_f5e3caf2-3873-4ae3-b579-9f4e5f35693f' as uid),
edges as (
    select c.uid1 as uid, c.uid2 as nbr, c.weight
    from iceberg.crossscreen.nscreen_ipcollocation_daily_clean c
    join target t on c.uid1 = t.uid
    where c.day = '2026-09-01'
    union all
    select c.uid2 as uid, c.uid1 as nbr, c.weight
    from iceberg.crossscreen.nscreen_ipcollocation_daily_clean c
    join target t on c.uid2 = t.uid
    where c.day = '2026-09-01'
),
cns as (
    select uid, matchid, stable
    from iceberg.crossscreen.nscreen_liveramp_throtle_ex_reason_staged
    where day = '2026-09-01' and stage = 'connected_ns'
),
cands as (
    select e.uid, c.matchid, c.stable,
           case when c.stable then sum(e.weight) * 2 else sum(e.weight) end as weight
    from edges e
    join cns c on e.nbr = c.uid
    group by e.uid, c.matchid, c.stable
)
select matchid, stable, weight,
       row_number() over (partition by uid order by weight desc, matchid desc) as rnk_by_uid
from cands
order by rnk_by_uid
```

```text
             matchid  stable   weight  rnk_by_uid
-9200925499677856902    True 3.619048           1
-5765204961259389485    True 1.119048           2
```

`ranked_by_uid` keeps only `-9200925499677856902`. The alternative `-5765204961259389485` is discarded here.

**(b) The chosen matchid was saturated, and the UID missed the cut.** Its ten `stage1` winners, with their weights toward that matchid recomputed the same way:

```sql
with winners as (
    select uid from iceberg.crossscreen.nscreen_liveramp_throtle_ex_reason_staged
    where day = '2026-09-01' and stage = 'stage1' and matchid = -9200925499677856902
),
edges as (
    select c.uid1 as uid, c.uid2 as nbr, c.weight
    from iceberg.crossscreen.nscreen_ipcollocation_daily_clean c
    join winners w on c.uid1 = w.uid
    where c.day = '2026-09-01'
    union all
    select c.uid2 as uid, c.uid1 as nbr, c.weight
    from iceberg.crossscreen.nscreen_ipcollocation_daily_clean c
    join winners w on c.uid2 = w.uid
    where c.day = '2026-09-01'
),
cns as (
    select uid, matchid, stable
    from iceberg.crossscreen.nscreen_liveramp_throtle_ex_reason_staged
    where day = '2026-09-01' and stage = 'connected_ns' and matchid = -9200925499677856902
)
select e.uid,
       case when c.stable then sum(e.weight) * 2 else sum(e.weight) end as weight_toward_M
from edges e
join cns c on e.nbr = c.uid
group by e.uid, c.stable
order by weight_toward_M
```

```text
                                                                uid  weight_toward_M
                  I5_ID5-36bfwF3fP21wuyNtTbgEbtBDzV5dI_r4VpX0uHNAQQ         5.692857
                                                FP_nrdEebrCRoz7A3K3         6.000000
                                                FP_TPJSHTCBxa_2sFEo         6.000000
                                                FP_nHD0hcOrvYC9CqCn         6.000000
LT_a4f782532a4cb4083715f3b76cbf185ca02c8a8e5b2773fa405a2408cf090c7d         6.157143
                  I5_ID5-78f4_foI2wOuvQF_aWB1kJUuJoZAYzTVWDBhxwZtgA         9.007143
LT_5050dff20f70d56981538b2274fa4945a7026a2e9269fa0c155e0c2ca5a4b664        14.352381
                                                       PxqI3zdS4FXt        16.633333
                            PC_55b2fa1d-dfe9-47b4-9a68-5728dab9b52c        17.161905
                  I5_ID5-e85dllZdAgkutGR3cwObp3Qh_y7HmRhSmZoSVuCJag        31.838095
```

Ten winners, the lowest at 5.692857 — all above our UID's 3.619048. It was genuinely 11th in line and cut by `rnk <= 10`.

**(c) It received nothing, and (d) its discarded alternative had room.**

```sql
select 'uid_rows_any_stage' as fact, cast(count(*) as varchar) as v
from iceberg.crossscreen.nscreen_liveramp_throtle_ex_reason_staged
where day = '2026-09-01' and uid = 'PC_f5e3caf2-3873-4ae3-b579-9f4e5f35693f'
union all
select 'stage1_uids_top_matchid', cast(count(*) as varchar)
from iceberg.crossscreen.nscreen_liveramp_throtle_ex_reason_staged
where day = '2026-09-01' and stage = 'stage1' and matchid = -9200925499677856902
union all
select 'stage1_uids_discarded_alt', cast(count(*) as varchar)
from iceberg.crossscreen.nscreen_liveramp_throtle_ex_reason_staged
where day = '2026-09-01' and stage = 'stage1' and matchid = -5765204961259389485
```

```text
                     fact  v
stage1_uids_top_matchid   10
stage1_uids_discarded_alt  2
       uid_rows_any_stage   0
```

The UID appears in **zero** staged rows at any stage — no `stage1`, no `stage2`, no `louvain` (it is excluded from the Louvain path too, since the remainder step only keeps edges where both endpoints are unassigned, and its neighbours are assigned). Meanwhile `-5765204961259389485`, the candidate discarded in step (1), finished the round having absorbed only 2 UIDs — **8 of its 10 slots unused**.

Summarised:

| candidate matchid | weight | `rnk_by_uid` | UIDs absorbed in `stage1` | outcome |
| --- | --- | --- | --- | --- |
| `-9200925499677856902` | 3.619048 | 1 | 10 — capped | UID ranked 11th, cut |
| `-5765204961259389485` | 1.119048 | 2 | 2 — 8 slots free | discarded before the cap ran |

### Scale

Other UIDs showing the identical pattern: `I5_ID5-56a2sxwECdCgt5lsfAbi3z-dMPcebVTBRHhpG4mGOQ` (top choice capped; alternative absorbed 1 UID, 9 slots free; absent from all stages), plus `PC_9233d5aa-…`, `PC_7aed7f00-…` and `LT_7367c19d…`.

**Estimated volume — approximate, and the weakest number here.** Over a non-random sample of 5,000 capped `stage1` matchids (`order by matchid limit 5000`), their candidate pools held 125,402 distinct UIDs, of which 1,174 (~0.94%) appear in no stage at all. Naively scaling to all 3,107,561 capped matchids suggests losses in the hundreds of thousands of UIDs per day, but treat that as an order of magnitude only: candidate pools overlap, and the sample is biased toward one end of the matchid range. A proper measurement would reconstruct candidates across the full edge set.

### Suggested resolution

Apply the cap *before* collapsing each UID to one candidate, so a UID displaced from a saturated matchid can fall through to its next-best option — e.g. rank by matchid first, drop over-cap `(uid, matchid)` pairs, then pick each UID's best *surviving* candidate. Iterating to a fixed point would be strictly better still, at more cost.

Note this is a behaviour change, not a pure bug fix: it increases how many UIDs propagation assigns, and matchids currently at the cap would absorb a different set of UIDs. It needs the same scrutiny as any change to graph density — worth confirming the cap's original purpose (runaway-cluster protection, most likely) is still served.

---

## Reproducing

All queries above run read-only against production Trino and are safe to re-run. Day `2026-09-01` is used throughout; substitute any completed day. Tables involved, all in `iceberg.crossscreen`:

| Table | Role |
| --- | --- |
| `nscreen_liveramp_throtle_ex_reason_staged` | Staged output, partitioned by `day` + `stage` |
| `nscreen_ipcollocation_daily_clean` | IP-collocation edges, one row per undirected edge |
| `throtle_source`, `liveramp_source`, `experian_source` | Vendor sources |

`matchid` is a `bigint`; quoting a matchid literal in Trino fails with `TYPE_MISMATCH`.

# Provider Source Multi-Assignment Resolution

## Status

This document proposes source-normalization changes. No production change described here has been implemented.

## Scope

This plan covers cases where one provider assigns several matchids to one UID on one processing day.

Examples:

- `v6` carries Throtle matchids `T3`, `T4`, and `T5`.
- `v13` carries LiveRamp matchids `L2` and `L3`.

Collocation-based reconciliation between already-assigned matchid groups is separate.

## Hard requirements

```text
every valid input UID remains
every provider source emits one matchid per UID
every published UID receives one matchid
```

No ambiguous UID may be dropped, quarantined, or omitted merely because one provider supplied several claims.

Here, valid means the UID passes existing final-result UID filters and carries a nonzero matchid.

## Current behavior

`NScreenLiverampSource.sql` groups by `(uid, ramp_id)`. Every Ramp ID survives when one UID has several Ramp IDs.

`NScreenThrotleSource.sql` emits every `(uid, throtleid)` association. Every Throtle ID survives when one UID has several Throtle IDs.

Experian currently produces one matchid per UID in measured production data, so no Experian change is proposed.

Provider alignment processes surviving rows independently. It never selects one claim per UID, so source ambiguity reaches the final result.

## Minimal solution

Select one deterministic provider claim per ordinary UID during source normalization. Preserve synthetic provider-anchor UIDs separately.

This solution guarantees row uniqueness and UID retention. It does not prove that the selected provider claim is semantically correct.

### LiveRamp rule

1. Collapse duplicate `(uid, ramp_id)` pairs.
2. Rank candidates per UID.
3. Prefer stable Ramp IDs where `ramp_id like 'XY%'`.
4. Break remaining ties using raw `ramp_id asc`.
5. Keep `row_number() = 1`.
6. Generate every `LR_<ramp_id>` anchor from the unfiltered Ramp-ID set.

Conceptual ranking:

```sql
row_number() over (
    partition by uid
    order by
        case when ramp_id like 'XY%' then 0 else 1 end,
        ramp_id
) as claim_rank
```

### Throtle rule

1. Collapse duplicate `(uid, throtleid)` pairs.
2. Rank candidates per UID.
3. Break ties using raw `throtleid asc`.
4. Keep `row_number() = 1`.
5. Generate every `TH_<throtleid>` anchor from the unfiltered Throtle-ID set.

Conceptual ranking:

```sql
row_number() over (
    partition by uid
    order by throtleid
) as claim_rank
```

Raw provider identifiers should determine fallback order. Ordering hashed matchids would obscure behavior and could change after hashing changes.

## Why source selection uses `row_number()`

Current provider-alignment SQL uses `rank()` for a different decision:

- `NScreenLiverampThrotleOnlyStage.sql` ranks LiveRamp-Throtle matchid-pair overlap in both directions.
- `NScreenLiverampThrotleExInitialStage.sql` ranks Experian-aligned matchid-pair overlap in both directions.

Those jobs order candidates only by shared-UID count. Equal counts intentionally receive the same rank:

```sql
rank() over (
    partition by matchid
    order by cnt desc
)
```

Every equally supported candidate therefore receives `rank = 1`. Later `count1 = 1 and count2 = 1` checks reject the whole tie instead of selecting one mapping. That behavior protects provider-group alignment from arbitrary tie-breaking.

Source normalization has a different requirement. Every valid UID must remain, and exactly one provider claim must survive. Rejecting every tie would drop ambiguous UIDs; preserving every rank-one tie would keep the multi-assignment defect.

The source plan therefore changes the decision model:

| Context | Window function | Tie behavior | Required outcome |
| --- | --- | --- | --- |
| Existing provider alignment | `rank()` | Preserve equal winners, then reject tied mappings | Avoid unsupported group merges |
| Proposed source normalization | `row_number()` | Select exactly one ordered candidate | Retain every UID once |

`row_number()` must use a total deterministic order. LiveRamp uses stable-ID preference followed by raw `ramp_id`; Throtle uses raw `throtleid`. Distinct provider IDs therefore receive distinct positions even when every quality signal ties.

For example:

```text
v6:  T3 -> 1, T4 -> 2, T5 -> 3
v13: L2 -> 1, L3 -> 2
```

Only position `1` survives. Both UIDs remain.

Using `rank()` with the same complete ordering would normally produce the same winner because raw provider ID breaks every tie. `row_number()` remains preferable because it directly guarantees one row, documents the source invariant, and remains safe if future candidate data contains unexpected duplicates. Duplicate `(uid, provider_id)` pairs should still be collapsed before ranking.

Existing `row_number()` inside `NScreenThrotleSource.sql` does not already solve this problem. It partitions by `throtleid`, not by `uid`, and exists only to emit one synthetic `TH_<throtleid>` anchor per Throtle group.

## Expected toy behavior

| UID | Source candidates | Selected claim | UID retained |
| --- | --- | --- | --- |
| `v6` | `T3`, `T4`, `T5` | `T3` | Yes |
| `v13` | `L2`, `L3` | `L2` | Yes |

These winners follow deterministic fallback ordering. They do not represent measured identity quality.

## Files requiring changes

| File | Change |
| --- | --- |
| `src/nscreen_graph/spark/sparksql/NScreenLiverampSource.sql` | Rank Ramp IDs per ordinary UID; keep one; preserve every synthetic Ramp-ID anchor. |
| `src/nscreen_graph/spark/sparksql/NScreenThrotleSource.sql` | Rank Throtle IDs per ordinary UID; keep one; preserve every synthetic Throtle-ID anchor. |

No provider-alignment, propagation, remainder, Louvain, or final-result SQL change is required for this narrow fix.

## Why downstream uniqueness follows

After source normalization:

1. each LiveRamp UID has one matchid;
2. each Throtle UID has one matchid;
3. each Experian UID has one matchid;
4. LiveRamp-Throtle alignment emits LiveRamp rows plus Throtle-only UIDs;
5. Experian alignment emits aligned rows plus Experian-only UIDs;
6. propagation selects one candidate per new UID;
7. remainder clustering emits one assignment per remaining UID.

Therefore provider-source ambiguity can no longer create several final rows for one UID.

## Coverage safeguards

Synthetic anchors must use unfiltered provider groups. Filtering before anchor generation could delete provider matchids whose only ordinary members were ambiguous.

Validate ordinary UID retention separately from synthetic anchors:

```sql
-- LiveRamp ordinary UIDs must remain.
select count(distinct uid)
from iceberg.liveramp.ramp_id_mapping_flat
where day = '{{ source_day }}'
  and length(ramp_id) > 20
  and length(uid) > 11
  and length(uid) < 40
  and translate(uid, '01-_!*', '') != '';

select count(distinct uid)
from iceberg.crossscreen.liveramp_source
where day = '{{ day }}'
  and uid not rlike '^LR_.*$';
```

Equivalent input-output coverage checks are required for Throtle.

## Required assertions

```sql
-- Each source check must return zero rows.
select uid, count(distinct matchid) as matchid_count
from iceberg.crossscreen.liveramp_source
where day = '{{ day }}' and uid not rlike '^LR_.*$'
group by uid
having count(distinct matchid) <> 1;

select uid, count(distinct matchid) as matchid_count
from iceberg.crossscreen.throtle_source
where day = '{{ day }}' and uid not rlike '^TH_.*$'
group by uid
having count(distinct matchid) <> 1;

-- Final check must return zero rows.
select uid, count(distinct matchid) as matchid_count
from iceberg.crossscreen.nscreen_lr_throtle_ex_reason_result
where day = '{{ day }}'
group by uid
having count(distinct matchid) <> 1;

-- Coverage check must return zero rows.
with expected as (
    select distinct uid
    from iceberg.crossscreen.nscreen_liveramp_throtle_ex_reason_staged
    where day = '{{ day }}'
      and stage = 'initial'
      and matchid <> 0
      and uid not rlike '^[01\\-_\\!\\*]*$'
),
published as (
    select distinct uid
    from iceberg.crossscreen.nscreen_lr_throtle_ex_reason_result
    where day = '{{ day }}'
)
select e.uid
from expected as e
left anti join published as p on e.uid = p.uid;
```

Also assert input and output ordinary UID counts match for each modified provider source.

## Limitations

- Deterministic fallback is not identity evidence.
- Source timestamps or provider confidence could improve selection later.
- Synthetic anchors preserve every provider matchid, so this change may not reduce distinct matchid cardinality.
- This change resolves duplicate UID assignments only.

## Acceptance criteria

1. Every valid ordinary provider UID remains.
2. Every modified provider source emits one matchid per ordinary UID.
3. Every synthetic provider anchor remains.
4. `v6` retains one Throtle assignment.
5. `v13` retains one LiveRamp assignment.
6. No UID is quarantined or dropped.
7. Every valid provider UID reaches final output exactly once.
8. Selected winners remain deterministic across reruns.

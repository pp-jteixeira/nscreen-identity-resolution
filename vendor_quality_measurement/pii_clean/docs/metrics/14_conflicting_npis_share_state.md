# Conflicting NPIs share a state

**Question:** does this link share a recognized state with another NPI in its conflict context? Geographic agreement does not establish email ownership.

**Where:** `conflicting_npis_share_state` in `iceberg.jteixeira_ipa.pii__int_<vendor>__metrics` and `iceberg.jteixeira_ipa.pii_clean`; one row per source/email/NPI link, key: `source`, `link_id`.

## How it is computed

Trim and uppercase vendor state values; normalize internal spaces. Map recognized US state names/codes, DC and five territories to two-letter codes. Missing or unrecognized values produce an empty `source_state_values` array. Explicit foreign countries in Medscape/RocketReach are excluded; absent country information permits recognized states.

Inputs: QuantumMedica/Medscape/DRDB `state`, Endato’s returned `address_state`, RocketReach `region`, and HealthLink HCP `state` joined by NPI across retained history without date alignment. Haymarket has no state field. Provider-input and registry addresses never fill missing states.

A link can hold several versions of a source record. `source_state_values` is the union of recognized states across all versions of the link, and the peer comparison uses that union for both the link and each peer link. This metric has no `_latest` form.

Compare only other NPIs for the same vendor/email on overlapping `conflict_days`. Endato, RocketReach and both DRDB feeds use their undated vendor snapshot, so every other NPI of the email is a peer. Never infer overlap from date bounds.

For each applicable peer:

```sql
CASE WHEN cardinality(source_state_values) > 0 AND cardinality(peer.states) > 0
     THEN arrays_overlap(source_state_values, peer.states)
END AS shares_state
```

For established conflicts:

```sql
any_match(conflicting_npi_state_comparisons, p -> p.shares_state) AS conflicting_npis_share_state
```

Any true peer gives true; all known mismatches give false. Otherwise the result is null. Without an established conflict, null means not applicable (`has_conflict_linkage = false`) or unknown timing (that flag is null).

`conflicting_npi_state_comparisons` retains peer NPIs, states, overlapping days and outcomes for [full inspection](../../sql/conflicting_states_debug.sql). A match may coexist with disagreeing peers. Each link remains a separate row.

## Real examples

No executed examples exist yet for this definition.

**What differentiates outcomes:** A known shared value gives true; known disjoint evidence gives false. With an established conflict, missing evidence leaves NULL. Without a conflict, NULL is not applicable. Recognized states can agree or differ, while empty state evidence remains unknown. Geographic agreement is not identity proof.

## Statistics by source

No measurements exist yet for this definition.

[Statistics SQL](../../sql/statistics/14_conflicting_npis_share_state.sql)

Percentages use links with `has_conflict_linkage = true`, not all links. A zero conflict denominator is shown as —. Links without an established conflict are not counted as unknown conflicts.

# Conflicting NPIs share a state

**Question:** does this record share a recognized state with another NPI in its conflict context? Geographic agreement does not establish email ownership.

**Where:** `conflicting_npis_share_state` in `iceberg.jteixeira_ipa.pii__int_<vendor>__metrics` and `iceberg.jteixeira_ipa.pii_clean`; key: `source`, `metric_row_id`.

## How it is computed

Trim and uppercase vendor state values; normalize internal spaces. Map recognized US state names/codes, DC and five territories to two-letter codes. Missing or unrecognized values produce an empty `source_state_values` array. Explicit foreign countries in Medscape/RocketReach are excluded; absent country information permits recognized states.

Inputs: QuantumMedica/Medscape/DRDB `state`, Endato’s returned `address_state`, RocketReach `region`, and HealthLink HCP `state` joined by NPI across retained history without date alignment. Haymarket has no state field. Provider-input and registry addresses never fill missing states.

Compare only other NPIs for the same vendor/email on overlapping `conflict_days`. Endato, RocketReach and both DRDB feeds use their current vendor snapshot. Never infer overlap from date bounds.

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

**Illustrative examples** (different NPIs, same conflict context):

| This record | Peer state | Result |
|---|---|---|
| NY | New York | true |
| NY | CA | false |
| NY | Missing or XX | unknown |

`conflicting_npi_state_comparisons` retains peer NPIs, states, overlapping days and outcomes for [full inspection](../../sql/conflicting_states_debug.sql). A match may coexist with disagreeing peers. Existing rows remain separate.

## Statistics by vendor

[Statistics SQL](../../sql/statistics/14_conflicting_npis_share_state.sql). This file preserves the executed read-only SQL behind these statistics, including the original measurement relation. Re-running it requires that relation and reference inputs; changing sources will change the results.

Measured **October 29, 2026**, on `iceberg.jteixeira_ipa.pii_clean`. Extraction: `2026-10-29T10:21:38.979875+00:00`. Exact counts. State availability percentages use all vendor rows; outcome percentages use that vendor’s conflict rows.

| Vendor | Usable-state rows, n (%) | Conflict rows | Shared state, n (%) | Different states, n (%) | Unknown states, n (%) |
|---|---:|---:|---:|---:|---:|
| HealthLink | 11,011,113 (98.70%) | 0 | 0 (—) | 0 (—) | 0 (—) |
| QuantumMedica | 0 (0.00%) | 56 | 0 (0.00%) | 0 (0.00%) | 56 (100.00%) |
| Medscape | 46,192,862 (98.13%) | 46 | 32 (69.57%) | 4 (8.70%) | 10 (21.74%) |
| Endato | 5,425,749 (99.97%) | 194,982 | 153,206 (78.57%) | 41,690 (21.38%) | 86 (0.04%) |
| RocketReach | 4,206,864 (86.49%) | 96,287 | 53,925 (56.00%) | 20,533 (21.32%) | 21,829 (22.67%) |
| DRDB | 1,115,412 (100.00%) | 22,404 | 15,850 (70.75%) | 6,552 (29.24%) | 2 (0.01%) |
| Haymarket | 0 (0.00%) | 0 | 0 (—) | 0 (—) | 0 (—) |

QuantumMedica’s raw states contain only missing/placeholder values and one `state` header value; none normalize to a recognized state.

— means no conflict rows. Missing states are unknown, not geographic disagreement. The union retains 75,564,265 metric rows; 75,250,490 have no conflict and 0 have unknown conflict timing.

Counts and SQL (local-only: `../../results/conflicting_states_measurements.json`) · Native fixtures and field preservation (local-only: `../../results/conflicting_states_native_validation.json`) · Final publication checks (local-only: `../../results/final_build.json`)

[Normalization](../../macros/state_consistency.sql) · [Comparison](../../macros/name_consistency.sql) · [Independent check](../../tests/conflicting_states.sql) · [Profile SQL](../../sql/conflicting_states_profile.sql)

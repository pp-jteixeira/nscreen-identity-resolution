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

`conflicting_npi_state_comparisons` retains peer NPIs, states, overlapping days and outcomes for [full inspection](../../sql/conflicting_states_debug.sql). A match may coexist with disagreeing peers. Existing rows remain separate.

## Real examples: contrasting outcomes

Selected real records, queried October 30, 2026, from `iceberg.jteixeira_ipa.pii_clean` at snapshot `8096642935433856886`. These examples explain outcomes; they are not prevalence estimates. Conflict examples are selected with exactly one peer comparison, so the displayed peer fully explains the aggregate outcome. Undated Endato comparisons use the available vendor snapshot.

[Runnable example SQL](../../sql/examples/14_conflicting_npis_share_state.sql):

```sql
WITH selected AS (
    SELECT *
    FROM iceberg.jteixeira_ipa.pii_clean FOR VERSION AS OF 8096642935433856886
    WHERE (source = 'endato' AND metric_row_id IN (
        '5A4F2A12631E80536E669103B3F317D42F2765161DD8DB94B5E0529DDDC5D98F',
        '5FBC85C91EE6BCD4497632464719C42645215081E9552AEFC2644F672A8CCD9F',
        'D13284F7A914B72A2E7C30495579F5B20C45368C0F2ACD40BBE0A10DFADB3DE1'))
       OR (source = 'haymarket' AND metric_row_id IN (
        '9DF2E9F9E7A4ECB5EE6C33558A69F6F91B5222D322F1CDB70BE08D0EE1FB82DC'))
)
SELECT m.source,
       m.npi,
       (element_at(m.conflicting_npi_state_comparisons, 1)).npi AS peer_npi,
       m.source_state_values AS own_values,
       (element_at(m.conflicting_npi_state_comparisons, 1)).states AS peer_values,
       m.has_conflict_linkage AS conflict,
       m.conflicting_npis_share_state AS shares_state
FROM selected m
ORDER BY m.source, m.metric_row_id
```

**Result:** 4 rows.

| source | npi | peer_npi | own_values | peer_values | conflict | shares_state |
|---|---|---|---|---|---|---|
| endato | 1518387349 | 1790171247 | [AL] | [AL] | true | true |
| endato | 1205912391 | 1891105805 | [PA] | [GA] | true | false |
| endato | 1003046194 | 1275624934 | [] | [LA] | true | NULL |
| haymarket | 1962472621 | NULL | [] | NULL | false | NULL |

**What differentiates these cases:** A known shared value gives true; known disjoint evidence gives false. With an established conflict, missing evidence leaves NULL. Without a conflict, NULL is not applicable. Recognized states can agree or differ, while empty state evidence remains unknown. Geographic agreement is not identity proof.

Stored indicators are unchanged by display helpers. Reproduction requires the pinned snapshot to remain available.

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

Counts and SQL (historical output, not retained: `../../results/conflicting_states_measurements.json`) · Native fixtures and field preservation (historical output, not retained: `../../results/conflicting_states_native_validation.json`) · Final publication checks (historical output, not retained: `../../results/final_build.json`)

[Normalization](../../macros/state_consistency.sql) · [Comparison](../../macros/name_consistency.sql) · [Independent check](../../tests/conflicting_states.sql) · [Profile SQL](../../sql/conflicting_states_profile.sql)

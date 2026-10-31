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

## Real examples

Executed October 31, 2026, against canonical snapshot `8811920360682490090`. These selected cases explain outcomes; they do not measure prevalence.

[Executed example SQL](../../sql/examples/14_conflicting_npis_share_state.sql):

```sql
WITH selected AS (
    SELECT *
    FROM iceberg.jteixeira_ipa.pii_clean FOR VERSION AS OF 8811920360682490090
    WHERE (source = 'endato' AND metric_row_id IN (
        '5A4F2A12631E80536E669103B3F317D42F2765161DD8DB94B5E0529DDDC5D98F',
        '5FBC85C91EE6BCD4497632464719C42645215081E9552AEFC2644F672A8CCD9F',
        'D13284F7A914B72A2E7C30495579F5B20C45368C0F2ACD40BBE0A10DFADB3DE1'))
       OR (source = 'haymarket' AND metric_row_id IN (
        '9DF2E9F9E7A4ECB5EE6C33558A69F6F91B5222D322F1CDB70BE08D0EE1FB82DC'))
)
SELECT m.source,
       m.email,
       m.npi,
       (element_at(m.conflicting_npi_state_comparisons, 1)).npi AS peer_npi,
       m.source_state_values AS own_values,
       (element_at(m.conflicting_npi_state_comparisons, 1)).states AS peer_values,
       m.has_conflict_linkage AS conflict,
       m.conflicting_npis_share_state AS shares_state
FROM selected m
ORDER BY m.source, m.metric_row_id
```

| source | email | npi | peer_npi | own_values | peer_values | conflict | shares_state |
|---|---|---|---|---|---|---|---|
| endato | evapg052@yahoo.com | 1518387349 | 1790171247 | [AL] | [AL] | true | true |
| endato | aahand@hotmail.com | 1205912391 | 1891105805 | [PA] | [GA] | true | false |
| endato | kathleen.molinar@yahoo.com | 1003046194 | 1275624934 | [] | [LA] | true | NULL |
| haymarket | amaslo@yahoo.com | 1962472621 | NULL | [] | NULL | false | NULL |

**What differentiates these cases:** A known shared value gives true; known disjoint evidence gives false. With an established conflict, missing evidence leaves NULL. Without a conflict, NULL is not applicable. Recognized states can agree or differ, while empty state evidence remains unknown. Geographic agreement is not identity proof.

## Statistics by source

Measured **October 31, 2026** from `iceberg.jteixeira_ipa.pii_clean` snapshot `8811920360682490090`. These are exact published-population counts across retained eligible history, not a sample. Stored evaluation dates remain unchanged.

[Executed statistics SQL](../../sql/statistics/14_conflicting_npis_share_state.sql)

| Source | Conflict records | Shared, n (%) | Disjoint, n (%) | Unknown, n (%) |
|---|---|---|---|---|
| HealthLink | 0 | 0 (—) | 0 (—) | 0 (—) |
| QuantumMedica | 56 | 0 (0.000000%) | 0 (0.000000%) | 56 (100.000000%) |
| Medscape | 46 | 32 (69.565217%) | 4 (8.695652%) | 10 (21.739130%) |
| Endato | 194,982 | 153,206 (78.574433%) | 41,690 (21.381461%) | 86 (0.044107%) |
| RocketReach | 96,287 | 53,925 (56.004445%) | 20,533 (21.324789%) | 21,829 (22.670766%) |
| DRDB | 22,404 | 15,850 (70.746295%) | 6,552 (29.244778%) | 2 (0.008927%) |
| Haymarket | 0 | 0 (—) | 0 (—) | 0 (—) |

Percentages use records with `has_conflict_linkage = true`, not all records. A zero conflict denominator is shown as —. Records without an established conflict are not counted as unknown conflicts.

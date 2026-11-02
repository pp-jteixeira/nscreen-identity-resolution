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

Executed November 2, 2026, against `iceberg.jteixeira_ipa.pii_clean` snapshot `2837737034249693554`. These selected cases explain outcomes; they do not measure prevalence.

```sql
SELECT source, email, npi, record_count, source_state_values,
       transform(conflicting_npi_state_comparisons, p -> p.npi || ': ' || array_join(p.states, ', ')) AS peer_states,
       has_conflict_linkage, conflicting_npis_share_state
FROM iceberg.jteixeira_ipa.pii_clean
WHERE (source = 'endato' AND link_id IN ('0000D99684BF16BE7602BA1F9A425F5BAC8E6AC57A0EA41D47F76C41805EA27A', '0001C709726BB99DFFA4AE0200D2B2F8D4508BAFA94D2706F32A7FB6552D2C2E', '0725CC19D8FF73C6A2EB1D3838B6AC6D3475E5991A0BEB1A686A438FE2588216'))
   OR (source = 'medscape' AND link_id IN ('4C7468EBC1D99D7914693F0F05ED57FF0F55BDBF5DC6277B2801FC795FED5D19', '4AC7E03D58C982D74C164A9AB653C77BA18CCA102D3AA4D7565653E26E421889'))
   OR (source = 'quantummedica' AND link_id IN ('B1BF32E78A2E6EDF12ACF41194D025D4BBF1C4828370D72D4E42629AD83095BB'))
   OR (source = 'healthlink' AND link_id IN ('011A4E3469D63171B176507DBDB51E1A4A7FE27976A32920F81AB683684A4A21'))
ORDER BY source, link_id
```

| source | email | npi | record_count | source_state_values | peer_states | has_conflict_linkage | conflicting_npis_share_state |
|---|---|---|---|---|---|---|---|
| endato | ppaulaj7i20@verizon.net | 1871569921 | 1 | ['NH'] | ['1265075410: NH'] | true | true |
| endato | jessgene045@gmail.com | 1326082884 | 1 | ['MD'] | ['1770928194: NY'] | true | false |
| endato | clovestoo@gmail.com | 1770663965 | 1 | [] | ['1700412863: CA'] | true | NULL |
| healthlink | kchuang@memorialcare.org | 1205998929 | 1 | ['CA'] | [] | false | NULL |
| medscape | andrewsj2@gmail.com | 1548321714 | 1 | ['PA'] | ['1134484942: PA'] | true | true |
| medscape | pawnking4@netscape.net | 1033420419 | 2 | ['NJ', 'RI'] | ['1861566606: MA'] | true | false |
| quantummedica | aroman@prongersmith.com | 1174520019 | 1 | [] | ['1659335578: '] | true | NULL |

**What differentiates these cases:**

- **Shared state (true):** the Endato link for `ppaulaj7i20@verizon.net` and its peer both report NH. The Medscape link for `andrewsj2@gmail.com` and its peer both report PA on the conflict days.
- **Known disjoint states (false):** the Endato link for `jessgene045@gmail.com` reports MD and its peer reports NY. The Medscape link for `pawnking4@netscape.net` merges 2 versions, so its state set is the union NJ and RI, which does not overlap the peer's MA.
- **Missing evidence (NULL, unknown):** the Endato link for `clovestoo@gmail.com` has no recognized state although its peer reports CA. The QuantumMedica link for `aroman@prongersmith.com` has no recognized state, and neither does its peer.
- **No conflict (NULL, not applicable):** the HealthLink link for `kchuang@memorialcare.org` has the state CA but no conflict, so the metric does not apply. Geographic agreement is not identity proof.

## Statistics by source

Measured **November 2, 2026** from `iceberg.jteixeira_ipa.pii_clean` snapshot `2837737034249693554`. These are exact published-population counts across retained eligible history, not a sample. Source data period (first to last observed day): HealthLink 2026-01-07 to 2026-10-03, QuantumMedica 2025-09-14 to 2026-10-15, Medscape 2024-01-10 to 2026-11-01 and Haymarket 2021-07-06 (a single day). Endato, RocketReach and DRDB are undated.

[Statistics SQL](../../sql/statistics/14_conflicting_npis_share_state.sql)

| Source | Links | With a recognized state, n (% of links) | Conflict links, n (% of links) | Shares a state, n (% of conflict links) | Different states, n (% of conflict links) | Unknown, n (% of conflict links) |
|---|---|---|---|---|---|---|
| HealthLink | 7,688,451 | 7,577,592 (98.558110%) | 0 (0.000000%) | 0 (undefined) | 0 (undefined) | 0 (undefined) |
| QuantumMedica | 1,705,723 | 0 (0.000000%) | 56 (0.003283%) | 0 (0.000000%) | 0 (0.000000%) | 56 (100.000000%) |
| Medscape | 3,661,537 | 3,463,669 (94.596040%) | 32 (0.000874%) | 20 (62.500000%) | 4 (12.500000%) | 8 (25.000000%) |
| Endato | 5,427,459 | 5,425,749 (99.968494%) | 194,982 (3.592510%) | 153,206 (78.574433%) | 41,690 (21.381461%) | 86 (0.044107%) |
| RocketReach | 3,199,535 | 2,803,749 (87.629890%) | 65,846 (2.057987%) | 39,045 (59.297452%) | 14,179 (21.533578%) | 12,622 (19.168970%) |
| DRDB | 826,886 | 826,883 (99.999637%) | 14,832 (1.793718%) | 10,549 (71.123247%) | 4,281 (28.863269%) | 2 (0.013484%) |
| Haymarket | 4,223,245 | 0 (0.000000%) | 0 (0.000000%) | 0 (undefined) | 0 (undefined) | 0 (undefined) |

Percentages of shared, different and unknown outcomes use links with `has_conflict_linkage = true`, not all links. A zero conflict denominator gives an undefined percentage. Links without an established conflict are not counted as unknown conflicts. No link has unknown conflict timing.

Haymarket has no state field, and QuantumMedica has no recognized state on any link, so all 56 QuantumMedica conflict links are unknown. Among the sources with conflicts, Endato (78.574433%) and DRDB (71.123247%) most often share a state, and RocketReach has the largest unknown share (19.168970%) because 12.370110% of its links lack a recognized state.

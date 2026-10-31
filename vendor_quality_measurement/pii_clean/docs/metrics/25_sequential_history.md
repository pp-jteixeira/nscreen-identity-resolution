# 25. Sequential attribution history

Sequential history describes changes in one vendor’s reported NPI set for an email. It does not establish ownership or whether a change was a correction. These metrics are published across all seven sources in the complete October 31, 2026 table, snapshot `8811920360682490090`. Native core integrity and final preservation checks passed. See [build evidence](../build_recovery.md).

## How it is computed

The [macro](../../macros/sequential_history.sql) reads eligible `metric_records` inside each `int_<vendor>__metrics` model. Medscape cumulative NPI opt-outs apply first. Distinct `source/email/npi/observed_day` observations eliminate repeated raw rows and email positions. Only dates through `sequence_as_of_day` participate. The default cutoff is Europe/Paris today.

Each email's NPI set is compared with its previous observed set. Missing calendar days add no transitions. Both additions and removals are required for a swap. A flip-back is a swap adding an NPI seen on any earlier observed day. Count transitions, not individual NPIs. Initial observations add no change.

```sql
count_if(is_swap) OVER w AS swaps,
count_if(is_swap AND cardinality(returned_npis) > 0) OVER w AS flipbacks
```

`w` runs from the first observed email day through the current day, within one source/email. `returned_npis` intersects added NPIs with previously seen NPIs. `sequence_daily_evidence` stores ordered sets, additions, removals, returns and cumulative counts. No daily entry reads future NPI observations.

HealthLink and QuantumMedica collapse consecutive equal delivery-content fingerprints, computed with Trino `checksum` over distinct email/NPI pairs. A later return to earlier content is a new version. Fingerprints have a theoretical collision risk. Medscape uses delivered days. Haymarket has one dated snapshot. Endato, RocketReach and DRDB have no usable dated history.

## Outputs and examples

Stored summaries are `n_versions_observed`, `n_npis_window`, `n_npi_changes`, `n_swaps` and `n_flipbacks`. Despite its compatibility name, `n_npis_window` covers all retained dated history through the cutoff, without a rolling window. These source/email summaries repeat on original metric rows, preserving exact-record grain.

Illustrative sequence: `{n1} → {n2,n3} → {n1,n2}` produces cumulative swaps `0,1,2` and flip-backs `0,0,1`. The final totals are three versions, three NPIs and two changes. Adding an NPI without removing another is not a swap.

`stability_history_sufficient` requires at least `sequence_min_versions` observations, default three. Missing history gives NULL counts, false sufficiency and empty evidence. Mixed dates retain qualified known-date counts with `sequence_has_undated_observations`. `sequence_history_status` and `sequence_definition_version` identify availability and rules. Sufficiency describes history volume, not independent confirmations.

## Real stored example: HealthLink

Native Trino queried complete canonical snapshot `8811920360682490090` on October 31, 2026. The [standalone stored-field query](../../sql/examples/25_sequential_history_published.sql) returns:

| Source | Email | Metric rows | Retained NPIs | Versions | Dated NPIs | Changes | Swaps | Flip-backs | Sufficient history |
|---|---|---:|---|---:|---:|---:|---:|---:|---|
| healthlink | jjacobson@mchswecare.com | 3 | [1366933715, 1427474964] | 4 | 2 | 1 | 1 | 0 | true |

Two exact records report NPI `1427474964` and one reports `1366933715`. The history belongs to the source/email and repeats on those records. The duplicate NPI records do not add transitions. Both HealthLink and Medscape cases read the same complete published snapshot without recomputing history.

## Real example: one swap without a flip-back

Queried October 31, 2026, for stored cleaned email `sbrooks.arnp@gmail.com`, directly from `iceberg.jteixeira_ipa.pii_clean` snapshot `8811920360682490090`. The stored sequence cutoff remains October 30. Medscape core used cumulative exclusions pinned to opt-out snapshot `4503450222412661359`. These queries read stored metrics without rebuilding history.

[Stored summary SQL](../../sql/examples/25_sequential_history_medscape_published.sql) returns:

| source | email | Retained NPIs | Versions | Dated NPIs | Changes | Swaps | Flip-backs | Sufficient history |
|---|---|---|---:|---:|---:|---:|---:|---|
| medscape | sbrooks.arnp@gmail.com | [1700132818, 1790783207] | 127 | 2 | 1 | 1 | 0 | true |

[Stored daily-transition SQL](../../sql/examples/25_sequential_history_medscape_daily_published.sql) selects the last old-NPI day and the next observed day:

| source | email | Observed day | Previous observed day | NPI set | Added | Removed | Cumulative versions | Changes | Swaps | Flip-backs |
|---|---|---|---|---|---|---|---:|---:|---:|---:|
| medscape | sbrooks.arnp@gmail.com | 2025-10-29 | 2025-10-28 | [1790783207] | [] | [] | 18 | 0 | 0 | 0 |
| medscape | sbrooks.arnp@gmail.com | 2025-10-30 | 2025-10-29 | [1700132818] | [1700132818] | [1790783207] | 19 | 1 | 1 | 0 |

October 30 removes one NPI and adds another, so it contributes one swap. The added NPI had not appeared earlier in this email's observed history, so it contributes no flip-back. The complete retained example has 127 observed versions through March 18, 2026; the table above shows only the transition. This selected case does not measure prevalence.

## Real example: a returning NPI after a removal

The same October 31 publication, retaining an October 30 sequence cutoff, stores a real flip-back for stored cleaned email `fangchenmd@gmail.com`. [Stored summary SQL](../../sql/examples/25_sequential_history_medscape_published.sql) returns:

| source | email | Retained NPIs | Versions | Dated NPIs | Changes | Swaps | Flip-backs | Sufficient history |
|---|---|---|---:|---:|---:|---:|---:|---|
| medscape | fangchenmd@gmail.com | [1255455689, 1407193790] | 6 | 2 | 2 | 1 | 1 | true |

Selected columns from the [stored six-day query](../../sql/examples/25_sequential_history_medscape_daily_published.sql):

| source | email | Observed day | NPI set | Added | Removed | Versions | Changes | Swaps | Flip-backs |
|---|---|---|---|---|---|---:|---:|---:|---:|
| medscape | fangchenmd@gmail.com | 2024-01-10 | [1255455689, 1407193790] | [] | [] | 1 | 0 | 0 | 0 |
| medscape | fangchenmd@gmail.com | 2024-02-08 | [1255455689, 1407193790] | [] | [] | 2 | 0 | 0 | 0 |
| medscape | fangchenmd@gmail.com | 2024-03-07 | [1255455689, 1407193790] | [] | [] | 3 | 0 | 0 | 0 |
| medscape | fangchenmd@gmail.com | 2024-05-10 | [1407193790] | [] | [1255455689] | 4 | 1 | 0 | 0 |
| medscape | fangchenmd@gmail.com | 2024-06-10 | [1255455689] | [1255455689] | [1407193790] | 5 | 2 | 1 | 1 |
| medscape | fangchenmd@gmail.com | 2024-09-10 | [1255455689] | [] | [] | 6 | 2 | 1 | 1 |

May 10 removes an NPI without adding another, so it changes the set but adds no swap. June 10 returns NPI `1255455689` while removing `1407193790`: that transition adds one swap and one flip-back. An earlier removal can therefore make the first swap a flip-back. Missing calendar dates contribute no steps. Sufficiency measures the six observed versions; [freshness](20_link_freshness.md) is assessed separately from the last observed date, September 10, 2024.

## Statistics and validation

[Population SQL](../../sql/statistics/25_sequential_history.sql) counts distinct source/emails, not metric rows. Swap and flip-back percentages divide by emails with dated history. The October 31 measurements use complete canonical snapshot `8811920360682490090`. Sufficient history means at least three observed versions. Counts must not be summed across vendors as unique people or globally distinct emails. The linked statistics query is pinned to this published snapshot for reproduction.

| Source | Emails | Dated emails | Sufficient history | Emails with swaps | Emails with flip-backs | Swap % of dated emails |
|---|---:|---:|---:|---:|---:|---:|
| medscape | 3,550,359 | 3,550,359 | 3,500,157 | 109,280 | 13 | 3.077999% |
| healthlink | 7,688,331 | 7,688,331 | 5,843,007 | 120 | 0 | 0.001561% |
| quantummedica | 1,705,695 | 1,705,695 | 1,703,724 | 0 | 0 | 0% |
| haymarket | 4,223,245 | 4,223,245 | 0 | 0 | 0 | 0% |
| endato | 5,324,318 | 0 | 0 | 0 | 0 | — |
| rocketreach | 3,163,679 | 0 | 0 | 0 | 0 | — |
| drdb | 819,454 | 0 | 0 | 0 | 0 | — |

A missing dated denominator is not a zero swap rate. Every email in the three undated vendors has incomplete-date evidence. Haymarket has dated observations but insufficient history. Medscape has 13 emails with flip-backs, or 0.0003662% of its dated emails. Existing source-date availability is documented in the [source map](../00_source_map.md#available-history).

[Synthetic tests](../../tools/test_sequential_history.py) cover cumulative causality, the illustrated sequence, repeated deliveries, additions/removals, missing days, source isolation and cutoff changes. [Stored integrity checks](../../tests/sequential_history.sql) validate bounds and evidence/summary consistency. DuckDB-translated tests do not replace native Trino checks.

Validation checkpoint, October 31, 2026: the complete local suite passed 120 tests. Native Trino validated the agreed three-day case with three versions, two swaps and one flip-back. All sixteen core integrity checks passed for the rebuilt Medscape population, including sequence and registration checks. Six recovered sources matched all 124 previously validated fields. Final cookie enrichment preserved every core field, key and count. The two Medscape examples and their daily transitions were queried directly from the complete publication.
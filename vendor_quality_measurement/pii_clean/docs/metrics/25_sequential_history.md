# 25. Sequential attribution history

Sequential history describes changes in one vendor’s reported NPI set for an email. It does not establish ownership or whether a change was a correction. These metrics are published for all seven sources.

## How it is computed

The [macro](../../macros/sequential_history.sql) reads eligible `metric_records`, one row per source/email/NPI link, inside each `int_<vendor>__metrics` model. Medscape cumulative NPI opt-outs apply first. Distinct `source/email/npi/observed_day` observations use each link's `observed_days`, which already union the days of all its versions, so repeated versions and email positions add nothing. Only dates through `sequence_as_of_day` participate. The default cutoff is Europe/Paris today.

Each email's NPI set is compared with its previous observed set. Missing calendar days add no transitions. Both additions and removals are required for a swap. A flip-back is a swap adding an NPI seen on any earlier observed day. Count transitions, not individual NPIs. Initial observations add no change.

```sql
count_if(is_swap) OVER w AS swaps,
count_if(is_swap AND cardinality(returned_npis) > 0) OVER w AS flipbacks
```

`w` runs from the first observed email day through the current day, within one source/email. `returned_npis` intersects added NPIs with previously seen NPIs. `sequence_daily_evidence` stores ordered sets, additions, removals, returns and cumulative counts. No daily entry reads future NPI observations.

HealthLink and QuantumMedica collapse consecutive equal delivery-content fingerprints, computed with Trino `checksum` over distinct email/NPI pairs. A later return to earlier content is a new version. Fingerprints have a theoretical collision risk. Medscape uses delivered days. Haymarket has one dated snapshot. Endato, RocketReach and DRDB have no usable dated history.

## Outputs and examples

Stored summaries are `n_versions_observed`, `n_npis_window`, `n_npi_changes`, `n_swaps` and `n_flipbacks`. Despite its name, `n_npis_window` covers all retained dated history through the cutoff, without a rolling window. These source/email summaries repeat on every link of the source/email. A sequence "version" here is an observed delivery state of the email's NPI set, not a version of a source record.

Illustrative sequence: `{n1} → {n2,n3} → {n1,n2}` produces cumulative swaps `0,1,2` and flip-backs `0,0,1`. The final totals are three versions, three NPIs and two changes. Adding an NPI without removing another is not a swap.

Illustrative removal then return: an email reports `{A,B}` on three days, then `{A}`, then `{B}`. The removal of `B` changes the set but adds no swap. The next day removes `A` and returns `B`, which was seen earlier: that transition adds one swap and one flip-back. An earlier removal can therefore make the first swap a flip-back.

`stability_history_sufficient` requires at least `sequence_min_versions` observations, default three. Missing history gives NULL counts, false sufficiency and empty evidence. Mixed dates retain qualified known-date counts with `sequence_has_undated_observations`. `sequence_history_status` and `sequence_definition_version` identify availability and rules. Sufficiency describes history volume, not independent confirmations.

## Real examples

No executed examples exist yet for this definition. [Freshness](20_link_freshness.md) is assessed separately from the last observed date.

## Statistics and validation

No measurements exist yet for this definition.

[Population SQL](../../sql/statistics/25_sequential_history.sql) counts distinct source/emails, not links. Swap and flip-back percentages divide by emails with dated history. Sufficient history means at least three observed versions. Counts must not be summed across vendors as unique people or globally distinct emails. A missing dated denominator is not a zero swap rate. Source-date availability is documented in the [source map](../00_source_map.md#available-history).

[Synthetic tests](../../tools/test_sequential_history.py) cover cumulative causality, the illustrated sequence, repeated deliveries, additions/removals, missing days, source isolation and cutoff changes. [Stored integrity checks](../../tests/sequential_history.sql) validate bounds and evidence/summary consistency. DuckDB-translated tests do not replace native Trino checks.

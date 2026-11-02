# 25. Sequential attribution history

Sequential history describes changes in one vendor’s reported NPI set for an email. It does not establish ownership or whether a change was a correction. These metrics are published for all seven sources.

## How it is computed

The [macro](../../macros/sequential_history.sql) reads eligible `metric_records`, one row per source/email/NPI link, inside each `int_<vendor>__metrics` model. Medscape cumulative NPI opt-outs apply first. Distinct `source/email/npi/observed_day` observations use each link's `observed_days`, which already union the days of all its versions, so repeated versions and email positions add nothing. Only dates through `sequence_as_of_day` participate. Unless set explicitly, the cutoff is the build day in the America/New_York time zone, and the table stores it in every row.

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

Executed November 2, 2026, against `iceberg.jteixeira_ipa.pii_clean` snapshot `2837737034249693554`. These selected cases explain outcomes; they do not measure prevalence.

```sql
SELECT source, email, npi, record_count, n_versions_observed, n_npis_window, n_npi_changes,
       n_swaps, n_flipbacks, stability_history_sufficient, sequence_history_status,
       sequence_has_undated_observations
FROM iceberg.jteixeira_ipa.pii_clean
WHERE ROW(source, link_id) IN (
    ROW('haymarket', '000001F7A2912A5F067399B37D6E035976692BB806F3C0D9BFEE46B2319F5867'),
    ROW('healthlink', '000003E1464D72618D55F78C6D464B854F2B8213906F0546468EE5C189A1376A'),
    ROW('healthlink', '011A4E3469D63171B176507DBDB51E1A4A7FE27976A32920F81AB683684A4A21'),
    ROW('medscape', '0CF18CAFBB0225E8B4AA033E2BE72EA19A212FFF8EFADD542854F7BFB12256E6'),
    ROW('medscape', '07F90157AC8FA07254DD4BF552EB4E4AEF27B83FDB65D97827B7FCDB7E7324A7'),
    ROW('quantummedica', '699DC460F3EC477E7638C66F23CCA825399301FA3110EB7F207D3C4A18B014C4'),
    ROW('quantummedica', 'F2E18603871FF26E72C57E9B80E84EB16AEB7A0489034D20A989D490FDA6A34C'),
    ROW('endato', '00000359411756A423CF6FA62F7ADEA5FAF7F0213AB36334DF4DE1CD16782DF9'))
ORDER BY source, email, link_id
```

| source | email | npi | record_count | n_versions_observed | n_npis_window | n_npi_changes | n_swaps | n_flipbacks | stability_history_sufficient | sequence_history_status | sequence_has_undated_observations |
|---|---|---|---|---|---|---|---|---|---|---|---|
| endato | hhutch2@gmail.com | 1922407774 | 1 | NULL | NULL | NULL | NULL | NULL | false | no_dated_history | true |
| haymarket | ejshim41@yahoo.com | 1104930056 | 1 | 1 | 1 | 0 | 0 | 0 | false | dated_history | false |
| healthlink | csteele@hotmail.com | 1720286941 | 3 | 4 | 1 | 0 | 0 | 0 | true | dated_history | false |
| healthlink | kchuang@memorialcare.org | 1205998929 | 1 | 3 | 2 | 1 | 1 | 0 | true | dated_history | false |
| medscape | drobertsmm@aol.com | 1285060574 | 2 | 172 | 2 | 2 | 2 | 1 | true | dated_history | false |
| medscape | usmanayubkhan@gmail.com | 1346658416 | 1 | 4 | 2 | 2 | 0 | 0 | true | dated_history | false |
| quantummedica | ekendle@yahoo.com | 1982917928 | 1 | 11 | 2 | 1 | 0 | 0 | true | dated_history | false |
| quantummedica | ekendle@yahoo.com | 1407944416 | 1 | 11 | 2 | 1 | 0 | 0 | true | dated_history | false |

**What differentiates these cases:** `ejshim41@yahoo.com` (Haymarket) has a single observed day, so one version, no change and insufficient history. HealthLink `csteele@hotmail.com` has three record versions but four observed sequence versions (the sequence counts delivery states of the email's NPI set, not record versions) with one NPI throughout, so no change. HealthLink `kchuang@memorialcare.org` has two NPIs over three sequence versions: one transition that adds and removes an NPI is one swap. Medscape `drobertsmm@aol.com` has two swaps, one of them a flip-back to an earlier NPI. Medscape `usmanayubkhan@gmail.com` has two changes but no swap, because they only add or remove NPIs. QuantumMedica `ekendle@yahoo.com` has two links, and the sequence summary repeats on both, so it counts once at email level. Endato `hhutch2@gmail.com` is undated: the counts are NULL and the history is not sufficient. [Freshness](20_link_freshness.md) is assessed separately from the last observed date.

## Statistics and validation

Measured **November 2, 2026** from `iceberg.jteixeira_ipa.pii_clean` snapshot `2837737034249693554`. These are exact published-population counts across retained eligible history, not a sample.

Source data period (first and last observed day): HealthLink 2026-01-07 to 2026-10-03, QuantumMedica 2025-09-14 to 2026-10-15, Medscape 2024-01-10 to 2026-11-01 and Haymarket 2021-07-06 (one snapshot day). Endato, RocketReach and DRDB are undated.

[Population SQL](../../sql/statistics/25_sequential_history.sql) counts distinct source/emails, not links. The sequence summary repeats on every link of an email, so distinct emails are the unit of this table. Swap and flip-back percentages divide by emails with dated history. Sufficient history means at least three observed versions. Counts must not be summed across vendors as unique people or globally distinct emails. A missing dated denominator is not a zero swap rate. Source-date availability is documented in the [source map](../00_source_map.md#available-history).

| Source | Emails | dated emails, n (%) | sufficient history, n (% of dated) | with swaps, n (% of dated) | with flip-backs, n (% of dated) | emails with incomplete dates, n |
|---|---|---|---|---|---|---|
| HealthLink | 7,688,331 | 7,688,331 (100.000000%) | 5,843,007 (75.998380%) | 120 (0.001561%) | 0 (0.000000%) | 0 |
| QuantumMedica | 1,705,695 | 1,705,695 (100.000000%) | 1,703,724 (99.884446%) | 0 (0.000000%) | 0 (0.000000%) | 0 |
| Medscape | 3,551,989 | 3,551,989 (100.000000%) | 3,502,047 (98.593971%) | 109,528 (3.083568%) | 13 (0.000366%) | 0 |
| Endato | 5,324,318 | 0 (0.000000%) | — | — | — | 5,324,318 |
| RocketReach | 3,163,679 | 0 (0.000000%) | — | — | — | 3,163,679 |
| DRDB | 819,454 | 0 (0.000000%) | — | — | — | 819,454 |
| Haymarket | 4,223,245 | 4,223,245 (100.000000%) | 0 (0.000000%) | 0 (0.000000%) | 0 (0.000000%) | 0 |

Medscape has the most sequence changes: 109,528 emails (3.08%) with a swap, of which 13 have a flip-back. HealthLink has 120 emails with a swap and none with a flip-back, and QuantumMedica has none. Haymarket has a single snapshot day, so no email has sufficient history. Sufficient history covers 76.0% of HealthLink emails, 98.6% of Medscape emails and 99.9% of QuantumMedica emails. Endato, RocketReach and DRDB have no dated emails, so swap and flip-back rates are undefined.

[Synthetic tests](../../tools/test_sequential_history.py) cover cumulative causality, the illustrated sequence, repeated deliveries, additions/removals, missing days, source isolation and cutoff changes. [Stored integrity checks](../../tests/sequential_history.sql) validate bounds and evidence/summary consistency. DuckDB-translated tests do not replace native Trino checks.

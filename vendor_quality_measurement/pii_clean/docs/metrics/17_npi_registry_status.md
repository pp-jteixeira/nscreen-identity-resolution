# NPI registry status

**Question:** what does current NPPES evidence report about this NPI?

**Target:** `npi_registry_status` in `iceberg.jteixeira_ipa.pii__int_<vendor>__metrics` and `iceberg.jteixeira_ipa.pii_clean`. One row per source/email/NPI link; key: `source`, `link_id`. [Full output reference](../../results/registry_status_summary.md#output-columns).

## How it is computed

Join the link's cleaned `npi` to text-converted `iceberg.npi.nppes_npidata_latest.npi`. Read `npi_deactivation_date`, `npi_reactivation_date`, `replacement_npi` and `npi_deactivation_reason_code`. Aggregate identical trimmed lifecycle tuples; preserve raw evidence and counts.

Parse dates without discarding malformed evidence:

```sql
try_cast(npi_deactivation_date AS date) AS deactivation_day
```

| Status | Meaning |
|---|---|
| `not_found` | No NPPES match; not proof of invalidity. |
| `unknown` | Unusable or contradictory evidence; inspect reason. |
| `replaced` | Agreed nonself replacement without conflicts. |
| `deactivated` | Latest dated event is deactivation. |
| `reactivated` | Latest dated event is reactivation. |
| `active_as_reported` | Matched record reports no lifecycle events/replacement. |

Uncertainty checks precede replacement and chronology.

Comparison date defaults to America/New_York today; `registry_status_as_of_day` fixes evaluation. No historical reconstruction or replacement redirects. Absent deactivation does not independently prove activity.

## Real examples

Executed November 2, 2026, against `iceberg.jteixeira_ipa.pii_clean` snapshot `2837737034249693554`. These selected cases explain outcomes; they do not measure prevalence.

```sql
SELECT source, email, npi, record_count, npi_registry_status, npi_registry_status_reason,
       npi_registry_reference_row_count AS reference_rows,
       npi_registry_deactivation_date, npi_registry_reactivation_date,
       transform(npi_registry_lifecycle_evidence, e -> e.replacement_npi) AS reported_replacement,
       npi_registry_replacement_npi
FROM iceberg.jteixeira_ipa.pii_clean
WHERE source = 'healthlink' AND link_id IN ('000003E1464D72618D55F78C6D464B854F2B8213906F0546468EE5C189A1376A', '000AA98B08D2D650303E377671ACF9FE4F2BA7093F1BF2DF89D72FBFD3E0DF5C', '0004AA908420DF667E820617CC34E9ABAC4A4700AC7DECE8DA3BC2F308F04876', '003135577AB5E3C3237D83842C0159AB42FA6FECBF2820C73E05FC2974262BBB', '004017DBF1446140FCAACF4318A595B969B5A46AA5A7CD1609B4CBFDCE4CDC72', '011FA4D701302B15588E1FEB0652AE9AB06BE1975F8DB463D916D5E2FAFBB0A0')
ORDER BY npi_registry_status, npi_registry_status_reason, link_id
```

| source | email | npi | record_count | npi_registry_status | npi_registry_status_reason | reference_rows | npi_registry_deactivation_date | npi_registry_reactivation_date | reported_replacement | npi_registry_replacement_npi |
|---|---|---|---|---|---|---|---|---|---|---|
| healthlink | csteele@hotmail.com | 1720286941 | 3 | active_as_reported | no_deactivation_reported | 1 | NULL | NULL | [NULL] | NULL |
| healthlink | vpineda@virtua.org | 1386671287 | 1 | deactivated | latest_event_deactivation | 1 | 2026-03-26 | NULL | [NULL] | NULL |
| healthlink | erick.saldanha@moffitt.org | 1104759802 | 1 | not_found | no_nppes_record | 0 | NULL | NULL | [] | NULL |
| healthlink | csmith@aultman.org | 1225659261 | 1 | reactivated | latest_event_reactivation | 1 | 2022-01-11 | 2022-03-25 | [NULL] | NULL |
| healthlink | kcrosse@umm.edu | 1063411908 | 2 | unknown | ambiguous_event_order | 1 | 2006-04-06 | 2006-04-06 | [NULL] | NULL |
| healthlink | llove@alumni.uchicago.edu | 1366687469 | 2 | unknown | self_replacement | 1 | 2008-11-20 | 2008-12-04 | ['1366687469'] | NULL |

**What differentiates these cases:**

- **Missing reference versus no reported events:** the HealthLink NPI `1104759802` has no NPPES match (`reference_rows` 0), so its status is `not_found`. The NPI `1720286941` has a matched reference with no reported events and is `active_as_reported`, which does not prove current activity. Its link merges 3 versions, and all versions share one status because the status depends only on the NPI.
- **Event chronology:** `1386671287` has a deactivation and no reactivation, so it is `deactivated`. `1225659261` has a later reactivation, so it is `reactivated`. For `1063411908` both events have the same date, which cannot establish their order, so it is `unknown`.
- **Uncertainty takes priority:** `1366687469` reports itself as its replacement. Its dates (a deactivation followed by a later reactivation) would otherwise give `reactivated`, but the status is `unknown` with reason `self_replacement`, and the accepted `npi_registry_replacement_npi` stays NULL.

## Statistics by source

Measured **November 2, 2026** from `iceberg.jteixeira_ipa.pii_clean` snapshot `2837737034249693554`. These are exact published-population counts across retained eligible history, not a sample. Source data period (first to last observed day): HealthLink 2026-01-07 to 2026-10-03, QuantumMedica 2025-09-14 to 2026-10-15, Medscape 2024-01-10 to 2026-11-01 and Haymarket 2021-07-06 (a single day). Endato, RocketReach and DRDB are undated.

[Statistics SQL 1](../../sql/statistics/17_npi_registry_status_statement_002.sql) · [Statistics SQL 2](../../sql/statistics/17_npi_registry_status_statement_003.sql)

| Source | Links | Distinct NPIs | active_as_reported, n (%) | deactivated, n (%) | reactivated, n (%) | not_found, n (%) | unknown: ambiguous_event_order, n (%) | unknown: self_replacement, n (%) | replaced, n (%) |
|---|---|---|---|---|---|---|---|---|---|
| HealthLink | 7,688,451 | 3,453,960 | 7,654,195 (99.554449%) | 9,938 (0.129259%) | 20,557 (0.267375%) | 3,415 (0.044417%) | 237 (0.003083%) | 109 (0.001418%) | 0 (0.000000%) |
| QuantumMedica | 1,705,723 | 1,022,015 | 1,692,741 (99.238915%) | 8,083 (0.473875%) | 4,805 (0.281699%) | 8 (0.000469%) | 55 (0.003224%) | 31 (0.001817%) | 0 (0.000000%) |
| Medscape | 3,661,537 | 2,191,605 | 3,520,284 (96.142248%) | 117,970 (3.221871%) | 8,226 (0.224660%) | 14,898 (0.406878%) | 101 (0.002758%) | 58 (0.001584%) | 0 (0.000000%) |
| Endato | 5,427,459 | 1,194,462 | 5,227,039 (96.307296%) | 189,378 (3.489257%) | 10,773 (0.198491%) | 10 (0.000184%) | 135 (0.002487%) | 124 (0.002285%) | 0 (0.000000%) |
| RocketReach | 3,199,535 | 593,028 | 3,118,525 (97.468070%) | 73,265 (2.289864%) | 7,560 (0.236284%) | 14 (0.000438%) | 122 (0.003813%) | 49 (0.001531%) | 0 (0.000000%) |
| DRDB | 826,886 | 580,189 | 782,108 (94.584743%) | 42,214 (5.105178%) | 2,512 (0.303790%) | 5 (0.000605%) | 37 (0.004475%) | 10 (0.001209%) | 0 (0.000000%) |
| Haymarket | 4,223,245 | 1,712,938 | 4,030,766 (95.442391%) | 176,950 (4.189906%) | 9,062 (0.214574%) | 6,286 (0.148843%) | 116 (0.002747%) | 65 (0.001539%) | 0 (0.000000%) |

Percentages use all links within each source. Every link has the stored evaluation date 2026-11-02. Stored classifications preserve their evaluation dates; extraction does not reread NPPES or infer historical activity. `active_as_reported` is not proof of current clinical activity.

Most links are `active_as_reported`: from 94.584743% for DRDB to 99.554449% for HealthLink. Deactivated NPIs are most frequent in DRDB (5.105178%), Haymarket (4.189906%) and Endato (3.489257%). Medscape has the most `not_found` links (14,898, 0.406878%), while no other source exceeds 6,286. The `replaced` status does not occur in any source.

The independent raw-reference diagnostics ([statistics SQL base file](../../sql/statistics/17_npi_registry_status.sql) and [statement 004](../../sql/statistics/17_npi_registry_status_statement_004.sql)) inspect `iceberg.npi.nppes_npidata_latest` directly and are not part of the published population:

| Raw NPPES measure | Count |
|---|---|
| Reference rows (each a distinct NPI) | 9,551,447 |
| Rows with a deactivation date | 361,585 |
| Rows with a reactivation date | 18,267 |
| Rows with a replacement NPI | 82 |
| Rows with a deactivation reason code | 0 |
| Malformed deactivation or reactivation dates | 0 |
| Replacement NPIs that equal the row's own NPI | 82 |
| Replacement NPIs that differ from the row's own NPI | 0 |

Every reported replacement is a self-replacement, which the status rules treat as uncertain, so `replaced` is never assigned. This agrees with the `unknown: self_replacement` links above.

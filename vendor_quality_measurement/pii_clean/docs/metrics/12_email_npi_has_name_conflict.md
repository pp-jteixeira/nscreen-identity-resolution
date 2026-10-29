# Email–NPI name conflict

**Principle:** flag incompatible usable names reported for the same vendor/email/NPI across retained history. The result applies to every metric row for that link, including earlier or nameless records.

**Where:** `iceberg.jteixeira_ipa.pii__int_<vendor>__metrics` and `iceberg.jteixeira_ipa.pii_clean`. Inputs: `source`, `email`, `npi`, `source_name_values`. Output: nullable boolean `email_npi_has_name_conflict`.

## How it is computed

Collect distinct usable names within `source`, `email`, `npi` into `pair_names`. Compare every pair. In this excerpt, `has_disagreeing_pair` means at least one pair fails the fuzzy first/last-name rules below; it is false when there is only one name or all pairs agree.

```sql
CASE WHEN cardinality(pair_names) = 0 THEN NULL
     ELSE has_disagreeing_pair
END AS email_npi_has_name_conflict
```

Both first and last names must agree under [metric 07's fuzzy rules](07_vendor_name_matches_registry_name.md): nicknames, shared tokens, permitted first-name prefixes and small spelling differences. First-name-only agreement is insufficient. Missing/partial names do not create disagreement; registry names never fill missing vendor names.

**Illustrative examples:**

| Names within one vendor/email/NPI | Name count | Conflict |
|---|---:|---|
| `ROBERT SMITH`, `BOB SMITH` | 2 | false |
| `JOHN SMITH`, `JOHN JONES` | 2 | true |
| `JOHN SMITH`, `JOHN SMITH-JONES`, `JOHN JONES` | 3 | true |
| `JOHN SMITH`, missing name | 1 | false |

Every pair is checked: the compound surname in the third example cannot hide disagreement between SMITH and JONES. Different names attached only to different NPIs do not create this flag. The separate `has_conflict_linkage` metric checks competing NPIs at the observation time or within current undated vendor data.

HealthLink uses its retained HCP names without date alignment. This metric includes historical name changes; a true result does not establish an incorrect identity. Vendor partitions and existing metric rows remain separate.

## Statistics by vendor

[Statistics SQL](../../sql/statistics/12_email_npi_has_name_conflict.sql). This file preserves the executed read-only SQL behind these statistics, including the original measurement relation. Re-running it requires that relation and reference inputs; changing sources will change the results.

Historical baseline: `pii__evidence` was the measurement relation at the stated extraction time; it is outside the current managed build. This table is not a live population report.

Measured **October 29, 2026**, on `iceberg.jteixeira_ipa.pii__evidence`, across all retained history. Extraction timestamp: `2026-10-29T07:42:53.767364+00:00`. Counts are exact.

Link percentages use distinct vendor/email/NPI links; row percentages use that vendor's metric rows. Reporting link counts does not deduplicate metric output.

| Vendor | Distinct email–NPI links | Conflicting links, n (%) | Unknown links, n (%) | Conflicting metric rows, n (%) |
|---|---:|---:|---:|---:|
| HealthLink | 7,688,451 | 51 (0.00066%) | 515 (0.00670%) | 73 (0.00065%) |
| QuantumMedica | 1,705,723 | 0 (0.00000%) | 1,705,722 (99.99994%) | 0 (0.00000%) |
| Medscape | 3,659,306 | 2,883 (0.07879%) | 44,709 (1.22179%) | 76,913 (0.16339%) |
| Endato | 5,427,459 | 0 (0.00000%) | 222 (0.00409%) | 0 (0.00000%) |
| RocketReach | 3,199,535 | 0 (0.00000%) | 1,958 (0.06120%) | 0 (0.00000%) |
| DRDB | 826,886 | 10,781 (1.30381%) | 62 (0.00750%) | 23,227 (2.08236%) |
| Haymarket | 4,223,245 | 0 (0.00000%) | 191,914 (4.54423%) | 0 (0.00000%) |

QuantumMedica has usable vendor names for only one link; almost all its outcomes are unknown. Zero conflicts in Endato or RocketReach does not imply that each email belongs to one NPI: this metric compares names within the same email–NPI link.

Measured counts and executed SQL (local-only: `../../results/name_consistency_measurements.json`) · Native validation and field-preservation checks (local-only: `../../results/name_consistency_native_validation.json`)

[Profile SQL](../../sql/name_consistency_profile.sql) · [Independent pairwise check](../../tests/name_consistency.sql) · [Rules](../../macros/name_consistency.sql) · [Name count](11_email_name_count.md)

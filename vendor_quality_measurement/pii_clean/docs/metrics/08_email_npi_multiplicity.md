# Email–NPI multiplicity

**Principle:** count how many distinct reported NPIs one vendor associates with an email across its retained history.

**Where:** `iceberg.jteixeira_ipa.pii__int_<vendor>__metrics` and `iceberg.jteixeira_ipa.pii_clean`. Inputs: `source`, cleaned `email`, trimmed `npi`. Outputs: `email_npi_count` and `email_has_multiple_npis`.

## How it is computed

Group retained records by `source`, `email` and count different nonempty, trimmed NPIs. Then flag counts above one:

```sql
count(DISTINCT npi) AS email_npi_count
```

```sql
email_npi_count > 1 AS email_has_multiple_npis
```

Every metric row for the same vendor/email receives the same count. Vendors are never pooled. DRDB's two inputs belong to one vendor. Repeated records, duplicate email slots and repeated dates cannot increase the distinct-NPI count. Missing email/NPI keys remain in staging; malformed nonempty NPIs still count because validity is a separate question.

**Illustrative examples:**

| Retained observations | Count | Multiple NPIs |
|---|---:|---|
| NPI A repeated 100 times | 1 | false |
| NPI A, then NPI B on a later day | 2 | true |
| Same email, NPI A in vendor X and NPI B in vendor Y | 1 in each vendor | false in each vendor |

Multiplicity does not distinguish historical changes from same-day conflicts or establish ownership. See [reassignment](09_has_been_reassigned.md) and [conflict](10_has_conflict_linkage.md). Aggregation computes the indicator only: existing `source`, `metric_row_id` rows remain, and email–NPI deduplication is deferred.

## Statistics by vendor

Historical baseline: `pii__evidence` was the measurement relation at the stated extraction time; it is outside the current managed build. This table is not a live population report. Medscape counts precede the October 29 population in the project README.

Measured **October 28, 2026**, on `iceberg.jteixeira_ipa.pii__evidence` across all retained source history. Exact counts; email percentages use each vendor's distinct emails, and row percentages use its metric rows. Extraction timestamp: `2026-10-28T21:27:21.738506+00:00`.

| Vendor | Distinct emails | Multiple NPIs: emails, n (%) | Affected metric rows, n (%) | Maximum NPIs/email |
|---|---:|---:|---:|---:|
| HealthLink | 7,688,331 | 120 (0.00156%) | 271 (0.00243%) | 2 |
| QuantumMedica | 1,705,695 | 28 (0.00164%) | 56 (0.00328%) | 2 |
| Medscape | 3,549,520 | 109,147 (3.07498%) | 2,351,016 (5.00414%) | 3 |
| Endato | 5,324,318 | 91,841 (1.72493%) | 194,982 (3.59251%) | 2,172 |
| RocketReach | 3,163,679 | 29,990 (0.94795%) | 96,287 (1.97953%) | 24 |
| DRDB | 819,454 | 7,400 (0.90304%) | 22,404 (2.00858%) | 5 |
| Haymarket | 4,223,245 | 0 (0.00000%) | 0 (0.00000%) | 1 |

Measured counts and executed SQL (local-only: `../../results/email_linkage_measurements.json`) · Native fixtures and preservation checks (local-only: `../../results/email_linkage_native_validation.json`)

[Profile SQL](../../sql/email_npi_profile.sql) · [Population check](../../tests/email_npi_multiplicity.sql) · [Source tables and fields](../00_source_map.md)

# Has conflict linkage

**Principle:** flag competing reported NPIs at the same observation time, within one vendor/email. Output: nullable boolean `has_conflict_linkage` in `iceberg.jteixeira_ipa.pii__int_<vendor>__metrics` and `iceberg.jteixeira_ipa.pii_clean`.

## How it is computed

For dated vendors, count distinct NPIs within `source`, `email`, actual delivery day. Collect days with more than one NPI into `email_conflict_days`, then keep only days observed for this record:

```sql
count(DISTINCT npi) AS daily_npi_count
```

```sql
array_sort(array_intersect(observed_days, email_conflict_days)) AS conflict_days
```

Endato, RocketReach and DRDB compare all current records within each vendor, including both DRDB inputs. This assumes comparability, not a common collection date.

```sql
CASE WHEN source IN ('endato', 'rocketreach', 'drdb') THEN email_npi_count > 1
     WHEN cardinality(conflict_days) > 0 THEN true
     WHEN email_npi_count = 1 THEN false
     WHEN undated_observation_count > 0 THEN NULL
     ELSE false
END AS has_conflict_linkage
```

Repeated copies of one NPI do not create conflict. Unknown days in dated vendors remain unknown; date ranges are never expanded.

**Illustrative example:**

| Day | Email | NPI | Conflict | Reassigned |
|---|---|---|---|---|
| 1 | email1 | A | false | true |
| 2 | email1 | B | true | true |
| 2 | email1 | C | true | true |

Otherwise-identical records can span several days. `conflict_days` lists exactly which of that record's `observed_days` conflict; any such day makes its flag true. Undated-vendor conflicts have an empty `conflict_days` array. A conflict may reflect a shared mailbox or reporting error; it does not identify the correct NPI. Source metric rows remain intact.

## Statistics by vendor

[Statistics SQL](../../sql/statistics/10_has_conflict_linkage.sql). This file preserves the executed read-only SQL behind these statistics, including the original measurement relation. Re-running it requires that relation and reference inputs; changing sources will change the results.

Historical baseline: `pii__evidence` was the measurement relation at the stated extraction time; it is outside the current managed build. This table is not a live population report. Medscape counts precede the October 29 population in the project README.

Measured **October 28, 2026**, on `iceberg.jteixeira_ipa.pii__evidence` across all retained source history. Exact counts; email percentages use each vendor's distinct emails, and row percentages use its metric rows. Extraction timestamp: `2026-10-28T21:27:21.738506+00:00`.

| Vendor | Emails with conflict, n (%) | Conflicting metric rows, n (%) | Unknown metric rows, n (%) |
|---|---:|---:|---:|
| HealthLink | 0 (0.00000%) | 0 (0.00000%) | 0 (0.00000%) |
| QuantumMedica | 28 (0.00164%) | 56 (0.00328%) | 0 (0.00000%) |
| Medscape | 16 (0.00045%) | 46 (0.00010%) | 0 (0.00000%) |
| Endato | 91,841 (1.72493%) | 194,982 (3.59251%) | 0 (0.00000%) |
| RocketReach | 29,990 (0.94795%) | 96,287 (1.97953%) | 0 (0.00000%) |
| DRDB | 7,400 (0.90304%) | 22,404 (2.00858%) | 0 (0.00000%) |
| Haymarket | 0 (0.00000%) | 0 (0.00000%) | 0 (0.00000%) |

An email counts once if any of its records conflicts. Only the conflicting records contribute to the row count. Endato, RocketReach and DRDB use the undated-data comparison described above.

Measured counts and executed SQL (local-only: `../../results/email_linkage_measurements.json`) · Native fixtures and preservation checks (local-only: `../../results/email_linkage_native_validation.json`)

[Profile SQL](../../sql/email_linkage_profile.sql) · [Population check](../../tests/email_linkage_history.sql) · [Reassignment](09_has_been_reassigned.md) · [Source tables](../00_source_map.md)

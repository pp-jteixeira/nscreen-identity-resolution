# Conflicting NPIs share a name

**Question:** does this record share a fuzzy-matching vendor name with another NPI in its conflict context? A shared name does not establish which NPI is correct.

**Where:** `conflicting_npis_share_name` in `iceberg.jteixeira_ipa.pii__int_<vendor>__metrics` and `iceberg.jteixeira_ipa.pii_clean`; key: `source`, `metric_row_id`.

## How it is computed

Within the same vendor/email, compare this record’s `source_name_values` with records on other NPIs whose `conflict_days` overlap. Endato, RocketReach and DRDB instead use one current snapshot per vendor, including both DRDB feeds. Never infer overlap from date bounds or use names from unrelated dates.

Both first and last names must agree under [metric 07’s fuzzy rules](07_vendor_name_matches_registry_name.md). Each peer comparison is true for any matching name pair, false when usable names exist on both sides but none match, or null when either side lacks usable names.

```sql
CASE WHEN has_conflict_linkage AND cardinality(conflicting_npi_name_comparisons) > 0
     THEN any_match(conflicting_npi_name_comparisons, p -> p.shares_name)
END AS conflicting_npis_share_name
```

Any true wins; otherwise a missing comparison leaves null. False requires every peer comparison to be a known mismatch. Without an established conflict, the result is null: not applicable when `has_conflict_linkage = false`, unknown timing when that flag is null.

**Illustrative examples** (different NPIs, same conflict context):

| This record | Other NPI’s name | Result |
|---|---|---|
| ROBERT SMITH | BOB SMITH | true |
| JOHN SMITH | JOHN JONES | false |
| JOHN SMITH | Missing | unknown |

HealthLink’s HCP-reference names have no date alignment. Registry names never fill missing names. A true result can coexist with disagreeing peers; records remain separate.

`conflicting_npi_name_comparisons` retains peer NPIs, names, overlapping days and outcomes for [full manual inspection](../../sql/conflicting_names_debug.sql). Undated comparisons have empty day arrays.

## Statistics by vendor

Historical baseline: `pii__evidence` was the measurement relation at the stated extraction time; it is outside the current managed build. This table is not a live population report.

Measured **October 29, 2026**, on `iceberg.jteixeira_ipa.pii__evidence`. Extraction: `2026-10-29T09:55:28.873179+00:00`. Exact counts; percentages use each vendor’s conflict rows.

| Vendor | Conflict rows | Shared name, n (%) | Different names, n (%) | Unknown names, n (%) |
|---|---:|---:|---:|---:|
| HealthLink | 0 | 0 (—) | 0 (—) | 0 (—) |
| QuantumMedica | 56 | 0 (0.00%) | 0 (0.00%) | 56 (100.00%) |
| Medscape | 46 | 21 (45.65%) | 21 (45.65%) | 4 (8.70%) |
| Endato | 194,982 | 131,452 (67.42%) | 63,516 (32.58%) | 14 (0.01%) |
| RocketReach | 96,287 | 29,601 (30.74%) | 66,538 (69.10%) | 148 (0.15%) |
| DRDB | 22,404 | 17,010 (75.92%) | 4,985 (22.25%) | 409 (1.83%) |
| Haymarket | 0 | 0 (—) | 0 (—) | 0 (—) |

Across 75,564,265 metric rows, 75,250,490 are not applicable and 0 have unknown conflict timing; both groups have a null name-sharing flag. Rows for one email–NPI link can differ. — means no conflict rows.

Measured counts and SQL (local-only: `../../results/conflicting_names_measurements.json`) · Native fixtures and preservation (local-only: `../../results/conflicting_names_native_validation.json`) · Publication checks (local-only: `../../results/evidence_build.json`)

[Calculation](../../macros/name_consistency.sql) · [Independent check](../../tests/conflicting_names.sql) · [Profile SQL](../../sql/conflicting_names_profile.sql)

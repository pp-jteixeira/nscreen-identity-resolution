# Conflicting NPIs share a facility

**Question:** does another NPI in this record’s conflict context share an associated facility NPI?

**Status:** implemented locally; measured read-only on October 29, 2026. Unpublished: warehouse outputs lack these columns.

**Target columns:** `conflicting_npis_share_facility`, `facility_npi_values`, `conflicting_npi_facility_comparisons` in `iceberg.jteixeira_ipa.pii__int_<vendor>__metrics` and `iceberg.jteixeira_ipa.pii_clean`. Key: `source`, `metric_row_id`.

## How it is computed

Join trimmed `npi` to `bq_bi.analytics_prod.npi_facility_association.provider_npi`. Collect distinct trimmed `facility_npis` across **all ranks**. Keep ten-digit IDs except `0000000000`; no checksum validation. Cluster IDs and states are not matching keys.

Compare within vendor/email on overlapping `conflict_days`. Endato, RocketReach and DRDB use undated snapshots. Retain peer NPIs, overlapping dates, facility IDs and intersections.

Simplified peer calculation:

```sql
CASE WHEN cardinality(facility_npi_values) > 0
          AND cardinality(peer.facilities) > 0
     THEN arrays_overlap(facility_npi_values, peer.facilities)
END AS shares_facility
```

Any match gives true. False requires usable, disjoint sets for every peer. Otherwise null means missing evidence, unknown timing or inapplicable conflict. Empty arrays mean unavailable evidence. Reference duplicates cannot multiply records.

Associations have no activity dates. Overlap proves neither coattendance nor ownership; disjoint sets do not prove different workplaces. HealthLink contributes reference evidence.

**Illustrative:** `{F1,F2}` versus `{F2}` matches; versus missing evidence remains unknown.

## Statistics by vendor

Exact read-only evaluation over 75,564,265 saved metric rows. Percentages below use each vendor’s conflict rows. — means no conflicts.

| Vendor | Conflict rows | Shared, n (%) | Disjoint, n (%) | Unknown, n (%) |
|---|---:|---:|---:|---:|
| HealthLink | 0 | 0 (—) | 0 (—) | 0 (—) |
| QuantumMedica | 56 | 0 (0.00%) | 10 (17.86%) | 46 (82.14%) |
| Medscape | 46 | 0 (0.00%) | 21 (45.65%) | 25 (54.35%) |
| Endato | 194,982 | 2,347 (1.20%) | 19,181 (9.84%) | 173,454 (88.96%) |
| RocketReach | 96,287 | 5,998 (6.23%) | 12,309 (12.78%) | 77,980 (80.99%) |
| DRDB | 22,404 | 235 (1.05%) | 2,832 (12.64%) | 19,337 (86.31%) |
| Haymarket | 0 | 0 (—) | 0 (—) | 0 (—) |

[Link-level coverage and real examples](../../results/conflicting_facilities_summary.md) · Executed SQL/results (local-only: `../../results/conflicting_facilities_measure.json`) · Native checks (local-only: `../../results/conflicting_facilities_native.json`) · Local tests (local-only: `../../results/conflicting_facilities_local_tests.txt`)

[Lookup/comparison SQL](../../macros/facility_consistency.sql) · [Shared windows](../../macros/name_consistency.sql) · [Independent check](../../tests/conflicting_facilities.sql) · [Post-publication inspection](../../sql/conflicting_facilities_debug.sql)

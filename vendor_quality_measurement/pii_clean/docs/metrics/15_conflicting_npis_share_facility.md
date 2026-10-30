# Conflicting NPIs share a facility

**Question:** does another NPI in this record’s conflict context share an associated facility NPI?

**Status:** published in all seven vendor metric views and `iceberg.jteixeira_ipa.pii_clean` on October 29, 2026. Full candidate integrity, schema and checksum checks passed. [Publication report](../../results/publication_20261029/report.md).

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

## Real examples: contrasting outcomes

Selected real records, queried October 30, 2026, from `iceberg.jteixeira_ipa.pii_clean` at snapshot `8096642935433856886`. These examples explain outcomes; they are not prevalence estimates. Conflict examples are selected with exactly one peer comparison, so the displayed peer fully explains the aggregate outcome. Undated Endato comparisons use the available vendor snapshot.

[Runnable example SQL](../../sql/examples/15_conflicting_npis_share_facility.sql):

```sql
WITH selected AS (
    SELECT *
    FROM iceberg.jteixeira_ipa.pii_clean FOR VERSION AS OF 8096642935433856886
    WHERE (source = 'endato' AND metric_row_id IN (
        '730FB3822EC1EB3855BF21A4E1C10C1F2788A9DAA943ED02124432207C2B0194',
        'BA2E681A099C6DCF48E741F31F4DA9744B7A4D4FBF656281D78517944D4F72C4',
        'CE8141B8077B2FE80852C9AF88CB99C0FF2B3C84EB6C6C4293F90E954E801367'))
       OR (source = 'haymarket' AND metric_row_id IN (
        '3BA64E63FD9A2721167D2B60E3B60D71164171D99D17697F44AA1A7D35751BEE'))
)
SELECT m.source,
       m.npi,
       (element_at(m.conflicting_npi_facility_comparisons, 1)).npi AS peer_npi,
       m.facility_npi_values AS own_values,
       (element_at(m.conflicting_npi_facility_comparisons, 1)).facility_npis AS peer_values,
       m.has_conflict_linkage AS conflict,
       m.conflicting_npis_share_facility AS shares_facility
FROM selected m
ORDER BY m.source, m.metric_row_id
```

**Result:** 4 rows.

| source | npi | peer_npi | own_values | peer_values | conflict | shares_facility |
|---|---|---|---|---|---|---|
| endato | 1114929445 | 1922090380 | [] | [] | true | NULL |
| endato | 1275994485 | 1649528381 | [1194762294, 1538324009, 1962582015] | [1447206370, 1548253917, 1710970918] | true | false |
| endato | 1558628578 | 1255422341 | [1033475959, 1184709057, 1326033341] | [1184709057, 1326033341] | true | true |
| haymarket | 1639195985 | NULL | [1306883228, 1457071235, 1881642239, 1932829488, 1942920616] | NULL | false | NULL |

**What differentiates these cases:** A known shared value gives true; known disjoint evidence gives false. With an established conflict, missing evidence leaves NULL. Without a conflict, NULL is not applicable. Facility IDs must overlap exactly. Shared state or cluster membership is insufficient, and empty facility sets are unknown.

Stored indicators are unchanged by display helpers. Reproduction requires the pinned snapshot to remain available.

## Statistics by vendor

[Statistics SQL](../../sql/statistics/15_conflicting_npis_share_facility.sql). These read-only queries aggregate the published evidence columns in `iceberg.jteixeira_ipa.pii_clean`, without rebuilding reference joins. The tables below retain their stated historical measurement times. A later pipeline publication can change query results. Run coverage for all vendor denominators, then outcomes for conflict classifications; zero-conflict vendors emit no outcome rows.

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

[Link-level coverage and real examples](../../results/conflicting_facilities_summary.md) · Executed SQL/results (historical output, not retained: `../../results/conflicting_facilities_measure.json`) · Native checks (historical output, not retained: `../../results/conflicting_facilities_native.json`) · Local tests (historical output, not retained: `../../results/conflicting_facilities_local_tests.txt`)

[Lookup/comparison SQL](../../macros/facility_consistency.sql) · [Shared windows](../../macros/name_consistency.sql) · [Independent check](../../tests/conflicting_facilities.sql) · [Stored facility inspection](../../sql/conflicting_facilities_debug.sql)

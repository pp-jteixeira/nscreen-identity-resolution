# Conflicting NPIs share a facility

**Question:** does another NPI in this record’s conflict context share an associated facility NPI?

**Status:** published in canonical snapshot `8811920360682490090`, verified October 31, 2026.

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

## Real examples

Executed October 31, 2026, against canonical snapshot `8811920360682490090`. These selected cases explain outcomes; they do not measure prevalence.

[Executed example SQL](../../sql/examples/15_conflicting_npis_share_facility.sql):

```sql
WITH selected AS (
    SELECT *
    FROM iceberg.jteixeira_ipa.pii_clean FOR VERSION AS OF 8811920360682490090
    WHERE (source = 'endato' AND metric_row_id IN (
        '730FB3822EC1EB3855BF21A4E1C10C1F2788A9DAA943ED02124432207C2B0194',
        'BA2E681A099C6DCF48E741F31F4DA9744B7A4D4FBF656281D78517944D4F72C4',
        'CE8141B8077B2FE80852C9AF88CB99C0FF2B3C84EB6C6C4293F90E954E801367'))
       OR (source = 'haymarket' AND metric_row_id IN (
        '3BA64E63FD9A2721167D2B60E3B60D71164171D99D17697F44AA1A7D35751BEE'))
)
SELECT m.source,
       m.email,
       m.npi,
       (element_at(m.conflicting_npi_facility_comparisons, 1)).npi AS peer_npi,
       m.facility_npi_values AS own_values,
       (element_at(m.conflicting_npi_facility_comparisons, 1)).facility_npis AS peer_values,
       m.has_conflict_linkage AS conflict,
       m.conflicting_npis_share_facility AS shares_facility
FROM selected m
ORDER BY m.source, m.metric_row_id
```

| source | email | npi | peer_npi | own_values | peer_values | conflict | shares_facility |
|---|---|---|---|---|---|---|---|
| endato | cmizelle@att.net | 1114929445 | 1922090380 | [] | [] | true | NULL |
| endato | mountaindeeva2@aol.com | 1275994485 | 1649528381 | [1194762294, 1538324009, 1659456077] | [1336132364, 1447206370, 1548253917] | true | false |
| endato | nathan@nobrien.com | 1558628578 | 1255422341 | [1033475959, 1184709057, 1326033341] | [1184709057, 1326033341] | true | true |
| haymarket | mkubosumi@wvmedical.com | 1639195985 | NULL | [1306883228, 1457071235, 1881642239, 1932829488, 1942920616] | NULL | false | NULL |

**What differentiates these cases:** A known shared value gives true; known disjoint evidence gives false. With an established conflict, missing evidence leaves NULL. Without a conflict, NULL is not applicable. Facility IDs must overlap exactly. Shared state or cluster membership is insufficient, and empty facility sets are unknown.

## Statistics by source

Measured **October 31, 2026** from `iceberg.jteixeira_ipa.pii_clean` snapshot `8811920360682490090`. These are exact published-population counts across retained eligible history, not a sample. Stored evaluation dates remain unchanged.

[Executed statistics SQL 1](../../sql/statistics/15_conflicting_npis_share_facility.sql) · [Executed statistics SQL 2](../../sql/statistics/15_conflicting_npis_share_facility_statement_002.sql)

| Source | Usable evidence / all records, n (%) | Conflict records | Shared, n (%) | Disjoint, n (%) | Unknown, n (%) |
|---|---|---|---|---|---|
| HealthLink | 4,305,037 (38.589376%) | 0 | 0 (—) | 0 (—) | 0 (—) |
| QuantumMedica | 785,920 (46.075476%) | 56 | 0 (0.000000%) | 10 (17.857143%) | 46 (82.142857%) |
| Medscape | 19,824,025 (42.031785%) | 46 | 0 (0.000000%) | 21 (45.652174%) | 25 (54.347826%) |
| Endato | 1,653,631 (30.467867%) | 194,982 | 2,393 (1.227293%) | 19,259 (9.877322%) | 173,330 (88.895385%) |
| RocketReach | 1,887,187 (38.797918%) | 96,287 | 6,102 (6.337304%) | 12,405 (12.883359%) | 77,780 (80.779337%) |
| DRDB | 415,129 (37.217448%) | 22,404 | 241 (1.075701%) | 2,807 (12.529013%) | 19,356 (86.395287%) |
| Haymarket | 1,778,551 (42.113375%) | 0 | 0 (—) | 0 (—) | 0 (—) |

Coverage uses all metric records. Shared/disjoint/unknown percentages use established conflict records. Zero-conflict percentages are undefined (—). Distinct-link outcomes can overlap across records and must not be added.

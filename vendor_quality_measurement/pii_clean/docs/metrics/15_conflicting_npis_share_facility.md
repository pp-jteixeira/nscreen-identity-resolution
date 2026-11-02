# Conflicting NPIs share a facility

**Question:** does another NPI in this link’s conflict context share an associated facility NPI?

**Target columns:** `conflicting_npis_share_facility`, `facility_npi_values`, `conflicting_npi_facility_comparisons` in `iceberg.jteixeira_ipa.pii__int_<vendor>__metrics` and `iceberg.jteixeira_ipa.pii_clean`. One row per source/email/NPI link; key: `source`, `link_id`.

## How it is computed

Join trimmed `npi` to `bq_bi.analytics_prod.npi_facility_association.provider_npi`. Collect distinct trimmed `facility_npis` across **all ranks**. Keep ten-digit IDs except `0000000000`; no checksum validation. Cluster IDs and states are not matching keys. Facility evidence depends only on the link's NPI, so every version of a link shares it.

Compare within vendor/email on overlapping `conflict_days`. Endato, RocketReach and DRDB use undated snapshots, so every other NPI of the email is a peer. Retain peer NPIs, overlapping dates, facility IDs and intersections.

Simplified peer calculation:

```sql
CASE WHEN cardinality(facility_npi_values) > 0
          AND cardinality(peer.facilities) > 0
     THEN arrays_overlap(facility_npi_values, peer.facilities)
END AS shares_facility
```

Any match gives true. False requires usable, disjoint sets for every peer. Otherwise null means missing evidence, unknown timing or inapplicable conflict. Empty arrays mean unavailable evidence. Reference duplicates cannot multiply links. This metric has no `_latest` form.

Associations have no activity dates. Overlap proves neither coattendance nor ownership; disjoint sets do not prove different workplaces. HealthLink contributes reference evidence.

## Real examples

No executed examples exist yet for this definition.

**What differentiates outcomes:** A known shared value gives true; known disjoint evidence gives false. With an established conflict, missing evidence leaves NULL. Without a conflict, NULL is not applicable. Facility IDs must overlap exactly. Shared state or cluster membership is insufficient, and empty facility sets are unknown.

## Statistics by source

No measurements exist yet for this definition.

[Statistics SQL 1](../../sql/statistics/15_conflicting_npis_share_facility.sql) · [Statistics SQL 2](../../sql/statistics/15_conflicting_npis_share_facility_statement_002.sql)

Coverage uses all links. Shared/disjoint/unknown percentages use links with an established conflict. Zero-conflict percentages are undefined (—).

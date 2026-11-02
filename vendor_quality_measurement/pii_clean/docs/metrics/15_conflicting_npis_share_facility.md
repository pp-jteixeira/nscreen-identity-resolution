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

Executed November 2, 2026, against `iceberg.jteixeira_ipa.pii_clean` snapshot `2837737034249693554`. These selected cases explain outcomes; they do not measure prevalence.

```sql
SELECT source, email, npi,
       cardinality(facility_npi_values) AS facility_count,
       transform(conflicting_npi_facility_comparisons, p -> p.npi || ': ' || cast(cardinality(p.facility_npis) AS varchar) || ' facilities, shared ' || array_join(p.shared_facility_npis, ',')) AS peer_facilities,
       has_conflict_linkage, conflicting_npis_share_facility
FROM iceberg.jteixeira_ipa.pii_clean
WHERE (source = 'endato' AND link_id IN ('00243E31A3B9EB536C682B46BAE71B75246EA991E2A60F994DD18C2320ADD9ED', '000592C07B21C865EAAD74780C5202F3DA313FB089E7A8BE531845996D9D56E2', '0000D99684BF16BE7602BA1F9A425F5BAC8E6AC57A0EA41D47F76C41805EA27A'))
   OR (source = 'rocketreach' AND link_id IN ('00033226A0177C4F4553C42BC5684634B96FD45835A11FCEE9901F94D39D47F4'))
   OR (source = 'medscape' AND link_id IN ('4C7468EBC1D99D7914693F0F05ED57FF0F55BDBF5DC6277B2801FC795FED5D19', '07F90157AC8FA07254DD4BF552EB4E4AEF27B83FDB65D97827B7FCDB7E7324A7'))
   OR (source = 'healthlink' AND link_id IN ('011A4E3469D63171B176507DBDB51E1A4A7FE27976A32920F81AB683684A4A21'))
ORDER BY source, link_id
```

| source | email | npi | facility_count | peer_facilities | has_conflict_linkage | conflicting_npis_share_facility |
|---|---|---|---|---|---|---|
| endato | ppaulaj7i20@verizon.net | 1871569921 | 0 | ['1265075410: 1 facilities, shared '] | true | NULL |
| endato | jlynnschlieckau@gmail.com | 1346594702 | 2 | ['1538236492: 2 facilities, shared '] | true | false |
| endato | dkottra@aol.com | 1841347879 | 2 | ['1699788901: 2 facilities, shared 1912904210'] | true | true |
| healthlink | kchuang@memorialcare.org | 1205998929 | 4 | [] | false | NULL |
| medscape | usmanayubkhan@gmail.com | 1346658416 | 2 | ['1437227543: 8 facilities, shared '] | true | false |
| medscape | pawnking4@netscape.net | 1033420419 | 0 | ['1861566606: 0 facilities, shared '] | true | NULL |
| rocketreach | mtwester@yahoo.com | 1669457917 | 3 | ['1366401457: 0 facilities, shared '] | true | NULL |

**What differentiates these cases:**

- **Shared facility (true):** the Endato link for `dkottra@aol.com` and its peer both list facility `1912904210`.
- **Known disjoint sets (false):** the Endato link for `jlynnschlieckau@gmail.com` has 2 facilities and its peer has 2 others. The Medscape link for `usmanayubkhan@gmail.com` has 2 facilities and its dated peer has 8 others.
- **Missing evidence (NULL, unknown):** the Endato link for `ppaulaj7i20@verizon.net` has no facility evidence although its peer has one. The RocketReach link for `mtwester@yahoo.com` has 3 facilities but its peer has none. Both Medscape links of `pawnking4@netscape.net` have no facility evidence.
- **No conflict (NULL, not applicable):** the HealthLink link for `kchuang@memorialcare.org` has 4 facilities but no conflict, so the metric does not apply.

## Statistics by source

Measured **November 2, 2026** from `iceberg.jteixeira_ipa.pii_clean` snapshot `2837737034249693554`. These are exact published-population counts across retained eligible history, not a sample. Source data period (first to last observed day): HealthLink 2026-01-07 to 2026-10-03, QuantumMedica 2025-09-14 to 2026-10-15, Medscape 2024-01-10 to 2026-11-01 and Haymarket 2021-07-06 (a single day). Endato, RocketReach and DRDB are undated.

[Statistics SQL 1](../../sql/statistics/15_conflicting_npis_share_facility.sql) · [Statistics SQL 2](../../sql/statistics/15_conflicting_npis_share_facility_statement_002.sql)

| Source | Links | With facility evidence, n (% of links) | Conflict links, n (% of links) | Shares a facility, n (% of conflict links) | Different facilities, n (% of conflict links) | Unknown, n (% of conflict links) |
|---|---|---|---|---|---|---|
| HealthLink | 7,688,451 | 2,829,519 (36.802199%) | 0 (0.000000%) | 0 (undefined) | 0 (undefined) | 0 (undefined) |
| QuantumMedica | 1,705,723 | 786,248 (46.094706%) | 56 (0.003283%) | 0 (0.000000%) | 10 (17.857143%) | 46 (82.142857%) |
| Medscape | 3,661,537 | 1,297,433 (35.434109%) | 32 (0.000874%) | 0 (0.000000%) | 12 (37.500000%) | 20 (62.500000%) |
| Endato | 5,427,459 | 1,654,126 (30.476987%) | 194,982 (3.592510%) | 2,430 (1.246269%) | 19,273 (9.884502%) | 173,279 (88.869229%) |
| RocketReach | 3,199,535 | 1,217,955 (38.066625%) | 65,846 (2.057987%) | 3,971 (6.030738%) | 7,693 (11.683322%) | 54,182 (82.285940%) |
| DRDB | 826,886 | 298,347 (36.080790%) | 14,832 (1.793718%) | 160 (1.078749%) | 1,846 (12.446063%) | 12,826 (86.475189%) |
| Haymarket | 4,223,245 | 1,779,289 (42.130850%) | 0 (0.000000%) | 0 (undefined) | 0 (undefined) | 0 (undefined) |

Coverage uses all links. Shared, different and unknown percentages use links with an established conflict. Zero-conflict percentages are undefined. Haymarket and HealthLink have no conflict links, so only their coverage is shown, and they have no outcome rows. No link has unknown conflict timing.

Facility evidence is available for 30.476987% (Endato) to 46.094706% (QuantumMedica) of links. Most conflict outcomes are unknown because at least one side lacks facility evidence: Endato 88.869229%, DRDB 86.475189% and RocketReach 82.285940%. A shared facility is uncommon: Endato 1.246269%, RocketReach 6.030738% and DRDB 1.078749%, and none of the 32 Medscape and 56 QuantumMedica conflict links share one.

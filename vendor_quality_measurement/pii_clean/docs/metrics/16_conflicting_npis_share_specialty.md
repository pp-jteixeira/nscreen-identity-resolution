# Conflicting NPIs share a specialty

**Status:** published in all seven vendor metric views and `iceberg.jteixeira_ipa.pii_clean` on October 29, 2026. Full candidate integrity, schema and checksum checks passed. [Publication report](../../results/publication_20261029/report.md).

**Question:** does another NPI in this record’s conflict context share an exact recognized taxonomy code?

**Target:** `conflicting_npis_share_specialty`, `specialty_code_values`, `specialty_reference_table`, `specialty_definition_version`, `conflicting_npi_specialty_comparisons` in `iceberg.jteixeira_ipa.pii__int_<vendor>__metrics` and `iceberg.jteixeira_ipa.pii_clean`. Key: `source`, `metric_row_id`.

## How it is computed

Join record `npi` to text-converted `iceberg.npi.nppes_npidata_latest.npi`. Read `healthcare_provider_taxonomy_code_1` through `_15`. Trim, uppercase, validate against `iceberg.npi.npi_taxonomy.code`, and deduplicate per NPI. Include all slots without preferring primary flags. Vendor specialty labels and broad classification names are not substituted.

Compare other NPIs within vendor/email on exact overlapping `conflict_days`; Endato, RocketReach and both DRDB feeds use undated vendor contexts. Simplified peer expression:

```sql
CASE WHEN cardinality(specialty_code_values) > 0
          AND cardinality(peer.specialties) > 0
     THEN arrays_overlap(specialty_code_values, peer.specialties)
END AS shares_specialty
```

Any match gives true. False requires known disjoint retained sets for every peer. Otherwise null means missing evidence, unknown timing or inapplicable conflict. Preserve peer NPIs, dates, code sets and intersections. Lookup aggregation preserves record grain.

Current NPPES evidence is not aligned to historical vendor dates. Disjoint codes do not prove clinically unrelated providers; shared codes do not establish email ownership.

## Real examples: contrasting outcomes

Selected real records, queried October 30, 2026, from `iceberg.jteixeira_ipa.pii_clean` at snapshot `8096642935433856886`. These examples explain outcomes; they are not prevalence estimates. Conflict examples are selected with exactly one peer comparison, so the displayed peer fully explains the aggregate outcome. Undated Endato comparisons use the available vendor snapshot.

[Runnable example SQL](../../sql/examples/16_conflicting_npis_share_specialty.sql):

```sql
WITH selected AS (
    SELECT *
    FROM iceberg.jteixeira_ipa.pii_clean FOR VERSION AS OF 8096642935433856886
    WHERE (source = 'endato' AND metric_row_id IN (
        '730FB3822EC1EB3855BF21A4E1C10C1F2788A9DAA943ED02124432207C2B0194',
        '81EEC062442BE87D989714B321418BF79E372D7467D15AC482DE2844E199216D',
        'A3299D24002D082B3C08421FE21B7E983C55D975FD46ECF9BC388D5C60E3052F'))
       OR (source = 'haymarket' AND metric_row_id IN (
        '207590C83205FF116C6350B5F9ED7FD684F8341BDD55BA5CA2FF0A38755319AF'))
)
SELECT m.source,
       m.email,
       m.npi,
       (element_at(m.conflicting_npi_specialty_comparisons, 1)).npi AS peer_npi,
       m.specialty_code_values AS own_values,
       (element_at(m.conflicting_npi_specialty_comparisons, 1)).specialty_codes AS peer_values,
       m.has_conflict_linkage AS conflict,
       m.conflicting_npis_share_specialty AS shares_specialty
FROM selected m
ORDER BY m.source, m.metric_row_id
```

**Result:** 4 rows.

| source | email | npi | peer_npi | own_values | peer_values | conflict | shares_specialty |
|---|---|---|---|---|---|---|---|
| endato | cmizelle@att.net | 1114929445 | 1922090380 | [363L00000X, 367A00000X] | [363LP0200X] | true | false |
| endato | mish16a@collegeclub.com | 1851550107 | 1083841183 | [225100000X] | [225100000X] | true | true |
| endato | ramboleymah@gmail.com | 1902846181 | 1346316783 | [] | [163W00000X] | true | NULL |
| haymarket | robinljones99@hotmail.com | 1215221387 | nan | [] | NULL | false | NULL |

**What differentiates these cases:** A known shared value gives true; known disjoint evidence gives false. With an established conflict, missing evidence leaves NULL. Without a conflict, NULL is not applicable. `363L00000X` and `363LP0200X` do not match despite the shared prefix. Taxonomy codes must overlap exactly. Similar labels or broad specialty groups are insufficient, and empty code sets are unknown.

Stored indicators are unchanged by display helpers. Reproduction requires the pinned snapshot to remain available.

## Statistics by vendor

[Statistics SQL](../../sql/statistics/16_conflicting_npis_share_specialty.sql). These read-only queries aggregate the published evidence columns in `iceberg.jteixeira_ipa.pii_clean`, without rebuilding reference joins. The tables below retain their stated historical measurement times. A later pipeline publication can change query results. Run coverage for all vendor denominators, then outcomes for conflict classifications; zero-conflict vendors emit no outcome rows.

Exact evaluation over 75,564,265 saved rows. Outcome percentages use each vendor’s conflict rows; — means no conflicts.

| Vendor | Conflict rows | Shared, n (%) | Disjoint, n (%) | Unknown, n (%) |
|---|---:|---:|---:|---:|
| HealthLink | 0 | 0 (—) | 0 (—) | 0 (—) |
| QuantumMedica | 56 | 8 (14.29%) | 48 (85.71%) | 0 (0.00%) |
| Medscape | 46 | 8 (17.39%) | 34 (73.91%) | 4 (8.70%) |
| Endato | 194,982 | 21,991 (11.28%) | 157,786 (80.92%) | 15,205 (7.80%) |
| RocketReach | 96,287 | 16,044 (16.66%) | 73,947 (76.80%) | 6,296 (6.54%) |
| DRDB | 22,404 | 1,978 (8.83%) | 17,642 (78.74%) | 2,784 (12.43%) |
| Haymarket | 0 | 0 (—) | 0 (—) | 0 (—) |

[Coverage, link counts and examples](../../results/conflicting_specialties_summary.md) · Executed measurements (historical output, not retained: `../../results/conflicting_specialties_measure.json`) · Native validation (historical output, not retained: `../../results/conflicting_specialties_native.json`) · Local tests (historical output, not retained: `../../results/conflicting_specialties_local_tests.txt`)

[Lookup and comparison](../../macros/specialty_consistency.sql) · [Shared windows](../../macros/name_consistency.sql) · [Independent checks](../../tests/conflicting_specialties.sql) · [Post-publication inspection](../../sql/conflicting_specialties_debug.sql)

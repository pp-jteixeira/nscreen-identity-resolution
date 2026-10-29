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

**Illustrative:** two providers sharing `207Q00000X` match. Different codes under the same broad classification do not. Unrecognized-only codes remain unknown.

Current NPPES evidence is not aligned to historical vendor dates. Disjoint codes do not prove clinically unrelated providers; shared codes do not establish email ownership.

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

[Coverage, link counts and examples](../../results/conflicting_specialties_summary.md) · Executed measurements (local-only: `../../results/conflicting_specialties_measure.json`) · Native validation (local-only: `../../results/conflicting_specialties_native.json`) · Local tests (local-only: `../../results/conflicting_specialties_local_tests.txt`)

[Lookup and comparison](../../macros/specialty_consistency.sql) · [Shared windows](../../macros/name_consistency.sql) · [Independent checks](../../tests/conflicting_specialties.sql) · [Post-publication inspection](../../sql/conflicting_specialties_debug.sql)

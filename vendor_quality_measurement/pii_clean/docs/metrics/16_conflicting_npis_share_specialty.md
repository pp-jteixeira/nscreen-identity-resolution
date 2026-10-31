# Conflicting NPIs share an NPPES specialty

**Status:** published in canonical snapshot `8811920360682490090`, verified October 31, 2026.

**Question:** does another NPI in this record’s conflict context share an exact recognized NPPES taxonomy code? Vendor-reported specialty and profession are not compared. Separate published metrics `conflicting_npis_share_vendor_specialty` and `conflicting_npis_share_vendor_profession` compare vendor labels.

**Target:** `conflicting_npis_share_nppes_specialty`, `specialty_code_values`, `specialty_reference_table`, `specialty_definition_version`, `conflicting_npi_specialty_comparisons` in `iceberg.jteixeira_ipa.pii__int_<vendor>__metrics` and `iceberg.jteixeira_ipa.pii_clean`. Key: `source`, `metric_row_id`.

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

## Real examples

Executed October 31, 2026, against canonical snapshot `8811920360682490090`. These selected cases explain outcomes; they do not measure prevalence.

[Executed example SQL](../../sql/examples/16_conflicting_npis_share_specialty.sql):

```sql
WITH selected AS (
    SELECT *
    FROM iceberg.jteixeira_ipa.pii_clean FOR VERSION AS OF 8811920360682490090
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
       m.conflicting_npis_share_nppes_specialty AS shares_specialty
FROM selected m
ORDER BY m.source, m.metric_row_id
```

| source | email | npi | peer_npi | own_values | peer_values | conflict | shares_specialty |
|---|---|---|---|---|---|---|---|
| endato | cmizelle@att.net | 1114929445 | 1922090380 | [363L00000X, 367A00000X] | [363LP0200X] | true | false |
| endato | mish16a@collegeclub.com | 1851550107 | 1083841183 | [225100000X] | [225100000X] | true | true |
| endato | ramboleymah@gmail.com | 1902846181 | 1346316783 | [] | [163W00000X] | true | NULL |
| haymarket | robinljones99@hotmail.com | 1215221387 | NULL | [] | NULL | false | NULL |

**What differentiates these cases:** A known shared value gives true; known disjoint evidence gives false. With an established conflict, missing evidence leaves NULL. Without a conflict, NULL is not applicable. `363L00000X` and `363LP0200X` do not match despite the shared prefix. Taxonomy codes must overlap exactly. Similar labels or broad specialty groups are insufficient, and empty code sets are unknown.

## Statistics by source

Measured **October 31, 2026** from `iceberg.jteixeira_ipa.pii_clean` snapshot `8811920360682490090`. These are exact published-population counts across retained eligible history, not a sample. Stored evaluation dates remain unchanged.

[Executed statistics SQL 1](../../sql/statistics/16_conflicting_npis_share_specialty.sql) · [Executed statistics SQL 2](../../sql/statistics/16_conflicting_npis_share_specialty_statement_002.sql)

| Source | Usable evidence / all records, n (%) | Conflict records | Shared, n (%) | Disjoint, n (%) | Unknown, n (%) |
|---|---|---|---|---|---|
| HealthLink | 11,140,518 (99.861079%) | 0 | 0 (—) | 0 (—) | 0 (—) |
| QuantumMedica | 1,697,632 (99.525656%) | 56 | 8 (14.285714%) | 48 (85.714286%) | 0 (0.000000%) |
| Medscape | 46,764,639 (99.152481%) | 46 | 8 (17.391304%) | 34 (73.913043%) | 4 (8.695652%) |
| Endato | 5,238,071 (96.510559%) | 194,982 | 21,991 (11.278477%) | 157,786 (80.923367%) | 15,205 (7.798156%) |
| RocketReach | 4,757,453 (97.806562%) | 96,287 | 16,044 (16.662686%) | 73,947 (76.798529%) | 6,296 (6.538785%) |
| DRDB | 1,056,015 (94.674628%) | 22,404 | 1,978 (8.828781%) | 17,642 (78.744867%) | 2,784 (12.426352%) |
| Haymarket | 4,040,009 (95.661251%) | 0 | 0 (—) | 0 (—) | 0 (—) |

Coverage uses all metric records. Shared/disjoint/unknown percentages use established conflict records. Zero-conflict percentages are undefined (—). Distinct-link outcomes can overlap across records and must not be added.

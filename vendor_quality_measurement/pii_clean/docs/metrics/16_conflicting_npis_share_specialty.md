# Conflicting NPIs share an NPPES specialty

**Question:** does another NPI in this link’s conflict context share an exact recognized NPPES taxonomy code? Vendor-reported specialty and profession are not compared. Separate published metrics `conflicting_npis_share_vendor_specialty` and `conflicting_npis_share_vendor_profession` compare vendor labels.

**Target:** `conflicting_npis_share_nppes_specialty`, `specialty_code_values`, `specialty_reference_table`, `specialty_definition_version`, `conflicting_npi_specialty_comparisons` in `iceberg.jteixeira_ipa.pii__int_<vendor>__metrics` and `iceberg.jteixeira_ipa.pii_clean`. One row per source/email/NPI link; key: `source`, `link_id`.

## How it is computed

Join the link's `npi` to text-converted `iceberg.npi.nppes_npidata_latest.npi`. Read `healthcare_provider_taxonomy_code_1` through `_15`. Trim, uppercase, validate against `iceberg.npi.npi_taxonomy.code`, and deduplicate per NPI. Include all slots without preferring primary flags. Vendor specialty labels and broad classification names are not substituted. Taxonomy evidence depends only on the NPI, so every version of a link shares it.

Compare other NPIs within vendor/email on exact overlapping `conflict_days`; Endato, RocketReach and both DRDB feeds use undated vendor contexts, so every other NPI of the email is a peer. Simplified peer expression:

```sql
CASE WHEN cardinality(specialty_code_values) > 0
          AND cardinality(peer.specialties) > 0
     THEN arrays_overlap(specialty_code_values, peer.specialties)
END AS shares_specialty
```

Any match gives true. False requires known disjoint retained sets for every peer. Otherwise null means missing evidence, unknown timing or inapplicable conflict. Preserve peer NPIs, dates, code sets and intersections. Lookup aggregation preserves link grain. This metric has no `_latest` form.

Current NPPES evidence is not aligned to historical vendor dates. Disjoint codes do not prove clinically unrelated providers; shared codes do not establish email ownership.

## Real examples

No executed examples exist yet for this definition.

**What differentiates outcomes:** A known shared value gives true; known disjoint evidence gives false. With an established conflict, missing evidence leaves NULL. Without a conflict, NULL is not applicable. Taxonomy codes must overlap exactly: `363L00000X` and `363LP0200X` do not match despite the shared prefix. Similar labels or broad specialty groups are insufficient, and empty code sets are unknown.

## Statistics by source

No measurements exist yet for this definition.

[Statistics SQL 1](../../sql/statistics/16_conflicting_npis_share_specialty.sql) · [Statistics SQL 2](../../sql/statistics/16_conflicting_npis_share_specialty_statement_002.sql)

Coverage uses all links. Shared/disjoint/unknown percentages use links with an established conflict. Zero-conflict percentages are undefined (—).

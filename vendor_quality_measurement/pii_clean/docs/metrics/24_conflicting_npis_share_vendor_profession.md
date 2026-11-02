# 24. Conflicting NPIs share vendor profession

**Question:** does another NPI reported for the same vendor/email share a vendor profession on an eligible conflict date?

## How it is computed

Read `profession` from `iceberg.thirdparty.quantummedica_hcpmeta` and `iceberg.thirdparty.medscape_pii_meta_global`. Match NPI and exact delivery day; Medscape additionally matches registration `guid`, joining each GUID of the link only on that GUID's own observed days. Collapse duplicate metadata groups before joining. Missing metadata preserves the link with empty evidence arrays.

Normalize case and whitespace using the same rules as [vendor specialty](23_conflicting_npis_share_vendor_specialty.md). Unknown/unspecified placeholders, `OTHER` and CSV header labels are unusable. HealthLink provider-type codes and credentials, RocketReach job titles, NPPES entity types and specialty names do not supply fallback professions.

```sql
CASE WHEN cardinality(own_values) > 0 AND cardinality(peer_values) > 0
     THEN arrays_overlap(own_values, peer_values)
END AS shares_profession
```

Compare only different NPIs for the same vendor/email and actual conflict date. Any exact normalized overlap gives true. False requires all eligible comparisons to have usable disjoint values. Missing profession evidence, unknown timing or no applicable conflict gives NULL. The result is one value per link across all its days, versions and GUIDs; it has no `_latest` form. A shared broad profession does not prove shared identity or email ownership.

**Illustrative example:** two conflicting NPIs labelled `Physician` share profession even when their specialties differ. `Physician` and `Nurse/Advanced Practice Nurse` are disjoint labels. Credentials such as `MD` are not mapped to `Physician`.

`conflicting_npis_share_vendor_profession` retains `source_vendor_profession_values` and `conflicting_npi_vendor_profession_comparisons`. Shared `vendor_professional_evidence` preserves raw labels, normalized labels, delivery dates and source tables; its definition version identifies the comparison rules.

## Real examples

No executed examples exist yet for this definition.

**What differentiates outcomes:** two conflicting NPIs can share a profession even when their specialty labels differ. Known disjoint professions on a shared conflict day give false. An established conflict without usable profession labels remains NULL, and a link without an established conflict is NULL because the comparison is not applicable.

## Statistics by source

No measurements exist yet for this definition.

[Statistics SQL](../../sql/statistics/24_conflicting_npis_share_vendor_profession.sql)

Label coverage uses all links. Outcome percentages use only links with an established conflict. Zero-conflict percentages are undefined (—), not measured zero agreement. Only Medscape and QuantumMedica have a supported profession field. Unsupported sources do not acquire fallback professions.

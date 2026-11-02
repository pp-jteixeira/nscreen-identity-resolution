# 23. Conflicting NPIs share vendor specialty

**Question:** does another NPI reported for the same vendor/email share a vendor specialty on an eligible conflict date?

## How it is computed

HealthLink uses `iceberg.thirdparty.healthlink_hcp.specialty`, joined by NPI and exact delivery day. QuantumMedica uses the three specialty slots in `iceberg.thirdparty.quantummedica_hcpmeta`, also by NPI/day. Medscape uses those slots in `iceberg.thirdparty.medscape_pii_meta_global`, matching NPI, day and registration `guid`; each GUID of the link is joined only on that GUID's own observed days. Both DRDB feeds use the raw `specialty` labels of all versions of the undated link. Endato, RocketReach and Haymarket have no supported specialty input.

Trim, uppercase and collapse whitespace. Exclude blanks, nulls, unknown/unspecified placeholders, `OTHER`, and CSV column-header labels. Preserve punctuation and compare whole labels exactly; no synonym mapping, hierarchy expansion or delimiter splitting occurs. Raw labels remain in `vendor_professional_evidence`.

```sql
CASE WHEN cardinality(own_values) > 0 AND cardinality(peer_values) > 0
     THEN arrays_overlap(own_values, peer_values)
END AS shares_specialty
```

Compare different NPIs within source/email on the same actual conflict date. DRDB uses its available undated snapshot. Any matching peer/date gives true. False requires every comparison to be known and disjoint. Missing values or same-day metadata, unknown timing and no applicable conflict remain NULL. Metadata duplicates collapse before joining; no links are removed or multiplied. The result is one value per link across all its days, versions and GUIDs; it has no `_latest` form.

**Illustrative example:** ` family medicine ` matches `FAMILY MEDICINE`; `Cardiology` does not match `Internal Medicine/Cardiology`. Matching labels on different dates do not establish overlap.

`conflicting_npis_share_vendor_specialty` is accompanied by `source_vendor_specialty_values`, day-specific `vendor_professional_evidence`, `conflicting_npi_vendor_specialty_comparisons` and `vendor_professional_definition_version`. `source_vendor_specialty_values` is the display union across the link's observation days, versions and GUIDs; it never replaces date-specific comparison inputs. Each comparison entry identifies the peer by `npi` and `link_id`.

## Real examples

No executed examples exist yet for this definition.

**What differentiates outcomes:** known disjoint labels on a shared conflict day give false; a shared label gives true. An established conflict whose peer has no usable specialty labels remains NULL, and a link without an established conflict is NULL because the comparison is not applicable. DRDB compares its undated links; their NULL evidence day does not invent chronology.

## Statistics by source

No measurements exist yet for this definition.

[Statistics SQL](../../sql/statistics/23_conflicting_npis_share_vendor_specialty.sql)

Label coverage uses all links. Outcome percentages use only links with an established conflict. Zero-conflict percentages are undefined (—), not measured zero agreement. Endato, RocketReach and Haymarket have no supported specialty labels, so their conflicts remain unknown.

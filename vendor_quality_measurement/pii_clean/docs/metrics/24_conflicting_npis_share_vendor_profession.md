# 24. Conflicting NPIs share vendor profession

**Status:** published in canonical snapshot `8811920360682490090`, verified October 31, 2026.

**Question:** does another NPI reported for the same vendor/email share a vendor profession on an eligible conflict date?

## How it is computed

Read `profession` from `iceberg.thirdparty.quantummedica_hcpmeta` and `iceberg.thirdparty.medscape_pii_meta_global`. Match NPI and exact delivery day; Medscape additionally matches registration `guid`. Collapse duplicate metadata groups before joining. Missing metadata preserves the attribution row with empty evidence arrays.

Normalize case and whitespace using the same rules as [vendor specialty](23_conflicting_npis_share_vendor_specialty.md). Unknown/unspecified placeholders, `OTHER` and CSV header labels are unusable. HealthLink provider-type codes and credentials, RocketReach job titles, NPPES entity types and specialty names do not supply fallback professions.

```sql
CASE WHEN cardinality(own_values) > 0 AND cardinality(peer_values) > 0
     THEN arrays_overlap(own_values, peer_values)
END AS shares_profession
```

Compare only different NPIs for the same vendor/email and actual conflict date. Any exact normalized overlap gives true. False requires all eligible comparisons to have usable disjoint values. Missing profession evidence, unknown timing or no applicable conflict gives NULL. A shared broad profession does not prove shared identity or email ownership.

**Illustrative example:** two conflicting NPIs labelled `Physician` share profession even when their specialties differ. `Physician` and `Nurse/Advanced Practice Nurse` are disjoint labels. Credentials such as `MD` are not mapped to `Physician`.

`conflicting_npis_share_vendor_profession` retains `source_vendor_profession_values` and `conflicting_npi_vendor_profession_comparisons`. Shared `vendor_professional_evidence` preserves raw labels, normalized labels, delivery dates and source tables; its definition version identifies the comparison rules.

## Real examples

Executed October 31, 2026, against canonical snapshot `8811920360682490090`. These selected cases explain outcomes; they do not measure prevalence.

[Executed example SQL](../../sql/examples/24_conflicting_npis_share_vendor_profession.sql):

```sql
-- Display one stored peer comparison consistent with each record's outcome.
WITH selected AS (
    SELECT * FROM iceberg.jteixeira_ipa.pii_clean FOR VERSION AS OF 8811920360682490090
    WHERE (source = 'medscape' AND metric_row_id = '0088DFD5D04310BAA974C6E5FC6193832698547B2CB1DCE2FD1706BDBC90D982')
       OR (source = 'medscape' AND metric_row_id = '1A825CFC0781883F8EE8CD56AEC97ED97B6B6D343985DE7BA61A5C722AA6938E')
       OR (source = 'quantummedica' AND metric_row_id = '000F87BE1EBCB93F92B83E7EF1749A01A14C2B045B4346609AB50B7330A5B5B7')
       OR (source = 'medscape' AND metric_row_id = '000000292E237796D17BEC9BB60DA00A81701AF9AE2B875BF008FEE8FE171D10')
), evidence AS (
    SELECT m.*, element_at(filter(conflicting_npi_vendor_profession_comparisons, x -> x.shares_profession IS NOT DISTINCT FROM conflicting_npis_share_vendor_profession), 1) AS peer
    FROM selected m
)
SELECT source,email,npi,peer.npi AS peer_npi,peer.evidence_day,
       coalesce(peer.own_values,source_vendor_profession_values) AS own_values,peer.peer_values,
       has_conflict_linkage AS conflict,conflicting_npis_share_vendor_profession AS shares_profession
FROM evidence
ORDER BY source,email,npi
```

| source | email | npi | peer_npi | evidence_day | own_values | peer_values | conflict | shares_profession |
|---|---|---|---|---|---|---|---|---|
| medscape | cdknoblauch@comcast.net | 1194772020 | 1851492250 | 2024-02-08 | [PHYSICIAN] | [NURSE/ADVANCED PRACTICE NURSE] | true | false |
| medscape | henryc61@verizon.net | 1053329078 | 1457363186 | 2024-01-10 | [PHYSICIAN] | [PHYSICIAN] | true | true |
| medscape | prestonlurie@verizon.net | 1871571513 | NULL | NULL | [PHYSICIAN] | NULL | false | NULL |
| quantummedica | seema.sidhu@kp.org | 1619938834 | 1497831929 | 2025-09-14 | [] | [] | true | NULL |

`henryc61@verizon.net` shares profession even though its specialty labels differ. `cdknoblauch@comcast.net` has known disjoint professions. `seema.sidhu@kp.org` has an established QuantumMedica conflict but no usable profession labels. `prestonlurie@verizon.net` has no conflict, so its NULL outcome is not applicable.

## Statistics by source

Measured **October 31, 2026** from `iceberg.jteixeira_ipa.pii_clean` snapshot `8811920360682490090`. These are exact published-population counts across retained eligible history, not a sample. Stored evaluation dates remain unchanged.

[Executed statistics SQL](../../sql/statistics/24_conflicting_npis_share_vendor_profession.sql)

| Source | Metric records | Usable labels, n (%) | Conflict records | Shared, n (%) | Disjoint, n (%) | Unknown, n (%) |
|---|---|---|---|---|---|---|
| HealthLink | 11,156,016 | 0 (0.000000%) | 0 | 0 (—) | 0 (—) | 0 (—) |
| QuantumMedica | 1,705,723 | 0 (0.000000%) | 56 | 0 (0.000000%) | 0 (0.000000%) | 56 (100.000000%) |
| Medscape | 47,164,366 | 47,164,319 (99.999900%) | 46 | 41 (89.130435%) | 5 (10.869565%) | 0 (0.000000%) |
| Endato | 5,427,459 | 0 (0.000000%) | 194,982 | 0 (0.000000%) | 0 (0.000000%) | 194,982 (100.000000%) |
| RocketReach | 4,864,145 | 0 (0.000000%) | 96,287 | 0 (0.000000%) | 0 (0.000000%) | 96,287 (100.000000%) |
| DRDB | 1,115,415 | 0 (0.000000%) | 22,404 | 0 (0.000000%) | 0 (0.000000%) | 22,404 (100.000000%) |
| Haymarket | 4,223,245 | 0 (0.000000%) | 0 | 0 (—) | 0 (—) | 0 (—) |

Label coverage uses all metric records. Outcome percentages use only established conflict records. Zero-conflict percentages are undefined (—), not measured zero agreement. Distinct-link outcomes can overlap across raw record variants and must not be summed. Only Medscape has usable profession labels in this publication. QuantumMedica supports a metadata profession field, but its retained values provide no usable normalized labels; all 56 conflict records therefore remain unknown. Unsupported sources do not acquire fallback professions.

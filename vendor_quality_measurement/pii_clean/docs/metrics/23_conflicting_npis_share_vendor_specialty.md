# 23. Conflicting NPIs share vendor specialty

**Status:** published in canonical snapshot `8811920360682490090`, verified October 31, 2026.

**Question:** does another NPI reported for the same vendor/email share a vendor specialty on an eligible conflict date?

## How it is computed

HealthLink uses `iceberg.thirdparty.healthlink_hcp.specialty`, joined by NPI and exact delivery day. QuantumMedica uses the three specialty slots in `iceberg.thirdparty.quantummedica_hcpmeta`, also by NPI/day. Medscape uses those slots in `iceberg.thirdparty.medscape_pii_meta_global`, matching NPI, day and registration `guid`. Both DRDB feeds use `specialty` on the original undated record. Endato, RocketReach and Haymarket have no supported specialty input.

Trim, uppercase and collapse whitespace. Exclude blanks, nulls, unknown/unspecified placeholders, `OTHER`, and CSV column-header labels. Preserve punctuation and compare whole labels exactly; no synonym mapping, hierarchy expansion or delimiter splitting occurs. Raw labels remain in `vendor_professional_evidence`.

```sql
CASE WHEN cardinality(own_values) > 0 AND cardinality(peer_values) > 0
     THEN arrays_overlap(own_values, peer_values)
END AS shares_specialty
```

Compare different NPIs within source/email on the same actual conflict date. DRDB uses its available undated snapshot. Any matching peer/date gives true. False requires every comparison to be known and disjoint. Missing values or same-day metadata, unknown timing and no applicable conflict remain NULL. Metadata duplicates collapse before joining; no attribution rows are removed or multiplied.

**Illustrative example:** ` family medicine ` matches `FAMILY MEDICINE`; `Cardiology` does not match `Internal Medicine/Cardiology`. Matching labels on different dates do not establish overlap.

`conflicting_npis_share_vendor_specialty` is accompanied by `source_vendor_specialty_values`, day-specific `vendor_professional_evidence`, `conflicting_npi_vendor_specialty_comparisons` and `vendor_professional_definition_version`. The display union across observation days never replaces date-specific comparison inputs.

## Real examples

Executed October 31, 2026, against canonical snapshot `8811920360682490090`. These selected cases explain outcomes; they do not measure prevalence.

[Executed example SQL](../../sql/examples/23_conflicting_npis_share_vendor_specialty.sql):

```sql
-- Display one stored peer comparison consistent with each record's outcome.
WITH selected AS (
    SELECT * FROM iceberg.jteixeira_ipa.pii_clean FOR VERSION AS OF 8811920360682490090
    WHERE (source = 'medscape' AND metric_row_id = '0B30EEBFE013B2D090F8D9018874F7013FA03BA19601857CAA925008050B3DF2')
       OR (source = 'medscape' AND metric_row_id = '0088DFD5D04310BAA974C6E5FC6193832698547B2CB1DCE2FD1706BDBC90D982')
       OR (source = 'medscape' AND metric_row_id = '854C681B0D4745D53A0B633CE658FEC97BC323DB8EF45516A8AA30C0B3556099')
       OR (source = 'medscape' AND metric_row_id = '000000292E237796D17BEC9BB60DA00A81701AF9AE2B875BF008FEE8FE171D10')
       OR (source = 'drdb' AND metric_row_id = '0008D8852D81B2FD4A1FA38F8361BCC927C5550E747F3ECF86E7D823D9997911')
), evidence AS (
    SELECT m.*, element_at(filter(conflicting_npi_vendor_specialty_comparisons, x -> x.shares_specialty IS NOT DISTINCT FROM conflicting_npis_share_vendor_specialty), 1) AS peer
    FROM selected m
)
SELECT source,email,npi,peer.npi AS peer_npi,peer.evidence_day,
       coalesce(peer.own_values,source_vendor_specialty_values) AS own_values,peer.peer_values,
       has_conflict_linkage AS conflict,conflicting_npis_share_vendor_specialty AS shares_specialty
FROM evidence
ORDER BY source,email,npi
```

| source | email | npi | peer_npi | evidence_day | own_values | peer_values | conflict | shares_specialty |
|---|---|---|---|---|---|---|---|---|
| drdb | jsullivan8@yahoo.com | 1730161308 | 1730179607 | NULL | [INTERNAL MEDICINE] | [INTERNAL MEDICINE] | true | true |
| medscape | henryc61@verizon.net | 1053329078 | 1457363186 | 2024-01-10 | [INTERNAL MEDICINE] | [OB/GYN & WOMEN'S HEALTH] | true | false |
| medscape | planterstrail@gmail.com | 1275572547 | 1114168358 | 2024-02-08 | [NEUROLOGY] | [NEUROLOGY] | true | true |
| medscape | prestonlurie@verizon.net | 1871571513 | NULL | NULL | [] | NULL | false | NULL |
| medscape | vlravenna@gmail.com | 243683 | 1689988784 | 2024-01-10 | [HIV/AIDS] | [] | true | NULL |

`henryc61@verizon.net` has known disjoint specialty labels. `planterstrail@gmail.com` has a shared specialty. `vlravenna@gmail.com` has an established conflict but its peer has no usable specialty labels. Its malformed stored NPI is a separate identifier-quality issue. `prestonlurie@verizon.net` has no established conflict, so NULL means not applicable. The DRDB example compares its available undated records; its NULL evidence day does not invent chronology.

## Statistics by source

Measured **October 31, 2026** from `iceberg.jteixeira_ipa.pii_clean` snapshot `8811920360682490090`. These are exact published-population counts across retained eligible history, not a sample. Stored evaluation dates remain unchanged.

[Executed statistics SQL](../../sql/statistics/23_conflicting_npis_share_vendor_specialty.sql)

| Source | Metric records | Usable labels, n (%) | Conflict records | Shared, n (%) | Disjoint, n (%) | Unknown, n (%) |
|---|---|---|---|---|---|---|
| HealthLink | 11,156,016 | 9,784,413 (87.705261%) | 0 | 0 (—) | 0 (—) | 0 (—) |
| QuantumMedica | 1,705,723 | 1,705,722 (99.999941%) | 56 | 8 (14.285714%) | 48 (85.714286%) | 0 (0.000000%) |
| Medscape | 47,164,366 | 42,395,100 (89.887989%) | 46 | 13 (28.260870%) | 31 (67.391304%) | 2 (4.347826%) |
| Endato | 5,427,459 | 0 (0.000000%) | 194,982 | 0 (0.000000%) | 0 (0.000000%) | 194,982 (100.000000%) |
| RocketReach | 4,864,145 | 0 (0.000000%) | 96,287 | 0 (0.000000%) | 0 (0.000000%) | 96,287 (100.000000%) |
| DRDB | 1,115,415 | 1,115,415 (100.000000%) | 22,404 | 6,374 (28.450277%) | 16,030 (71.549723%) | 0 (0.000000%) |
| Haymarket | 4,223,245 | 0 (0.000000%) | 0 | 0 (—) | 0 (—) | 0 (—) |

Label coverage uses all metric records. Outcome percentages use only established conflict records. Zero-conflict percentages are undefined (—), not measured zero agreement. Distinct-link outcomes can overlap across raw record variants and must not be summed. HealthLink has usable specialty labels but no same-day conflicts in this population. Endato and RocketReach conflicts remain unknown because those sources have no supported specialty labels.

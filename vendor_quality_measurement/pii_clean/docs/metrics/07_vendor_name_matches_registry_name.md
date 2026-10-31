# Vendor name matches registry name

**Question:** do a vendor-supplied name and a registry name for the same NPI agree under fuzzy comparison? Agreement does not prove they identify the same person.

**Where:** `vendor_name_matches_registry_name` in `iceberg.jteixeira_ipa.pii__int_<vendor>__metrics`; key: `source`, `metric_row_id`. Vendors: `healthlink`, `quantummedica`, `medscape`, `endato`, `rocketreach`, `drdb`, `haymarket`. Vendor [name inputs](../00_source_map.md#name-comparison-inputs) join the [registry name pairs](../../models/intermediate/int_npi__names.sql) by trimmed NPI.

## How it is computed

Compare normalized first and last names separately. Both parts must agree:

- First names: exact names, a shared space-separated token, a first-token prefix of at least three characters, overlapping nickname expansions, or allowed edits.
- Last names: equal letters-only forms, a shared space/hyphen-separated token, or allowed edits.
- Allowed edits: at most one when both parts have at least five letters; at most two when both have at least eight. These lengths apply to the compared name parts, not the email.

For each name pair, `fk` and `lk` are the first- and last-name match classes (`none` means disagreement). Missing usable names produce null. Aggregate comparisons within `source`, `metric_row_id`:

```sql
CASE WHEN source_name_usable AND registry_name_usable
     THEN fk <> 'none' AND lk <> 'none'
END AS vendor_registry_match
```

```sql
bool_or(vendor_registry_match) AS vendor_name_matches_registry_name
```

Any qualifying pair gives true; usable comparisons without a match give false; all-null comparisons stay unknown. Usability requires one first-name letter and two last-name letters. Names from different records are never combined.

**Limits:** common names, shared tokens and broad nickname mappings can produce false matches. Only this record’s vendor name and current readable registry variants contribute; HealthLink uses its separate HCP reference; no historical as-of alignment is implied. Endato compares its returned person's name, not the NPI-holder name supplied as input. No score or filtering is applied.

## Real examples

Executed October 31, 2026, against canonical snapshot `8811920360682490090`. These selected cases explain outcomes; they do not measure prevalence. Registry-name displays additionally use the current readable name view; those names are not snapshot-pinned with the stored indicators.

[Executed example SQL](../../sql/examples/07_vendor_name_matches_registry_name.sql):

```sql
SELECT DISTINCT
    m.source,
    m.npi,
    concat(s.first_name, ' ', s.last_name) AS vendor_name,
    concat(r.first_name, ' ', r.last_name) AS registry_name,
    m.source_name_usable,
    m.registry_name_usable,
    m.vendor_name_matches_registry_name AS matches
FROM iceberg.jteixeira_ipa.pii_clean FOR VERSION AS OF 8811920360682490090 m
LEFT JOIN UNNEST(m.source_name_values)
    AS s(first_name, last_name, first_variants) ON true
LEFT JOIN iceberg.jteixeira_ipa.pii__int_npi__names r ON m.npi = r.npi
WHERE m.source = 'endato'
  AND m.metric_row_id IN (
      '06AB31EC5574E57D8BB1D4D59458B398E5389AD406E98827B2DC8823A8DB5763',
      '001632ED6AB8E6E8E2C8D203E1988812E3F950707428DBA8D78289AB202A87CC',
      '00B93621FC5F2483F73C12B32DECBAD80480445C3CD407F0322BFF1A8E12D2B7',
      '0266F98E9735CB80EDAF62E5EAB302C958544CDFD4E70512AC1EFC7DAFCA7898',
      '5E463BFBBFA7821EA11FD393E13084C53B86EE3F55799BD657C9040A7F8E7460',
      '0457353A2653E64F33BC90E1AA0FC845139B0055EEAAD8FF6E861054D7751091',
      '01F2DBC4D54F8DCB79678C8F5AC82F7828B0EFC6ECBFC06DB1E15FE592682357'
  )
ORDER BY m.npi
```

| source | npi | vendor_name | registry_name | source_name_usable | registry_name_usable | matches |
|---|---|---|---|---|---|---|
| endato | 1104097450 | HYUNSUK KIM | HYUN KIM | true | true | true |
| endato | 1205977915 | MARY CHANG | NULL | true | false | NULL |
| endato | 1255544516 | NULL | RONALD CHENG | false | true | NULL |
| endato | 1770915233 | MITCHELL EATON | MICHELLE EATON | true | true | true |
| endato | 1821316597 | SARAH HAJJAJI | SARAH NAJJAR | true | true | false |
| endato | 1922088731 | JIM OGBURN | JAMES OGBURN | true | true | true |
| endato | 1952426611 | BLANCA PYLE | BLANCA PYLE | true | true | true |

**What differentiates these cases:**

- **Exact versus fuzzy agreement:** BLANCA PYLE matches exactly. JIM/JAMES matches through nickname expansions. HYUN/HYUNSUK matches through a four-letter first-token prefix. Each also has an exact last-name match.
- **Permissive edit rule:** MITCHELL/MICHELLE has edit distance two. Both first names have eight letters, so the rule accepts this pair with the matching surname EATON. This demonstrates a possible false match, not confirmed shared identity.
- **One matching part is insufficient:** SARAH matches, but HAJJAJI/NAJJAR does not pass the last-name rules. The result is false.
- **Unknown differs from disagreement:** MARY CHANG lacks a usable registry name. The RONALD CHENG record lacks a usable vendor name. Both results are NULL, rather than false.

Registry-name displays use the readable name view at extraction time. Stored match indicators come from the pinned publication.

## Statistics by source

Measured **October 31, 2026** from `iceberg.jteixeira_ipa.pii_clean` snapshot `8811920360682490090`. These are exact published-population counts across retained eligible history, not a sample. Stored evaluation dates remain unchanged.

[Executed statistics SQL](../../sql/statistics/07_vendor_name_matches_registry_name.sql)

| Source | Metric records | Match, n (%) | No match, n (%) | Unknown, n (%) |
|---|---|---|---|---|
| HealthLink | 11,156,016 | 10,528,135 (94.371817%) | 558,098 (5.002664%) | 69,783 (0.625519%) |
| QuantumMedica | 1,705,723 | 0 (0.000000%) | 0 (0.000000%) | 1,705,723 (100.000000%) |
| Medscape | 47,164,366 | 43,869,281 (93.013613%) | 2,600,509 (5.513716%) | 694,576 (1.472671%) |
| Endato | 5,427,459 | 1,279,079 (23.566811%) | 4,103,800 (75.611810%) | 44,580 (0.821379%) |
| RocketReach | 4,864,145 | 4,671,247 (96.034288%) | 140,057 (2.879376%) | 52,841 (1.086337%) |
| DRDB | 1,115,415 | 1,085,065 (97.279040%) | 14,661 (1.314399%) | 15,689 (1.406562%) |
| Haymarket | 4,223,245 | 3,756,468 (88.947433%) | 224,434 (5.314255%) | 242,343 (5.738313%) |

Percentages use all metric records within each source. Categories partition records. Distinct-email outcomes cannot be inferred by adding record counts. Unknown is NULL, not disagreement. Names and outcomes can differ between records sharing an email/NPI.

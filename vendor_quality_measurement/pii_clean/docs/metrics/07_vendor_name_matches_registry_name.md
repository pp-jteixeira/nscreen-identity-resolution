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

**Illustrative examples:**

| Vendor name | Registry name | Result | Reason |
|---|---|---|---|
| ROBERT SMITH | BOB SMITH | `true` | Nickname agreement; last names match. |
| JOHN SMITH-JONES | JOHN SMITH | `true` | First names match; last names share a token. |
| JOHN SMITH | JOHN JONES | `false` | First-name-only agreement is insufficient. |
| Missing | JOHN SMITH | Unknown (`null`) | No usable vendor name to compare. |

**Limits:** common names, shared tokens and broad nickname mappings can produce false matches. Only this record’s vendor name and current readable registry variants contribute; HealthLink uses its separate HCP reference; no historical as-of alignment is implied. Endato compares its returned person's name, not the NPI-holder name supplied as input. No score or filtering is applied.

## Statistics by source

Measured October 29, 2026, on `iceberg.jteixeira_ipa.pii_clean` at exact source-record/email-position grain. Percentages use all metric rows within each vendor. Counts are exact and cover all retained history; email–NPI links remain undeduplicated. These are saved measurements, not live counts.

| Source | Metric rows | Match, n (%) | No match, n (%) | Unknown, n (%) |
|---|---:|---:|---:|---:|
| HealthLink | 11,156,016 | 10,528,135 (94.37182%) | 558,098 (5.00266%) | 69,783 (0.62552%) |
| QuantumMedica | 1,705,723 | 0 (0.00000%) | 0 (0.00000%) | 1,705,723 (100.00000%) |
| Medscape | 47,072,262 | 43,780,904 (93.00786%) | 2,597,143 (5.51735%) | 694,215 (1.47479%) |
| Endato | 5,427,459 | 1,279,079 (23.56681%) | 4,103,800 (75.61181%) | 44,580 (0.82138%) |
| RocketReach | 4,864,145 | 4,671,247 (96.03429%) | 140,057 (2.87938%) | 52,841 (1.08634%) |
| DRDB | 1,115,415 | 1,085,065 (97.27904%) | 14,661 (1.31440%) | 15,689 (1.40656%) |
| Haymarket | 4,223,245 | 3,756,468 (88.94743%) | 224,434 (5.31425%) | 242,343 (5.73831%) |

Unknown is null, not false. Name outcomes can differ across records sharing the same email/NPI. These row counts do not establish distinct-email outcome counts.

Derived row statistics (local-only: `../../results/documentation_row_statistics.json`) · [Executed population SQL](../../results/metric_population_20261029/grouped.sql) · Measurement metadata (local-only: `../../results/metric_population_20261029/analysis_metadata.json`) · Published-table validation (local-only: `../../results/final_build.json`)

[Profile SQL](../../sql/name_match_profile.sql) · [Rule SQL](../../macros/name_matching.sql)

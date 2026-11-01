# Stored name-match evidence

**Published and verified — October 31, 2026.** Seven vendor models retain name-comparison explanations alongside the three existing nullable indicators. Core snapshot `3003274000539755025` has 128 fields, preserving all 75,656,369 records and all 124 original fields. Final snapshot `4233051104478921549` has 158 fields across all seven sources. Source-scoped cookie enrichment preserved every core field. Class statistics and examples below come from that verified core.

## Grain and contents

The key remains `(source, metric_row_id)`: one exact source record and email position. `name_match_evidence` is a typed array of distinct comparisons with normalized source/registry first and last names, `first_name_match_kind`, `last_name_match_kind`, `match_class`, and the three comparison-level email/source, email/registry and vendor/registry booleans. `vendor_registry_match_classes` is the sorted distinct set of classes. `name_match_evaluated_at` records evaluation time; `name_match_definition_version` is `stored_name_comparisons_v1`.

The existing name join supplies these comparisons inside each vendor's `name_metrics` CTE. They are aggregated before joining back to metric records. No additional reference join or model is introduced. All usable source-name pairs are retained. When none exist, source names are represented as null and comparisons remain `unknown`; raw names from email-bearing records remain in `record_payload`. HealthLink names come from its separate HCP reference and are not copied into the email payload. Unusable source names alongside usable names do not add redundant unknown comparisons. Missing or unusable registry variants remain explicit, even alongside a matching reference variant.

No best-match winner is selected. Repeated identical comparisons collapse, while distinct matching, partial and disagreeing comparisons remain. A record with classes `[exact, last_only]` still has `vendor_name_matches_registry_name = true`; its disagreeing comparison remains available. Array size measures distinct comparisons, not independent confirmations.

## Class rules

| Class | Meaning | Vendor/registry boolean |
|---|---|---|
| `exact` | Both parts agree exactly under the existing normalization rules. | true |
| `nickname` | First-name nickname expansions overlap; neither part requires an edit. | true |
| `token` | Shared tokens or a permitted first-token prefix establish agreement; no nickname/edit takes priority. | true |
| `edit` | Both parts agree, with at least one using the allowed edit-distance rule. | true |
| `first_only` | First names agree; last names disagree. | false |
| `last_only` | Last names agree; first names disagree. | false |
| `none` | Neither part agrees. | false |
| `unknown` | At least one complete usable name pair is missing. | null |

For complete agreements, precedence is edit, nickname, token, exact. Component kinds preserve the individual reasons. Both kinds become `unknown` when a complete name pair is unusable. First-name prefix matches belong to `token`. Exact last-name comparison uses letters only, so punctuation differences may be exact. [Metric 07](metrics/07_vendor_name_matches_registry_name.md) defines the normalization, nickname and edit boundaries.

The original booleans still aggregate with `bool_or`: any true wins; otherwise any false gives false; all unknown gives null. The [integrity check](../tests/name_match_evidence.sql) reconstructs all three booleans from the stored evidence, verifies classes and component kinds, rejects duplicate/empty comparisons, and checks evaluation metadata.

## Real stored examples

Executed October 31, 2026, against verified core snapshot `3003274000539755025`. Names, component kinds, classes and booleans below come directly from the stored array. No current-registry join is used. [Executed example SQL](../sql/examples/07_name_match_evidence.sql):

```sql
-- Stored name comparisons from the verified core, October 31 2026
SELECT m.source, m.metric_row_id, m.email, m.npi,
       e.source_first_name, e.source_last_name,
       e.registry_first_name, e.registry_last_name,
       e.first_name_match_kind, e.last_name_match_kind, e.match_class,
       e.comparison_vendor_match, m.vendor_name_matches_registry_name AS record_vendor_match,
       m.vendor_registry_match_classes, m.name_match_evaluated_at, m.name_match_definition_version
FROM iceberg.jteixeira_ipa.pii__int_pii__metrics FOR VERSION AS OF 3003274000539755025 m
CROSS JOIN UNNEST(m.name_match_evidence) AS e(
    source_first_name, source_last_name, registry_first_name, registry_last_name,
    first_name_match_kind, last_name_match_kind, match_class,
    email_matches_source_name, email_matches_registry_name, comparison_vendor_match)
WHERE (m.source = 'endato'
  AND m.metric_row_id IN (
      '06AB31EC5574E57D8BB1D4D59458B398E5389AD406E98827B2DC8823A8DB5763',
      '001632ED6AB8E6E8E2C8D203E1988812E3F950707428DBA8D78289AB202A87CC',
      '00B93621FC5F2483F73C12B32DECBAD80480445C3CD407F0322BFF1A8E12D2B7',
      '0266F98E9735CB80EDAF62E5EAB302C958544CDFD4E70512AC1EFC7DAFCA7898',
      '5E463BFBBFA7821EA11FD393E13084C53B86EE3F55799BD657C9040A7F8E7460',
      '0457353A2653E64F33BC90E1AA0FC845139B0055EEAAD8FF6E861054D7751091',
      '01F2DBC4D54F8DCB79678C8F5AC82F7828B0EFC6ECBFC06DB1E15FE592682357',
      '4EECBDD928AADF1D1FDB329664AB8B99D218EB6B4733CDAC63A3BD71F90E18E5',
      'DCB1AB6D00A4FF0F1B7A787BD6341A1240E38F5A55DAFCA2A37CCF506A0BDFD9'
  )) OR (m.source = 'healthlink' AND m.metric_row_id IN (
      '8DC2FAC07EDFFA360BDFDF799686AC1B272A7B36687BFD56F26BC14C3A0CBDEC',
      '68F30A7549648B7914AED7460DD6D63E766331459FC0214B2B131E8704DBC2DA'
  ))
ORDER BY m.npi, m.metric_row_id, e.match_class, e.source_first_name, e.source_last_name,
         e.registry_first_name, e.registry_last_name
```

The nine Endato records cover all eight classes:

| NPI | Vendor name | Registry name | First kind | Last kind | Class | Match |
|---|---|---|---|---|---|---|
| 1104097450 | HYUNSUK KIM | HYUN KIM | token | exact | token | true |
| 1205977915 | MARY CHANG | NULL | unknown | unknown | unknown | NULL |
| 1255544516 | NULL | RONALD CHENG | unknown | unknown | unknown | NULL |
| 1295002285 | LORRA WALDROP | ETHAN TAUB | none | none | none | false |
| 1417306309 | BARBARA BLUTSTEIN | REBEKAH BLUTSTEIN | none | exact | last_only | false |
| 1770915233 | MITCHELL EATON | MICHELLE EATON | edit | exact | edit | true |
| 1821316597 | SARAH HAJJAJI | SARAH NAJJAR | exact | none | first_only | false |
| 1922088731 | JIM OGBURN | JAMES OGBURN | nickname | exact | nickname | true |
| 1952426611 | BLANCA PYLE | BLANCA PYLE | exact | exact | exact | true |

The accepted MITCHELL/MICHELLE edit illustrates why a true boolean alone does not establish strong identity evidence. SARAH HAJJAJI/NAJJAR retains first-name agreement, while BARBARA/REBEKAH BLUTSTEIN retains last-name agreement. Neither establishes a family relationship or the reason for a name difference.

The same query returns four comparisons from two HealthLink records:

| Email | NPI | Vendor name | Registry name | Class | Comparison match | Record match |
|---|---|---|---|---|---|---|
| ramiro@memorialhermann.org | 1063767382 | RAMIRO ECHEVERRI | RAMIRO ECHEVERRY | edit | true | true |
| ramiro@memorialhermann.org | 1063767382 | RAMIRO ECHEVERRY | RAMIRO ECHEVERRY | exact | true | true |
| awattmd1@gmail.com | 1093706145 | ANGELA MAIO | ANGELA MAIO | exact | true | true |
| awattmd1@gmail.com | 1093706145 | ANGELA WATT | ANGELA MAIO | first_only | false | true |

The ANGELA record has classes `[exact, first_only]`. Its aggregate remains true because one comparison agrees, while the disagreeing pair is retained. RAMIRO retains both exact and edit comparisons. HealthLink uses its HCP reference without historical date alignment; these entries are not independent confirmations. The inspection query unfolds comparisons, but each original metric record remains one stored row.

## Statistics and validation

Measured October 31, 2026, from verified core snapshot `3003274000539755025`, containing **75,656,369 records**. Every comparison has `name_match_evaluated_at = 2026-10-31 18:46:11.738 UTC`. [Executed class statistics SQL](../sql/statistics/07_name_match_classes.sql) reads that pinned core. These are record counts, not distinct emails or links. Percentages use all metric records within each source and are rounded to three decimals.

| Source | Metric records | Exact | Nickname | Token | Edit |
|---|---:|---:|---:|---:|---:|
| HealthLink | 11,156,016 | 10,391,264 (93.145%) | 3,498 (0.031%) | 117,876 (1.057%) | 15,516 (0.139%) |
| QuantumMedica | 1,705,723 | 0 (0.000%) | 0 (0.000%) | 0 (0.000%) | 0 (0.000%) |
| Medscape | 47,164,366 | 40,488,902 (85.846%) | 645,330 (1.368%) | 2,619,417 (5.554%) | 115,632 (0.245%) |
| Endato | 5,427,459 | 1,179,897 (21.739%) | 20,063 (0.370%) | 64,849 (1.195%) | 14,270 (0.263%) |
| RocketReach | 4,864,145 | 4,526,928 (93.067%) | 16,025 (0.329%) | 85,081 (1.749%) | 43,213 (0.888%) |
| DRDB | 1,115,415 | 1,077,060 (96.561%) | 92 (0.008%) | 4,762 (0.427%) | 3,151 (0.282%) |
| Haymarket | 4,223,245 | 3,625,470 (85.846%) | 6,209 (0.147%) | 111,469 (2.639%) | 13,320 (0.315%) |

| Source | First only | Last only | Neither part | Unknown |
|---|---:|---:|---:|---:|
| HealthLink | 522,639 (4.685%) | 29,074 (0.261%) | 6,463 (0.058%) | 69,783 (0.626%) |
| QuantumMedica | 0 (0.000%) | 0 (0.000%) | 0 (0.000%) | 1,705,723 (100.000%) |
| Medscape | 1,210,178 (2.566%) | 1,022,532 (2.168%) | 367,799 (0.780%) | 694,576 (1.473%) |
| Endato | 129,049 (2.378%) | 2,246,581 (41.393%) | 1,728,170 (31.841%) | 44,580 (0.821%) |
| RocketReach | 68,762 (1.414%) | 44,904 (0.923%) | 26,391 (0.543%) | 52,841 (1.086%) |
| DRDB | 11,508 (1.032%) | 1,055 (0.095%) | 2,098 (0.188%) | 15,689 (1.407%) |
| Haymarket | 159,536 (3.778%) | 52,269 (1.238%) | 12,629 (0.299%) | 242,343 (5.738%) |

Class counts overlap: **97 HealthLink records** have multiple classes, and **106** have multiple distinct comparison rows. All other sources have one retained comparison/class per record in this snapshot. Do not sum class counts as disjoint populations or treat repeated comparisons as independent confirmations. QuantumMedica's 100% unknown means vendor-to-registry name comparison is unavailable, not that every name disagrees.

Name comparisons were evaluated at `2026-10-31 18:46:11.738 UTC` using NPI-reference snapshot `2149991209070307144`. Stored core snapshot `3003274000539755025` preserves every original indicator, key, source count and prior core field.

The original match/false/unknown counts remain documented in [metric 07](metrics/07_vendor_name_matches_registry_name.md#statistics-by-source). The new breakdown separates, for example, Endato's 41.393% last-name-only agreement from its 31.841% complete disagreement. These frequencies do not establish scoring weights or identity accuracy.

The complete local suite passed 141 tests in 293.70 seconds, including source-scoped cookie publication, adaptive writer retries and the explicit switch from an incomplete name-only backfill. Name fixtures cover all eight classes, duplicate references, multiple reference outcomes, unknown source/registry names, nullable aggregation and rejection of inconsistent evidence. Existing vendor and cookie fixtures verify record grain and field preservation. These run through Trino-to-DuckDB translation. DuckDB does not execute Trino's custom array-sort comparator. Separate native fixtures verified null-containing arrays, all eight classes and the integrity query. All seven vendor definitions passed native validation. Full-population reconstruction found zero differences in the three indicators, usability/presence flags or stored source-name arrays. Core preservation and stored-evidence integrity passed over the complete population. Final checks preserved all 128 core fields, counts and unique keys, and independently validated the recomputed cookie fields.

## Publication and lookup

The complete final publication uses [source-scoped cookie builds](cookie_stage.md) from verified core. Ordinary refreshes use `tools/pipeline.py cookies`. An incomplete name-only backfill can be replaced explicitly with `cookies --replace-name-backfill`, which requires the same verified core snapshot and replaces its marker atomically with the first committed cookie source. Subsequent recovery uses `tools/pipeline.py cookies`.

### Evidence-only upgrade alternative

The [evidence-only publisher](../tools/publish_name_evidence.py) adds these fields to the existing population without rebuilding vendor history or cookies. From the project directory:

```bash
# Read-only checks against pinned core, final and registry snapshots
../../.venv/bin/python tools/publish_name_evidence.py
# Validate, publish to existing tables and refresh the eight affected views
../../.venv/bin/python tools/publish_name_evidence.py --publish
# Resume final publication in bounded batches from an already verified core
../../.venv/bin/python tools/publish_name_evidence.py --publish --final-batches
```

It reconstructs names from stored `source_name_values`, checks all existing name indicators and arrays, and writes the four additions directly into core. It then copies those additions into the existing final records. Checksums, unique keys and source counts must preserve all 124 original core fields and all 154 original final fields, including cookies and `computed_at`. No candidate table is created. A retry can retain an already upgraded core after validating its evidence and original-field preservation. Concurrent snapshot changes stop the run.

With `--final-batches`, sixteen disjoint SHA-256 email buckets copy the same pinned inputs starting with four fixed writer tasks and 32 MB target files by default. Retryable write failures permit six attempts, with writer limits of 4, 4, 2, 2, 1 and 1 and increasing waits capped at 45 seconds. `--batch-writers` sets the initial maximum; `--batch-writers 1` keeps every attempt at one task. Local writer scaling is disabled; each task uses one writer. The first replacement stores the original core/final snapshot pins in the table comment atomically. Final output is partial until all buckets pass checks. On resume, each existing bucket must match expected counts, unique keys and checksums for all 154 original final fields and all 128 core fields before it is skipped. After an uncertain write result, committed data is inspected before retrying an INSERT. Mismatches stop publication. Full-population preservation and global key checks precede completion marking and view refresh.

For a full refresh from source data, use `tools/pipeline.py build --direct`. Ordinary recovery commands require the current core schema; refreshing cookies alone cannot create missing name evidence.

All 158 final columns are published and verified. The [complete email lookup](email_lookup.md) includes the four explanation fields and returns 164 outputs: 158 stored fields plus six helpers. Its SQL is regenerated from the published [final schema](../models/final/schema.yml). The lookup preserves stored evidence and does not recompute name matches.

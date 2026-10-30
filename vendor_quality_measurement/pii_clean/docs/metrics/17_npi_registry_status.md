# NPI registry status

**Status:** published in all seven vendor metric views and `iceberg.jteixeira_ipa.pii_clean` on October 29, 2026. Full candidate integrity, schema and checksum checks passed. [Publication report](../../results/publication_20261029/report.md).

**Question:** what does current NPPES evidence report about this NPI?

**Target:** `npi_registry_status` in `iceberg.jteixeira_ipa.pii__int_<vendor>__metrics` and `iceberg.jteixeira_ipa.pii_clean`. Key: `source`, `metric_row_id`. [Full output reference](../../results/registry_status_summary.md#output-columns).

## How it is computed

Join cleaned record `npi` to text-converted `iceberg.npi.nppes_npidata_latest.npi`. Read `npi_deactivation_date`, `npi_reactivation_date`, `replacement_npi` and `npi_deactivation_reason_code`. Aggregate identical trimmed lifecycle tuples; preserve raw evidence and counts.

Parse dates without discarding malformed evidence:

```sql
try_cast(npi_deactivation_date AS date) AS deactivation_day
```

| Status | Meaning |
|---|---|
| `not_found` | No NPPES match; not proof of invalidity. |
| `unknown` | Unusable or contradictory evidence; inspect reason. |
| `replaced` | Agreed nonself replacement without conflicts. |
| `deactivated` | Latest dated event is deactivation. |
| `reactivated` | Latest dated event is reactivation. |
| `active_as_reported` | Matched record reports no lifecycle events/replacement. |

Uncertainty checks precede replacement and chronology.

Comparison date defaults to Europe/Paris today; `registry_status_as_of_day` fixes evaluation. No historical reconstruction or replacement redirects. Absent deactivation does not independently prove activity.

## Real examples: lifecycle status versus uncertainty

Six selected Endato NPIs show how reported events and uncertainty produce different outcomes. This read-only query was executed on October 30, 2026, against stored columns in `iceberg.jteixeira_ipa.pii_clean`. All six results retain the stored evaluation date **October 29, 2026**. It does not recalculate status from today's NPPES reference. NPIs were chosen for explanation, not prevalence; emails and names are omitted. `DISTINCT` removes repeated copies of the selected evidence across email-position rows.

[Runnable example SQL](../../sql/examples/17_npi_registry_status.sql):

```sql
SELECT DISTINCT
    source,
    npi,
    npi_registry_status AS status,
    npi_registry_deactivation_date AS deactivated_on,
    npi_registry_reactivation_date AS reactivated_on,
    array_distinct(transform(npi_registry_lifecycle_evidence,
        evidence -> evidence.replacement_npi)) AS raw_replacements,
    npi_registry_status_reason AS reason,
    npi_registry_status_as_of_day AS evaluated_on
FROM iceberg.jteixeira_ipa.pii_clean
WHERE source = 'endato'
  AND npi IN ('1215977517', '1295334530', '1376022061',
              '1588945042', '1871599357', '1962620666')
ORDER BY npi
```

**Result:** six rows. All have `evaluated_on = 2026-10-29`; the other seven output columns appear below. `NULL` means absent evidence. `raw_replacements` preserves reported values, including rejected self-replacements; it is a display helper, not the accepted replacement column.

| source | npi | status | deactivated_on | reactivated_on | raw_replacements | reason |
|---|---|---|---|---|---|---|
| endato | `1215977517` | not_found | NULL | NULL | `[]` | no_nppes_record |
| endato | `1295334530` | active_as_reported | NULL | NULL | `[NULL]` | no_deactivation_reported |
| endato | `1376022061` | unknown | 2019-03-25 | 2019-03-25 | `[NULL]` | ambiguous_event_order |
| endato | `1588945042` | deactivated | 2024-04-10 | NULL | `[NULL]` | latest_event_deactivation |
| endato | `1871599357` | reactivated | 2006-03-21 | 2006-04-14 | `[NULL]` | latest_event_reactivation |
| endato | `1962620666` | unknown | 2006-10-25 | 2007-04-20 | `[1962620666]` | self_replacement |

**What differentiates these cases:**

- **Missing reference versus no reported events:** `1215977517` has no matched lifecycle evidence (`[]`). `1295334530` has a matched reference with no reported events (`[NULL]` replacement). Only the latter is `active_as_reported`, which still does not prove current activity.
- **Event chronology versus unresolved order:** `1588945042` has a deactivation without reactivation. `1871599357` has a later reactivation, so it is `reactivated`. Equal dates for `1376022061` cannot establish event order, so it remains `unknown`.
- **Uncertainty takes priority:** `1962620666` has a later reactivation, but reports itself as its replacement. The self-replacement check takes priority, leaving `unknown` rather than `reactivated` or `replaced`. Its accepted `npi_registry_replacement_npi` remains NULL.

No real `replaced` example was observed in the October 29 measurements: all 82 reported reference replacements were self-replacements. Later publications can change these query results.

## Measurements

[Statistics SQL](../../sql/statistics/17_npi_registry_status.sql). These read-only queries aggregate the published evidence columns in `iceberg.jteixeira_ipa.pii_clean`, without rebuilding reference joins. The tables below retain their stated historical measurement times. A later pipeline publication can change query results. Vendor totals and lifecycle outcomes use published records. The separate NPPES availability and self-replacement statements inspect the current raw reference and can differ from the publication snapshot.

All 82/82 replacement values (100%) point to themselves. They remain unknown.

Percentages below use all distinct links within each vendor.

| Vendor | Links | Deactivated, n (%) | Not found, n (%) | Unknown, n (%) |
|---|---:|---:|---:|---:|
| HealthLink | 7,688,451 | 9,938 (0.13%) | 3,415 (0.04%) | 346 (0.00450%) |
| QuantumMedica | 1,705,723 | 8,083 (0.47%) | 8 (0.00047%) | 86 (0.00504%) |
| Medscape | 3,659,306 | 117,978 (3.22%) | 14,900 (0.41%) | 159 (0.00435%) |
| Endato | 5,427,459 | 189,378 (3.49%) | 10 (0.00018%) | 259 (0.00477%) |
| RocketReach | 3,199,535 | 73,265 (2.29%) | 14 (0.00044%) | 171 (0.00534%) |
| DRDB | 826,886 | 42,214 (5.11%) | 5 (0.00060%) | 47 (0.00568%) |
| Haymarket | 4,223,245 | 176,950 (4.19%) | 6,286 (0.15%) | 181 (0.00429%) |

[Per-vendor counts, examples and SQL](../../results/registry_status_summary.md) · Executed measurements (historical output, not retained: `../../results/registry_status_measure.json`) · Replacement check (historical output, not retained: `../../results/registry_status_replacement_check.json`)

[Calculation](../../macros/registry_status.sql) · [Integrity check](../../tests/registry_status.sql) · Native fixtures (historical output, not retained: `../../results/registry_status_native.json`) · Local tests (historical output, not retained: `../../results/registry_status_local_tests.txt`)

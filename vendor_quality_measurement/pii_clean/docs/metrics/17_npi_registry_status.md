# NPI registry status

**Status:** published in canonical snapshot `8811920360682490090`, verified October 31, 2026.

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

## Real examples

Executed October 31, 2026, against canonical snapshot `8811920360682490090`. These selected cases explain outcomes; they do not measure prevalence.

[Executed example SQL](../../sql/examples/17_npi_registry_status.sql):

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
FROM iceberg.jteixeira_ipa.pii_clean FOR VERSION AS OF 8811920360682490090
WHERE source = 'endato'
  AND npi IN ('1215977517', '1295334530', '1376022061',
              '1588945042', '1871599357', '1962620666')
ORDER BY npi
```

| source | npi | status | deactivated_on | reactivated_on | raw_replacements | reason | evaluated_on |
|---|---|---|---|---|---|---|---|
| endato | 1215977517 | not_found | NULL | NULL | [] | no_nppes_record | 2026-10-30 |
| endato | 1295334530 | active_as_reported | NULL | NULL | [NULL] | no_deactivation_reported | 2026-10-30 |
| endato | 1376022061 | unknown | 2019-03-25 | 2019-03-25 | [NULL] | ambiguous_event_order | 2026-10-30 |
| endato | 1588945042 | deactivated | 2024-04-10 | NULL | [NULL] | latest_event_deactivation | 2026-10-30 |
| endato | 1871599357 | reactivated | 2006-03-21 | 2006-04-14 | [NULL] | latest_event_reactivation | 2026-10-30 |
| endato | 1962620666 | unknown | 2006-10-25 | 2007-04-20 | [1962620666] | self_replacement | 2026-10-30 |

**What differentiates these cases:**

- **Missing reference versus no reported events:** `1215977517` has no matched lifecycle evidence (`[]`). `1295334530` has a matched reference with no reported events (`[NULL]` replacement). Only the latter is `active_as_reported`, which still does not prove current activity.
- **Event chronology versus unresolved order:** `1588945042` has a deactivation without reactivation. `1871599357` has a later reactivation, so it is `reactivated`. Equal dates for `1376022061` cannot establish event order, so it remains `unknown`.
- **Uncertainty takes priority:** `1962620666` has a later reactivation, but reports itself as its replacement. The self-replacement check takes priority, leaving `unknown` rather than `reactivated` or `replaced`. Its accepted `npi_registry_replacement_npi` remains NULL.

## Statistics by source

Measured **October 31, 2026** from `iceberg.jteixeira_ipa.pii_clean` snapshot `8811920360682490090`. These are exact published-population counts across retained eligible history, not a sample. Stored evaluation dates remain unchanged.

[Executed statistics SQL 1](../../sql/statistics/17_npi_registry_status_statement_002.sql) · [Executed statistics SQL 2](../../sql/statistics/17_npi_registry_status_statement_003.sql)

| Source | Metric records | active_as_reported, n (%) | not_found, n (%) | deactivated, n (%) | reactivated, n (%) | unknown, n (%) | replaced, n (%) |
|---|---|---|---|---|---|---|---|
| HealthLink | 11,156,016 | 11,109,756 (99.585336%) | 3,415 (0.030611%) | 12,083 (0.108309%) | 30,263 (0.271271%) | 499 (0.004473%) | 0 (0.000000%) |
| QuantumMedica | 1,705,723 | 1,692,741 (99.238915%) | 8 (0.000469%) | 8,083 (0.473875%) | 4,805 (0.281699%) | 86 (0.005042%) | 0 (0.000000%) |
| Medscape | 47,164,366 | 46,657,938 (98.926249%) | 59,354 (0.125845%) | 340,373 (0.721674%) | 104,408 (0.221371%) | 2,293 (0.004862%) | 0 (0.000000%) |
| Endato | 5,427,459 | 5,227,039 (96.307296%) | 10 (0.000184%) | 189,378 (3.489257%) | 10,773 (0.198491%) | 259 (0.004772%) | 0 (0.000000%) |
| RocketReach | 4,864,145 | 4,745,762 (97.566212%) | 25 (0.000514%) | 106,667 (2.192924%) | 11,430 (0.234985%) | 261 (0.005366%) | 0 (0.000000%) |
| DRDB | 1,115,415 | 1,052,613 (94.369629%) | 6 (0.000538%) | 59,394 (5.324834%) | 3,336 (0.299082%) | 66 (0.005917%) | 0 (0.000000%) |
| Haymarket | 4,223,245 | 4,030,766 (95.442391%) | 6,286 (0.148843%) | 176,950 (4.189906%) | 9,062 (0.214574%) | 181 (0.004286%) | 0 (0.000000%) |

Percentages use all metric records within each source. Stored classifications preserve their evaluation dates; extraction does not reread NPPES or infer historical activity. `active_as_reported` is not proof of current clinical activity. The independent raw-reference diagnostics remain separate from these published-population statistics.

# NPI registry status

**Question:** what does current NPPES evidence report about this NPI?

**Target:** `npi_registry_status` in `iceberg.jteixeira_ipa.pii__int_<vendor>__metrics` and `iceberg.jteixeira_ipa.pii_clean`. One row per source/email/NPI link; key: `source`, `link_id`. [Full output reference](../../results/registry_status_summary.md#output-columns).

## How it is computed

Join the link's cleaned `npi` to text-converted `iceberg.npi.nppes_npidata_latest.npi`. Read `npi_deactivation_date`, `npi_reactivation_date`, `replacement_npi` and `npi_deactivation_reason_code`. Aggregate identical trimmed lifecycle tuples; preserve raw evidence and counts.

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

No executed examples exist yet for this definition.

**What differentiates outcomes:**

- **Missing reference versus no reported events:** an NPI without matched lifecycle evidence has an empty evidence array and status `not_found`. A matched reference with no reported events is `active_as_reported`, which still does not prove current activity.
- **Event chronology versus unresolved order:** a deactivation without a later reactivation is `deactivated`; a later reactivation gives `reactivated`. Equal event dates cannot establish order, so the status remains `unknown`.
- **Uncertainty takes priority:** an NPI that reports itself as its replacement is `unknown` even when its dates would otherwise give `reactivated`. Its accepted `npi_registry_replacement_npi` remains NULL.

## Statistics by source

No measurements exist yet for this definition.

[Statistics SQL 1](../../sql/statistics/17_npi_registry_status_statement_002.sql) · [Statistics SQL 2](../../sql/statistics/17_npi_registry_status_statement_003.sql)

Percentages use all links within each source. Stored classifications preserve their evaluation dates; extraction does not reread NPPES or infer historical activity. `active_as_reported` is not proof of current clinical activity. The independent raw-reference diagnostics remain separate from these published-population statistics.

# NPI registry status

**Status:** implemented and measured read-only, October 29, 2026; unpublished.

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

**Illustrative:** a 2025 deactivation overrides 2021 reactivation.

Comparison date defaults to Europe/Paris today; `registry_status_as_of_day` fixes evaluation. No historical reconstruction or replacement redirects. Absent deactivation does not independently prove activity.

## Measurements

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

[Per-vendor counts, examples and SQL](../../results/registry_status_summary.md) · Executed measurements (local-only: `../../results/registry_status_measure.json`) · Replacement check (local-only: `../../results/registry_status_replacement_check.json`)

[Calculation](../../macros/registry_status.sql) · [Integrity check](../../tests/registry_status.sql) · Native fixtures (local-only: `../../results/registry_status_native.json`) · Local tests (local-only: `../../results/registry_status_local_tests.txt`)

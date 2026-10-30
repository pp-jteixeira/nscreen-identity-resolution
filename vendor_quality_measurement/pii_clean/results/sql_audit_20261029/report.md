# SQL execution audit — October 29, 2026

**Subsequent publication:** all 103 columns are now published. All 13 former missing-column failures passed fresh validation. Five enrichment queries initially received validated base-column projections to avoid duplicate fields. The subsequent statistics cleanup replaced repeated enrichment with stored-column aggregations; all 27 current statistics files passed full execution. See [current statistics validation](../../sql/statistics/README.md). See the [publication report](../publication_20261029/report.md). The tables below retain the initial audit evidence and runtime limits.

Audited **269 SQL files** under `/Users/jteixeira/nscreen_analysis`, discovered with `rg --files -g "*.sql"`. Live checks ran from 17:07 to 17:19 Europe/Paris. Ignored/generated files and the virtual environment were outside this inventory.

**The initial audit found 13 files failing because published metric columns were absent.** The final UNION also fails under default Trino settings because its distributed plan exceeds the stage limit. **9 additional checks timed out** at the audit limit. The subsequent full publication completed all seven vendor models. The rewritten cookie-statistics query and direct published-table email lookup both completed in later validation; the lookup returned 17 records with 109 columns in 13.6 seconds. See the [current lookup validation](../../docs/email_lookup.md#validation-and-publication-status). All 58 local synthetic tests passed.

The audit executed only reads. Existing SQL/model files were not changed during this audit, no views or tables were replaced, and the 163 archived DROP statements were not run.

## Coverage and results

| Check outcome | Count |
|---|---:|
| Executed successfully | 82 |
| Missing columns | 13 |
| Stage limit exceeded | 1 |
| Timed out at 120s | 9 |

There were 105 rendered query checks across 93 files. The staging row-count template was checked for all 13 staging relations, which adds 12 variants. The remaining files are 13 macro libraries and 163 archived DROP statements. Macros were exercised through rendering and the local test suite.

All 269 files comply with the repository rules: no semicolons and no empty or whitespace-only lines.

## Missing-column failures before publication

Live schema inspection found **41 columns in `pii_clean` and each of the seven vendor metric views**. At that checkpoint, all eight outputs lacked the newer facility, specialty, registry-status, vendor/facility-state and cookie-location groups. Local models declare 103 columns. Re-running a query cannot supply columns that have not been published.

| File | First unresolved column | Read-only remedy |
|---|---|---|
| [sql/conflicting_facilities_profile.sql](../../sql/conflicting_facilities_profile.sql) | `facility_npi_values` | Compute `facility_consistency_metrics` before the profile/test. |
| [sql/conflicting_specialties_debug.sql](../../sql/conflicting_specialties_debug.sql) | `conflicting_npi_specialty_comparisons` | Compute `specialty_consistency_metrics` before projection/profile/test. |
| [sql/conflicting_specialties_profile.sql](../../sql/conflicting_specialties_profile.sql) | `specialty_code_values` | Compute `specialty_consistency_metrics` before projection/profile/test. |
| [sql/cookie_location_debug.sql](../../sql/cookie_location_debug.sql) | `cookie_location_status` | Apply `vendor_facility_records`, then `cookie_location_records`. |
| [sql/cookie_location_profile.sql](../../sql/cookie_location_profile.sql) | `cookie_location_status` | Apply `vendor_facility_records`, then `cookie_location_records`. |
| [sql/registry_status_profile.sql](../../sql/registry_status_profile.sql) | `npi_registry_status` | Enrich with `registry_status_records`. |
| [sql/vendor_facility_state_debug.sql](../../sql/vendor_facility_state_debug.sql) | `facility_primary_state` | Enrich with `vendor_facility_records`. |
| [sql/vendor_facility_state_profile.sql](../../sql/vendor_facility_state_profile.sql) | `vendor_state_evidence` | Enrich with `vendor_facility_records`. |
| [tests/conflicting_facilities.sql](../../tests/conflicting_facilities.sql) | `facility_npi_values` | Compute `facility_consistency_metrics` before the profile/test. |
| [tests/conflicting_specialties.sql](../../tests/conflicting_specialties.sql) | `specialty_code_values` | Compute `specialty_consistency_metrics` before projection/profile/test. |
| [tests/cookie_location.sql](../../tests/cookie_location.sql) | `cookie_count` | Apply `vendor_facility_records`, then `cookie_location_records`. |
| [tests/registry_status.sql](../../tests/registry_status.sql) | `npi_registry_status` | Enrich with `registry_status_records`. |
| [tests/vendor_facility_state.sql](../../tests/vendor_facility_state.sql) | `vendor_state_evidence` | Enrich with `vendor_facility_records`. |

**Candidate fixes:** all 13 read-only enrichment candidates passed live `EXPLAIN (TYPE VALIDATE)`. Their exact SQL and query IDs are in fix_candidates.json (historical output, not retained: `fix_candidates.json`). They were not applied to source files or fully executed; validation confirms syntax, relation/column resolution and types, not completion time or population correctness.

**Initial impact:** these failures blocked their respective diagnostics, profiles and live tests. They do not indicate corruption of the existing 41-column table. Using read-only enrichment changes only query output and cost. Keep complete source/email peer groups and exact conflict-day rules so filtering does not remove comparison evidence. Enrichment uses current reference data and can differ from a historical materialized snapshot.

**Remedy, since completed:** all seven vendor metric views were rebuilt and the final 103-column table was published through the managed pipeline after full validation and preservation checks. At the audit checkpoint, refreshing only `pii_clean` from the then-existing views would still have produced 41 columns. Rebuilding only some vendor views can make the final `UNION ALL` fail because column counts/order no longer match. Consumers that use `SELECT *`, positional inserts or a fixed schema may require updates. End-to-end publication and preservation were not tested by this read-only audit.

## Final model: stage limit

[models/final/pii_clean.sql](../../models/final/pii_clean.sql) passed semantic validation but failed execution with `QUERY_HAS_TOO_MANY_STAGES`. The bounded execution required 151 stages; the unbounded distributed plan required 157. The cluster permits 150.

The pipeline already configures `distinct_aggregations_strategy=single_step`. With that setting, the unbounded distributed plan succeeded with **149 fragments**. This is a session setting, so applying it to a separate connection does not affect a later query connection.

The bounded execution retry with the setting returned **passed** (1 row, 55.6s).

These stage counts describe the earlier 41-column views. The later 103-column union required 721 stages even with the pipeline setting, and was published successfully using vendor batches. See stage-limit evidence (historical output, not retained: `stage_limit.json`) and retry evidence (historical output, not retained: `final_retry.json`).

## Timeouts: not established SQL defects

These queries passed semantic validation but exceeded the audit’s `query_max_run_time=120s`. That limit includes waiting, planning and execution. The main execution batch used up to three concurrent queries. Supplemental validation and retry queries overlapped part of that batch. A `LIMIT` bounds returned rows; joins, aggregates and windows can still require broad scans.

| File | Variant | Observed outcome |
|---|---|---|
| [models/intermediate/int_drdb__metrics.sql](../../models/intermediate/int_drdb__metrics.sql) | `default` | Cancelled at the 120s server limit |
| [models/intermediate/int_endato__metrics.sql](../../models/intermediate/int_endato__metrics.sql) | `default` | Cancelled at the 120s server limit |
| [models/intermediate/int_haymarket__metrics.sql](../../models/intermediate/int_haymarket__metrics.sql) | `default` | Cancelled at the 120s server limit |
| [models/intermediate/int_healthlink__metrics.sql](../../models/intermediate/int_healthlink__metrics.sql) | `default` | Cancelled at the 120s server limit |
| [models/intermediate/int_medscape__metrics.sql](../../models/intermediate/int_medscape__metrics.sql) | `default` | Cancelled at the 120s server limit |
| [models/intermediate/int_quantummedica__metrics.sql](../../models/intermediate/int_quantummedica__metrics.sql) | `default` | Cancelled at the 120s server limit |
| [models/intermediate/int_rocketreach__metrics.sql](../../models/intermediate/int_rocketreach__metrics.sql) | `default` | Cancelled at the 120s server limit |
| [sql/email_lookup_full.sql](../../sql/email_lookup_full.sql) | `default` | Cancelled at the 120s server limit |
| [sql/statistics/19_cookie_location_evidence_statement_003.sql](../../sql/statistics/19_cookie_location_evidence_statement_003.sql) | `default` | Cancelled at the 120s server limit |

The subsequent full publication completed all seven vendor models using separate vendor batches. For large repeated computations, inspect distributed plans and use the existing pipeline’s batching or materialized intermediate results when appropriate. Do not remove historical rows or peer contexts merely to meet the audit timeout: that would change metric semantics. Raising the timeout changes resource use, not definitions. The earlier enrichment-based email lookup timed out in this audit. Its replacement reads only the published table and later returned 17 records with 109 columns in 13.6 seconds. The rewritten cookie-statistics query later completed in 37.2 seconds using stored evidence, with zero invariant failures. These later executions do not change the historical timeout records below.

## Templates and write statements

Fifteen files in `sql/` are report templates. They require `EVALUATED_SQL` or `EVIDENCE_SQL` substitution; two also require Jinja macro rendering. Pasting an unrendered template into SQLTools leaves an empty CTE or Jinja syntax and fails. This is expected template behavior. `sql/profile.sql` uses `EVIDENCE_SQL`; its correctly rendered form passed validation and execution, returning seven source summaries. The nine other rendered report templates without unpublished-column dependencies are assessed in the file matrix below.

Model and test files also require the existing Jinja renderer. Live metric tests in this audit targeted `pii_clean`; staging row-count tests targeted all 13 staging relations. The seven vendor-specific variants of each metric test and optional `debug=true` model variants were not separately executed.

For [create_state_daily_7d_view.sql](../../../../nscreen_state_daily/create_state_daily_7d_view.sql), only the SELECT body was validated and executed. The CREATE statement itself was not executed, so view creation, privileges and target replacement behavior are not established by the successful SELECT.

Metadata inspection found no existing target with that view name during this audit. Creation was still not attempted.

The 163 scripts under `results/table_cleanup_20261029/` contain destructive historical DROP operations. They are excluded from execution and are not classified as passing or failing. Re-running them could remove live objects or fail on objects already deleted.

## Verification limits

- Every runnable/renderable check received live `EXPLAIN (TYPE VALIDATE)` before execution.
- Successful ordinary queries were executed as `SELECT * FROM (<query>) AS audit_result LIMIT 100`. Models and invariant tests used `LIMIT 1`.
- For invariant tests, zero rows means no violation found by that complete query. A returned row is a failed invariant. A timeout establishes neither outcome.
- Result values containing email, NPI, UID or record payloads were not saved in this audit. Evidence retains query text, column names, row counts, runtime, errors and Trino query IDs.
- Email lookup queries retained their shipped example email. A zero-row lookup demonstrates successful execution for that parameter, not a real-email data-path check.
- Source snapshots were not pinned. This checks the observed live environment and does not establish historical reproducibility.
- The 58 passing local tests execute synthetic fixtures using translated DuckDB SQL and include rendering/publication checks. They complement rather than replace native runtime checks.

## Initial file-by-file execution matrix

| File | Check context | Outcome |
|---|---|---|
| [nscreen_state_daily/create_state_daily_7d_view.sql](../../../../nscreen_state_daily/create_state_daily_7d_view.sql) | create view body only | Executed successfully — 100 rows, 3.2s |
| [nscreen_state_daily/select_state_daily_7d.sql](../../../../nscreen_state_daily/select_state_daily_7d.sql) | standalone read | Executed successfully — 100 rows, 3.5s |
| [models/final/pii_clean.sql](../../models/final/pii_clean.sql) | model template | Stage limit exceeded |
| [models/intermediate/int_drdb__metrics.sql](../../models/intermediate/int_drdb__metrics.sql) | model template | Timed out at 120s |
| [models/intermediate/int_endato__metrics.sql](../../models/intermediate/int_endato__metrics.sql) | model template | Timed out at 120s |
| [models/intermediate/int_haymarket__metrics.sql](../../models/intermediate/int_haymarket__metrics.sql) | model template | Timed out at 120s |
| [models/intermediate/int_healthlink__metrics.sql](../../models/intermediate/int_healthlink__metrics.sql) | model template | Timed out at 120s |
| [models/intermediate/int_medscape__metrics.sql](../../models/intermediate/int_medscape__metrics.sql) | model template | Timed out at 120s |
| [models/intermediate/int_name__variants.sql](../../models/intermediate/int_name__variants.sql) | model template | Executed successfully — 1 row, 21.3s |
| [models/intermediate/int_npi__names.sql](../../models/intermediate/int_npi__names.sql) | model template | Executed successfully — 1 row, 6.0s |
| [models/intermediate/int_quantummedica__metrics.sql](../../models/intermediate/int_quantummedica__metrics.sql) | model template | Timed out at 120s |
| [models/intermediate/int_rocketreach__metrics.sql](../../models/intermediate/int_rocketreach__metrics.sql) | model template | Timed out at 120s |
| [models/staging/stg_drdb__enrich.sql](../../models/staging/stg_drdb__enrich.sql) | model template | Executed successfully — 1 row, 22.2s |
| [models/staging/stg_drdb__npi.sql](../../models/staging/stg_drdb__npi.sql) | model template | Executed successfully — 1 row, 6.2s |
| [models/staging/stg_endato__pii.sql](../../models/staging/stg_endato__pii.sql) | model template | Executed successfully — 1 row, 4.5s |
| [models/staging/stg_haymarket__npi.sql](../../models/staging/stg_haymarket__npi.sql) | model template | Executed successfully — 1 row, 4.7s |
| [models/staging/stg_healthlink__email.sql](../../models/staging/stg_healthlink__email.sql) | model template | Executed successfully — 1 row, 4.2s |
| [models/staging/stg_healthlink__hcp.sql](../../models/staging/stg_healthlink__hcp.sql) | model template | Executed successfully — 1 row, 3.9s |
| [models/staging/stg_medscape__global.sql](../../models/staging/stg_medscape__global.sql) | model template | Executed successfully — 1 row, 3.4s |
| [models/staging/stg_medscape__meta.sql](../../models/staging/stg_medscape__meta.sql) | model template | Executed successfully — 1 row, 3.9s |
| [models/staging/stg_medscape__optout.sql](../../models/staging/stg_medscape__optout.sql) | model template | Executed successfully — 1 row, 3.2s |
| [models/staging/stg_npi__reference.sql](../../models/staging/stg_npi__reference.sql) | model template | Executed successfully — 1 row, 4.4s |
| [models/staging/stg_quantummedica__hcpdata.sql](../../models/staging/stg_quantummedica__hcpdata.sql) | model template | Executed successfully — 1 row, 3.7s |
| [models/staging/stg_quantummedica__hcpmeta.sql](../../models/staging/stg_quantummedica__hcpmeta.sql) | model template | Executed successfully — 1 row, 7.4s |
| [models/staging/stg_rocketreach__lookup.sql](../../models/staging/stg_rocketreach__lookup.sql) | model template | Executed successfully — 1 row, 3.4s |
| [results/metric_population_20261029/flag_populations.sql](../metric_population_20261029/flag_populations.sql) | standalone read | Executed successfully — 10 rows, 10.3s |
| [results/metric_population_20261029/grouped.sql](../metric_population_20261029/grouped.sql) | standalone read | Executed successfully — 100 rows, 37.5s |
| [results/metric_population_20261029/grouped_global.sql](../metric_population_20261029/grouped_global.sql) | standalone read | Executed successfully — 100 rows, 30.9s |
| [results/metric_population_20261029/source_totals.sql](../metric_population_20261029/source_totals.sql) | standalone read | Executed successfully — 8 rows, 7.4s |
| [results/metric_population_20261029/strict_favorable.sql](../metric_population_20261029/strict_favorable.sql) | standalone read | Executed successfully — 1 row, 6.0s |
| [sql/conflicting_facilities_debug.sql](../../sql/conflicting_facilities_debug.sql) | standalone read | Executed successfully — 100 rows, 5.0s |
| [sql/conflicting_facilities_profile.sql](../../sql/conflicting_facilities_profile.sql) | profile template | Missing columns |
| [sql/conflicting_names_debug.sql](../../sql/conflicting_names_debug.sql) | standalone read | Executed successfully — 100 rows, 3.2s |
| [sql/conflicting_names_profile.sql](../../sql/conflicting_names_profile.sql) | profile template | Executed successfully — 7 rows, 7.5s |
| [sql/conflicting_specialties_debug.sql](../../sql/conflicting_specialties_debug.sql) | standalone read | Missing columns |
| [sql/conflicting_specialties_profile.sql](../../sql/conflicting_specialties_profile.sql) | profile template | Missing columns |
| [sql/conflicting_states_debug.sql](../../sql/conflicting_states_debug.sql) | standalone read | Executed successfully — 100 rows, 3.2s |
| [sql/conflicting_states_profile.sql](../../sql/conflicting_states_profile.sql) | profile template | Executed successfully — 7 rows, 7.5s |
| [sql/cookie_location_debug.sql](../../sql/cookie_location_debug.sql) | standalone read | Missing columns |
| [sql/cookie_location_profile.sql](../../sql/cookie_location_profile.sql) | profile template | Missing columns |
| [sql/email_domain_profile.sql](../../sql/email_domain_profile.sql) | profile template | Executed successfully — 28 rows, 10.9s |
| [sql/email_format_profile.sql](../../sql/email_format_profile.sql) | profile template | Executed successfully — 7 rows, 12.6s |
| [sql/email_linkage_profile.sql](../../sql/email_linkage_profile.sql) | profile template | Executed successfully — 7 rows, 5.5s |
| [sql/email_lookup_full.sql](../../sql/email_lookup_full.sql) | standalone read | Timed out at 120s |
| [sql/email_lookup_published.sql](../../sql/email_lookup_published.sql) | standalone read | Executed successfully — 0 rows, 2.9s |
| [sql/email_npi_profile.sql](../../sql/email_npi_profile.sql) | profile template | Executed successfully — 7 rows, 4.8s |
| [sql/email_role_profile.sql](../../sql/email_role_profile.sql) | profile template | Executed successfully — 7 rows, 10.9s |
| [sql/history_inventory.sql](../../sql/history_inventory.sql) | standalone read | Executed successfully — 8 rows, 4.0s |
| [sql/name_consistency_profile.sql](../../sql/name_consistency_profile.sql) | profile template | Executed successfully — 7 rows, 8.5s |
| [sql/name_match_profile.sql](../../sql/name_match_profile.sql) | profile template | Executed successfully — 21 rows, 89.2s |
| [sql/profile.sql](../../sql/profile.sql) | profile template | Executed successfully — 7 rows, 23.4s |
| [sql/registry_status_profile.sql](../../sql/registry_status_profile.sql) | profile template | Missing columns |
| [sql/statistics/01_observation_counts.sql](../../sql/statistics/01_observation_counts.sql) | standalone read | Executed successfully — 7 rows, 5.2s |
| [sql/statistics/02_email_format_valid.sql](../../sql/statistics/02_email_format_valid.sql) | standalone read | Executed successfully — 7 rows, 5.6s |
| [sql/statistics/03_email_role_account.sql](../../sql/statistics/03_email_role_account.sql) | standalone read | Executed successfully — 7 rows, 5.3s |
| [sql/statistics/04_email_domain_class.sql](../../sql/statistics/04_email_domain_class.sql) | standalone read | Executed successfully — 7 rows, 3.8s |
| [sql/statistics/05_email_matches_source_name.sql](../../sql/statistics/05_email_matches_source_name.sql) | standalone read | Executed successfully — 7 rows, 4.5s |
| [sql/statistics/06_email_matches_registry_name.sql](../../sql/statistics/06_email_matches_registry_name.sql) | standalone read | Executed successfully — 7 rows, 12.9s |
| [sql/statistics/07_vendor_name_matches_registry_name.sql](../../sql/statistics/07_vendor_name_matches_registry_name.sql) | standalone read | Executed successfully — 7 rows, 5.0s |
| [sql/statistics/08_email_npi_multiplicity.sql](../../sql/statistics/08_email_npi_multiplicity.sql) | standalone read | Executed successfully — 7 rows, 6.0s |
| [sql/statistics/09_has_been_reassigned.sql](../../sql/statistics/09_has_been_reassigned.sql) | standalone read | Executed successfully — 7 rows, 25.0s |
| [sql/statistics/10_has_conflict_linkage.sql](../../sql/statistics/10_has_conflict_linkage.sql) | standalone read | Executed successfully — 7 rows, 6.5s |
| [sql/statistics/11_email_name_count.sql](../../sql/statistics/11_email_name_count.sql) | standalone read | Executed successfully — 7 rows, 10.3s |
| [sql/statistics/12_email_npi_has_name_conflict.sql](../../sql/statistics/12_email_npi_has_name_conflict.sql) | standalone read | Executed successfully — 7 rows, 5.5s |
| [sql/statistics/13_conflicting_npis_share_name.sql](../../sql/statistics/13_conflicting_npis_share_name.sql) | standalone read | Executed successfully — 7 rows, 6.2s |
| [sql/statistics/14_conflicting_npis_share_state.sql](../../sql/statistics/14_conflicting_npis_share_state.sql) | standalone read | Executed successfully — 7 rows, 5.9s |
| [sql/statistics/15_conflicting_npis_share_facility.sql](../../sql/statistics/15_conflicting_npis_share_facility.sql) | standalone read | Executed successfully — 7 rows, 6.0s |
| [sql/statistics/15_conflicting_npis_share_facility_statement_002.sql](../../sql/statistics/15_conflicting_npis_share_facility_statement_002.sql) | standalone read | Executed successfully — 5 rows, 21.2s |
| [sql/statistics/16_conflicting_npis_share_specialty.sql](../../sql/statistics/16_conflicting_npis_share_specialty.sql) | standalone read | Executed successfully — 7 rows, 5.7s |
| [sql/statistics/16_conflicting_npis_share_specialty_statement_002.sql](../../sql/statistics/16_conflicting_npis_share_specialty_statement_002.sql) | standalone read | Executed successfully — 5 rows, 20.0s |
| [sql/statistics/17_npi_registry_status.sql](../../sql/statistics/17_npi_registry_status.sql) | standalone read | Executed successfully — 1 row, 4.0s |
| [sql/statistics/17_npi_registry_status_statement_002.sql](../../sql/statistics/17_npi_registry_status_statement_002.sql) | standalone read | Executed successfully — 7 rows, 5.7s |
| [sql/statistics/17_npi_registry_status_statement_003.sql](../../sql/statistics/17_npi_registry_status_statement_003.sql) | standalone read | Executed successfully — 42 rows, 6.6s |
| [sql/statistics/17_npi_registry_status_statement_004.sql](../../sql/statistics/17_npi_registry_status_statement_004.sql) | standalone read | Executed successfully — 1 row, 3.2s |
| [sql/statistics/18_vendor_facility_state.sql](../../sql/statistics/18_vendor_facility_state.sql) | standalone read | Executed successfully — 7 rows, 4.5s |
| [sql/statistics/18_vendor_facility_state_statement_002.sql](../../sql/statistics/18_vendor_facility_state_statement_002.sql) | standalone read | Executed successfully — 31 rows, 7.3s |
| [sql/statistics/19_cookie_location_evidence.sql](../../sql/statistics/19_cookie_location_evidence.sql) | standalone read | Executed successfully — 1 row, 3.0s |
| [sql/statistics/19_cookie_location_evidence_statement_002.sql](../../sql/statistics/19_cookie_location_evidence_statement_002.sql) | standalone read | Executed successfully — 7 rows, 5.6s |
| [sql/statistics/19_cookie_location_evidence_statement_003.sql](../../sql/statistics/19_cookie_location_evidence_statement_003.sql) | standalone read | Timed out at 120s |
| [sql/vendor_facility_state_debug.sql](../../sql/vendor_facility_state_debug.sql) | standalone read | Missing columns |
| [sql/vendor_facility_state_profile.sql](../../sql/vendor_facility_state_profile.sql) | profile template | Missing columns |
| [tests/conflicting_facilities.sql](../../tests/conflicting_facilities.sql) | pii_clean | Missing columns |
| [tests/conflicting_names.sql](../../tests/conflicting_names.sql) | pii_clean | Executed successfully — 0 rows, 16.1s |
| [tests/conflicting_specialties.sql](../../tests/conflicting_specialties.sql) | pii_clean | Missing columns |
| [tests/conflicting_states.sql](../../tests/conflicting_states.sql) | pii_clean | Executed successfully — 0 rows, 15.7s |
| [tests/cookie_location.sql](../../tests/cookie_location.sql) | pii_clean | Missing columns |
| [tests/email_linkage_history.sql](../../tests/email_linkage_history.sql) | pii_clean | Executed successfully — 0 rows, 79.3s |
| [tests/email_npi_multiplicity.sql](../../tests/email_npi_multiplicity.sql) | pii_clean | Executed successfully — 0 rows, 4.8s |
| [tests/name_consistency.sql](../../tests/name_consistency.sql) | pii_clean | Executed successfully — 0 rows, 12.4s |
| [tests/registry_status.sql](../../tests/registry_status.sql) | pii_clean | Missing columns |
| [tests/source_integrity.sql](../../tests/source_integrity.sql) | pii_clean | Executed successfully — 0 rows, 19.9s |
| [tests/staging_row_count.sql](../../tests/staging_row_count.sql) | stg_drdb__enrich | Executed successfully — 0 rows, 2.9s |
| [tests/staging_row_count.sql](../../tests/staging_row_count.sql) | stg_drdb__npi | Executed successfully — 0 rows, 2.9s |
| [tests/staging_row_count.sql](../../tests/staging_row_count.sql) | stg_endato__pii | Executed successfully — 0 rows, 3.4s |
| [tests/staging_row_count.sql](../../tests/staging_row_count.sql) | stg_haymarket__npi | Executed successfully — 0 rows, 2.9s |
| [tests/staging_row_count.sql](../../tests/staging_row_count.sql) | stg_healthlink__email | Executed successfully — 0 rows, 3.0s |
| [tests/staging_row_count.sql](../../tests/staging_row_count.sql) | stg_healthlink__hcp | Executed successfully — 0 rows, 3.3s |
| [tests/staging_row_count.sql](../../tests/staging_row_count.sql) | stg_medscape__global | Executed successfully — 0 rows, 2.8s |
| [tests/staging_row_count.sql](../../tests/staging_row_count.sql) | stg_medscape__meta | Executed successfully — 0 rows, 3.0s |
| [tests/staging_row_count.sql](../../tests/staging_row_count.sql) | stg_medscape__optout | Executed successfully — 0 rows, 6.6s |
| [tests/staging_row_count.sql](../../tests/staging_row_count.sql) | stg_npi__reference | Executed successfully — 0 rows, 3.0s |
| [tests/staging_row_count.sql](../../tests/staging_row_count.sql) | stg_quantummedica__hcpdata | Executed successfully — 0 rows, 3.1s |
| [tests/staging_row_count.sql](../../tests/staging_row_count.sql) | stg_quantummedica__hcpmeta | Executed successfully — 0 rows, 2.9s |
| [tests/staging_row_count.sql](../../tests/staging_row_count.sql) | stg_rocketreach__lookup | Executed successfully — 0 rows, 2.9s |
| [tests/vendor_facility_state.sql](../../tests/vendor_facility_state.sql) | pii_clean | Missing columns |

## Evidence

- Original inventory, SQL, validation and execution records (historical output, not retained: `audit.json`)
- Validated fix candidates and correctly rendered profile (historical output, not retained: `fix_candidates.json`)
- Published schema inspection (historical output, not retained: `published_schema.csv`)
- Local test output (historical output, not retained: `local_tests.txt`)
- Execution progress log (historical output, not retained: `progress.log`)

The original audit record retains the first `profile.sql` placeholder error. The report and file matrix use its subsequent correctly rendered validation/execution result from `fix_candidates.json`.

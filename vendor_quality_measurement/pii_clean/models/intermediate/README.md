# Intermediate: one CTE pipeline per vendor

This folder contains nine SQL models: seven vendor metric models and two shared name lookups. Vendor-specific steps are named CTEs inside each vendor file.

| Model | Purpose |
|---|---|
| `int_<vendor>__metrics.sql` | Exact-record history, email positions, reference comparisons and reviewed indicators for one vendor. |
| [int_npi__names.sql](int_npi__names.sql) | Distinct normalized registry name pairs and nickname expansions, shared by all vendors. |
| [int_name__variants.sql](int_name__variants.sql) | Shared first-name variant lookup built from the nickname seed. |

Start with [Medscape](int_medscape__metrics.sql) for a single input, [DRDB](int_drdb__metrics.sql) for two inputs, or [HealthLink](int_healthlink__metrics.sql) for a separate HCP name reference.

Each vendor file follows this flow:

1. `*_versions`: combine raw rows only when every original column except `day` agrees. The shared `record_versions` macro attaches counts, exact `observed_days`, date bounds, raw payload and record ID. DRDB has separate CTEs for its two raw tables.
2. `email_candidates`: unfold email positions and select nonempty cleaned email/NPI keys. Duplicate email positions remain separate.
3. `metric_records`: attach `metric_row_id`, identifying the exact record and email position.
4. `email_npi_counts`, `email_day_counts`, `email_conflicts`, `email_linkage`: count distinct NPIs within the vendor; dated vendors detect changing daily NPI sets and collect conflict days. Undated vendors skip the daily CTEs and compare all their current records for conflict.
5. `name_inputs`: select the record's paired names; HealthLink joins its HCP reference by NPI.
6. `name_metrics`: compare names using shared matching macros, aggregating only within each metric row.
7. HealthLink’s `hcp_states` CTE collects recognized HCP states by NPI without date alignment. `metric_base`: attach history-level reassignment and record-level conflict, including exact `conflict_days`, alongside name, state and email indicators. `source_name_values` retains the record's usable normalized names and first-name variants.
8. `facility_enriched`: join the association reference by trimmed NPI, aggregating distinct facility NPIs across all ranks before the join. This implementation is published and passed full-build validation. It adds no intermediate model or staging view.
9. `specialty_enriched`: attach unique per-NPI recognized taxonomy-code arrays from all fifteen NPPES slots. Code validation uses the NPI taxonomy dictionary; no date alignment or broad-label substitution. This metric is published.
10. `relationship_metrics`: attach `email_name_count` over vendor/email history and nullable `email_npi_has_name_conflict` over vendor/email/NPI history. Also compare this record’s names with other NPIs on overlapping conflict days (or within its undated vendor snapshot), producing `conflicting_npis_share_name` and peer comparison details. State comparisons use the same record/day scope with `source_state_values`, producing `conflicting_npis_share_state` and peer state details. Specialty comparisons reuse the same windows and conflict timing, with recognized code sets and exact shared codes retained for inspection. Facility comparisons reuse those windows and conflict contexts, preserving nullable peer outcomes and exact shared IDs. Facility associations have no activity-date alignment. Shared vendor windows preserve every metric row; the final table uses only UNION ALL.

11. `registry_metrics`: left-join a unique per-NPI NPPES lifecycle lookup to `relationship_metrics`. Retain raw dates/replacements, count lifecycle variants, and attach current registry status with explicit uncertainty reasons. No row is filtered, no replacement is followed, and no historical vendor-date status is inferred. This metric is published.

12. `location_metrics`: attach one usable historical rank-1 facility state per NPI and compare it with each record’s normalized vendor-state set.
13. `metrics`: attach per-email UID/day geography summaries for the seven completed days before evaluation. UID state ranking precedes email joins; ties supply no agreement. Coverage distinguishes missing source dates from observed disagreement. These additions passed local and native synthetic tests, all vendor plans and full-population read-only measurement; they are published and passed full-build validation on October 29, 2026.

The default SELECT returns `metrics`. Rendering the same vendor file with `debug=true` adds comparison details through shared macros. It requires no separate name-input or record views. Debug snapshots can contain several name pairs per metric row.

Only the nine intermediate models become views. Together with 13 staging views and the nickname seed, a normal build manages 23 views plus the final `pii_clean` table. Existing legacy helper views are left in place but are no longer managed or referenced by this build. Saved evidence and dated debug artifacts are historical references; their presence on disk does not establish that their warehouse tables still exist.

Missing-key raw rows remain in staging. Record identity, fuzzy matching, nullable outcomes and observation counts are unchanged. Email–NPI deduplication remains deferred until after metrics and indicators. See the [source map](../../docs/00_source_map.md) and [matching rules](../../macros/name_matching.sql).

# Intermediate: one CTE pipeline per vendor

This folder contains eleven SQL models: seven cookie-independent vendor metric models, two shared name lookups, one stored core union and one downstream cookie model. Vendor-specific steps are named CTEs inside each vendor file; the metric steps shared by all vendors come from one macro.

| Model | Purpose |
|---|---|
| [int_pii__metrics.sql](int_pii__metrics.sql) | 139-field union of all seven vendor outputs. |
| [int_cookie__metrics.sql](int_cookie__metrics.sql) | 180-field source-scoped domain and cookie outputs, combined after enrichment from stored core. |
| `int_<vendor>__metrics.sql` | Record versions, email positions, link collapse, reference comparisons and reviewed indicators for one vendor. One row per source/email/NPI link. |
| [int_npi__names.sql](int_npi__names.sql) | Distinct normalized registry name pairs and nickname expansions, shared by all vendors. |
| [int_name__variants.sql](int_name__variants.sql) | Shared first-name variant lookup built from the nickname seed. |

Start with [Medscape](int_medscape__metrics.sql) for dated global records with volatile fields, same-day metadata and cumulative opt-out exclusion, [DRDB](int_drdb__metrics.sql) for two attribution feeds, or [HealthLink](int_healthlink__metrics.sql) for a separate HCP name reference.

## Versions, email candidates and links

Each vendor file defines three CTEs and then calls the shared chain:

1. `*_versions`: the [`record_versions`](../../macros/record_versions.sql) macro groups raw staging rows that are identical except for `day` and the schema's volatile fields. A version is one distinct identity of a source record. It attaches exact `observed_days`, date bounds, observation counts, the JSON identity payload and `record_id`, the SHA256 of the source table and identity payload (Medscape also includes the cleaned email). Medscape first excludes cleaned NPIs listed in `stg_medscape__optout` across all retained deliveries, without opt-out date alignment; staging remains unchanged. DRDB has separate CTEs for its two raw tables.
2. `email_candidates`: unfold versions by email position and select nonempty cleaned email/NPI keys. QuantumMedica splits pipe-separated tokens, Endato reads `email_1` through `email_5`, RocketReach reads `emails[]` plus the recommended/current fields, and DRDB unions its two tables. Each candidate carries its `email_origin`, vendor names, recognized states, Medscape GUID and DRDB specialty labels.
3. `{{ link_metrics(vendor) }}`: the shared chain in [link_metrics.sql](../../macros/link_metrics.sql), described below.

Volatile fields are declared under `volatile` in [record_schemas.json](../record_schemas.json). They never split a version; each is kept as a sorted distinct array named `<field>_values` and appears as an array inside the JSON payload. Medscape declares `email_address` (raw spelling), `huid`, `ip` (split on commas), `payer_status`, `practice_setting`, `source` and `validated`. Other sources declare none.

## Shared link metric chain

1. `metric_records`: [`link_records`](../../macros/record_versions.sql) collapses candidates to one row per link and assigns `link_id`, the SHA256 of source, email and NPI. History columns cover all versions: day bounds and `observed_days` are unions, observation counts are sums. It also produces `record_count`, sorted `record_ids`, `email_origins`, `attribute_versions` and `latest_record_id`. The latest version is the one with the unique greatest `last_seen_day`, or the only version; `latest_record_id` is NULL when several undated versions exist or the greatest day is tied. The latest version's names, states and GUID are kept for the `_latest` columns.
2. `email_npi_counts`, `email_day_counts`, `email_conflicts`, `email_linkage`: count distinct NPIs within the vendor; dated vendors detect changing daily NPI sets and collect conflict days. Undated vendors skip the daily CTEs and compare all their current links for conflict.
3. `name_inputs`: every distinct vendor name pair across the link's versions; HealthLink joins its HCP reference by NPI. `latest_name_inputs`: the latest version's name pair, only when `latest_record_id` is not NULL (HealthLink reuses its HCP names).
4. `name_metrics` and `latest_name_metrics`: compare names using shared matching macros, aggregating to one row per link. `name_metrics` feeds the all-version indicators: any matching usable name gives true, all failing names give false, no usable name gives NULL. It retains distinct comparison rows, component match kinds, class sets, evaluation time and definition version; see [stored evidence](../../docs/name_match_evidence.md). `latest_name_metrics` feeds `email_matches_source_name_latest` and `vendor_name_matches_registry_name_latest`.
5. HealthLink’s `hcp_states` CTE collects recognized HCP states by NPI without date alignment. `metric_base`: attach history-level reassignment and link-level conflict, including exact `conflict_days`, alongside name, state and email indicators. `source_name_values` retains usable normalized names and first-name variants across versions. `source_state_values` is the union of recognized states across versions; `source_state_values_latest` holds the latest version's states.
6. `facility_enriched`: join the association reference by trimmed NPI, aggregating distinct facility NPIs across all ranks before the join.
7. `specialty_enriched`: attach unique per-NPI recognized taxonomy-code arrays from all fifteen NPPES slots. Code validation uses the NPI taxonomy dictionary; no date alignment or broad-label substitution.
8. `relationship_metrics`: attach `email_name_count` over vendor/email history and nullable `email_npi_has_name_conflict` over vendor/email/NPI history. Compare the link's union of names with each peer link sharing a conflict day (or every other NPI of the email for undated Endato, RocketReach and DRDB), producing `conflicting_npis_share_name` and peer comparison details. State, NPPES specialty and facility comparisons use the same peer contexts with `source_state_values`, recognized code sets and retained facility NPIs. Facility associations have no activity-date alignment. Cross-NPI comparisons have no `_latest` form.
9. `registry_metrics`: left-join a unique per-NPI NPPES lifecycle lookup. Retain raw dates/replacements, count lifecycle variants, and attach current registry status with explicit uncertainty reasons. No link is filtered, no replacement is followed, and no historical vendor-date status is inferred.
10. `location_metrics`: attach one usable rank-1 facility state per NPI and compare it with the link's vendor states (`vendor_state_evidence`) and with the latest version's states (`vendor_state_evidence_latest`).
11. `freshness_metrics`, `stability_inputs` and `stability_metrics`: attach latest-observation context and dated presence/overlap measures.
12. `identity_metrics` and `professional_metrics`: attach NPI structure/entity evidence and vendor specialty/profession evidence. Medscape metadata joins by NPI, day and registration GUID using each GUID's own days; DRDB uses the raw `specialty` labels of all versions.
13. `registration_metrics` and `metrics`: attach registration supersession and sequential history, as described below.

After all vendor steps finish and their union is stored in core, `int_cookie__metrics` computes cookie geography separately. It filters one source before computing email evidence over three completed days, attaches it to core links, then combines enriched source outputs for final publication. The runner executes those source branches separately. UID state ranking precedes email joins; ties supply no agreement. Coverage distinguishes missing source dates from observed disagreement. `cookie_vendor_state_evidence` compares cookie states with `source_state_values`, and `cookie_vendor_state_evidence_latest` with `source_state_values_latest`. See [independent enrichment](../../docs/cookie_stage.md).

The default SELECT returns `metrics`. Rendering the same vendor file with `debug=true` adds comparison details through shared macros. It requires no separate name-input or record views. Debug output can contain several name pairs per link.

Ten intermediate models become views; `int_pii__metrics` is stored. Together with 13 staging views and the nickname seed, a normal build manages 24 views and two stored tables: core and final `pii_clean`.

Missing-key and opted-out raw rows remain in staging. Medscape opt-out exclusion occurs only in intermediate. Cross-vendor deduplication is not performed. See the [source map](../../docs/00_source_map.md) and [matching rules](../../macros/name_matching.sql).

## Sequential history and registration supersession

After vendor professional evidence, `registration_metrics` evaluates Medscape registration status per link and registration GUID, using each GUID's own days through `sequence_as_of_day`; each link reports its most recently observed GUID as `registration_guid`. Other vendors receive typed inapplicable values. `metrics` then reads narrow `metric_records` through `sequential_history_records` and joins one source/email summary and ordered causal daily evidence onto each link. Content-version detection is source-specific and does not introduce a managed view. See [sequential history](../../docs/metrics/25_sequential_history.md) and [registration supersession](../../docs/metrics/26_registration_supersession.md).

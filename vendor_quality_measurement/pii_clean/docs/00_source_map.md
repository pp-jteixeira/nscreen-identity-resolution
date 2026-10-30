# Source tables and staging models

Each staging model reads one table, retains its raw columns and rows, and adds cleaned helpers. Warehouse view names are `iceberg.jteixeira_ipa.pii__` followed by the model name below.

| Vendor | Input table | Staging model |
|---|---|---|
| HealthLink | `iceberg.thirdparty.healthlink_email` | `stg_healthlink__email` |
| HealthLink | `iceberg.thirdparty.healthlink_hcp` | `stg_healthlink__hcp` |
| QuantumMedica | `iceberg.thirdparty.quantummedica_hcpdata` | `stg_quantummedica__hcpdata` |
| QuantumMedica | `iceberg.thirdparty.quantummedica_hcpmeta` | `stg_quantummedica__hcpmeta` |
| Medscape | `iceberg.thirdparty.medscape_pii_global` | `stg_medscape__global` |
| Medscape | `iceberg.thirdparty.medscape_pii_meta_global` | `stg_medscape__meta` |
| Medscape | `iceberg.thirdparty.medscape_npi_optout` | `stg_medscape__optout` |
| Endato | `iceberg.thirdparty.endato_pii` | `stg_endato__pii` |
| RocketReach | `iceberg.npi.rocket_reach_npi_lookup` | `stg_rocketreach__lookup` |
| DRDB | `iceberg.thirdparty.drdb_npi` | `stg_drdb__npi` |
| DRDB | `iceberg.thirdparty.npi_enrich_emails_hashlower` | `stg_drdb__enrich` |
| Haymarket | `iceberg.thirdparty.haymarket_npi` | `stg_haymarket__npi` |

Every vendor model adds nullable `npi_clean`, `vendor_day` and `invalid_vendor_day`. Haymarket reads NPI from `npi_number`; other tables use `npi`. Dated tables use `day`. Undated tables retain unknown observation dates.

Email inputs are HealthLink `hld_email`, QuantumMedica `email` (pipe-separated), Medscape `email_address`, Endato `email_1_address` through `email_5_address`, DRDB `emailaddress`/`email`, and Haymarket `email`. RocketReach supplies `emails[].email` plus recommended/current email fields.

Staging retains original values. Intermediate performs list splitting, slot combining and unnesting. Endato provider-input `email`/`emails` remain staged but are not attributed as Endato-returned matches.

NPI-reference names are joined in intermediate for name comparisons. Facility-NPI enrichment and cookie joins passed native and full-population validation and were published on October 29, 2026. See [source declarations](../models/sources.yml), [staging queries](../models/staging/) and [intermediate models](../models/intermediate/README.md).

## Available history

**Principle:** use every retained partition, not only the latest. A partition is a stored group of records, here grouped by date.

**Where to find it:** `iceberg.jteixeira_ipa.pii__int_<vendor>__metrics`: `first_seen_day`, `last_seen_day`, `observed_days`, `observed_day_count`, `undated_observation_count`, `computed_at`. Exact `observed_days` drive same-day conflict; `conflict_days` retains the conflicting subset for that record. Identify metric rows with `source`, `metric_row_id`; inspect raw identity using `record_id` and `record_payload`. Input `day` columns are listed above.

“All history” means rows currently readable in the mapped source tables. Deleted records and expired Iceberg snapshots are not recovered.

**Illustrative example:** January and March deliveries exist, but February is absent. This does not prove an email disappeared during February.

`first_seen_day` and `last_seen_day` bound the source dates containing the same exact raw record. `observed_day_count` counts those distinct dates. None measures how long someone owned an email. Unknown dates stay null; RocketReach update timestamps are not email observation dates.

Measured October 28, 2026, at exact-record grain. Date bounds describe readable delivery days; they do not imply uninterrupted coverage.

| Source | Earliest / latest day | Rows with undated observations, n (%) |
|---|---:|---:|
| HealthLink | 2026-01-07 / 2026-10-25 | 0 (0.00000%) |
| QuantumMedica | 2025-09-14 / 2026-10-15 | 0 (0.00000%) |
| Medscape | 2024-01-10 / 2026-10-27 | 0 (0.00000%) |
| Endato | Unknown | 5,427,459 (100.00000%) |
| RocketReach | Unknown | 4,864,145 (100.00000%) |
| DRDB | Unknown | 1,115,415 (100.00000%) |
| Haymarket | 2021-07-06 / 2021-07-06 | 0 (0.00000%) |

Measured history and SQL (local-only: `../results/email_linkage_measurements.json`). Endato, RocketReach and both DRDB inputs have no delivery `day`; their observation dates stay unknown. Other timestamps remain part of record identity, including RocketReach `created_at` and `updated_at`. For `has_conflict_linkage`, all currently available undated records are compared within each vendor; both DRDB feeds are combined for that comparison. This assumes comparability, not a common collection date. Multi-NPI reassignment remains unknown without dated history.

[Inventory SQL](../sql/history_inventory.sql) · [Profile SQL](../sql/profile.sql) · [Raw schema inventory](../models/record_schemas.json)

## Name-comparison inputs

| Vendor | Raw table and name fields | Intermediate interpretation |
|---|---|---|
| HealthLink | `iceberg.thirdparty.healthlink_hcp.firstname`, `lastname` | Join by trimmed `npi`; distinct name pairs across every retained HCP delivery. |
| QuantumMedica | `iceberg.thirdparty.quantummedica_hcpdata.first_name`, `last_name` | Names on the email-bearing record; missing names stay unknown. |
| Medscape | `iceberg.thirdparty.medscape_pii_global.first_name`, `last_name` | Preserve the name pair on each observation, across all retained feeds and dates. |
| Endato | `iceberg.thirdparty.endato_pii.name_first`, `name_last` | Returned person's name; excludes provider-input names. |
| RocketReach | `iceberg.npi.rocket_reach_npi_lookup.name` | Normalize full name; first and last space-separated tokens. Fewer than two tokens gives no usable name. |
| DRDB | `iceberg.thirdparty.drdb_npi.firstname`, `lastname`; `iceberg.thirdparty.npi_enrich_emails_hashlower.name` | Separate main-feed fields; enrichment full name uses first/last tokens. |
| Haymarket | `iceberg.thirdparty.haymarket_npi.first_name`, `last_name` | Preserve the supplied name pair. |

Registry input: `iceberg.npi.npi_reference.npi`, `first_name`, `last_name`. `stg_npi__reference` retains every raw row. `int_npi__names` retains distinct normalized name pairs per trimmed NPI; no date or deactivation filter. `last_update_date` is not used to reconstruct historical names.

Names are normalized in intermediate; raw source values remain available. HealthLink's HCP join uses NPI without date alignment. Its two retained HCP dates, January 7 and October 3, 2026, can therefore contribute names to any retained email link. Registry inputs contained 9,551,475 rows and 9,530,202 distinct NPIs when profiled on October 28, 2026. These historical registry counts are not a current row-grain measurement.

Inside each vendor model, the `name_metrics` CTE aggregates to one row per `metric_row_id` before joining the final `metrics` CTE. Missing HCP or registry matches remain visible as unknown name evidence. Repeated names are deduplicated; they never increase observation counts. The [nickname seed](../seeds/nicknames.csv) is rendered as a shared lookup view by the pipeline runner.

## State-comparison inputs

Use QuantumMedica/Medscape/DRDB `state`, Endato’s returned `address_state`, RocketReach `region`, and HealthLink HCP `state` joined by trimmed NPI across retained history. Haymarket has no state input. HealthLink reference states have no date alignment. Endato provider-input addresses and registry states are excluded. Medscape `country` and RocketReach `country_code`/`country` prevent recognized US codes from being assigned to explicit foreign locations. The shared [normalization macro](../macros/state_consistency.sql) trims, uppercases and collapses whitespace, mapping recognized full US state names/codes, DC and five territories to two-letter codes. For example, ` California ` becomes `CA` and `new   york` becomes `NY`. Unrecognized, missing or excluded foreign values produce empty state arrays, never a disagreement by themselves. No separate `state_normalization` configuration is required. Original source text remains in `record_payload`; HealthLink’s separate HCP state input is retained by its staging model. QuantumMedica’s measured values contain no recognized state, and Haymarket has no state field. See [state comparison](metrics/14_conflicting_npis_share_state.md).

## Facility-comparison inputs

The local metric joins record `npi` to trimmed `bq_bi.analytics_prod.npi_facility_association.provider_npi` and unions distinct `facility_npis` across every retained rank. The reference combines Claims, CMS, HealthLink and NPPES support. It has no activity date; it cannot align associations to historical vendor conflict days. Provider-scoped cluster numbers, cluster labels, state values and rank-1 selection are not used as facility identity. See [facility overlap](metrics/15_conflicting_npis_share_facility.md) for missingness, retained evidence and publication status.

## Specialty-comparison inputs

The local metric reads all fifteen `healthcare_provider_taxonomy_code_<1..15>` fields from `iceberg.npi.nppes_npidata_latest`, normalizes code text, and accepts only codes present in `iceberg.npi.npi_taxonomy.code`. The join uses the NPPES `npi` converted to text and the record’s cleaned `npi`. All recognized codes contribute; primary-taxonomy switches do not select or weight them. Reference duplicates aggregate before joining and cannot multiply metric rows. The current readable reference is not aligned to historical vendor days. Vendor specialty names, registry display labels and broad classifications are not fallback codes. See [specialty overlap](metrics/16_conflicting_npis_share_specialty.md) for statistics and publication status.

## NPI lifecycle inputs

The local `npi_registry_status` metric joins cleaned record `npi` to text-converted `iceberg.npi.nppes_npidata_latest.npi` and reads `npi_deactivation_date`, `npi_reactivation_date`, `replacement_npi`, and `npi_deactivation_reason_code`. It aggregates identical trimmed lifecycle tuples and preserves original values. Contradictory tuples are unknown; last-update dates never choose an arbitrary winner. The evaluation date defaults to Europe/Paris today and can be fixed with `registry_status_as_of_day`; this does not restore historical NPPES versions. No links are filtered or redirected.

This reference differs from `iceberg.npi.npi_reference`, which supplies `registry_npi_present` and registry-name comparisons. The two presence notions are not overwritten or assumed identical. Missing NPPES evidence is `not_found`, not proof of an invalid provider. See [lifecycle definitions, raw evidence and counts](metrics/17_npi_registry_status.md).

## Vendor/facility state and UID geography

The rank-1 reference is `bq_bi.analytics_prod.npi_facility_locations_with_ids`: join `npi_facility_provider_npi` to record `npi`, normalize `state_code`, and require nonblank `location`. Collapse every rank-1 group before joining; conflicting or incomplete evidence remains unknown. Compare each exact record’s existing `source_state_values`. This is a separate metric from shared facilities across conflicting NPIs.

Cookie evidence joins normalized email SHA-256 to `iceberg.thirdparty.liveintent_idsync.hashedemail_sha256`; `day` bounds historical mappings and `uids` contains pipe-separated namespace/UID tokens. UID prefixes remain intact; namespaces remain auditable. Join exact UID and mapping date to `iceberg.crossscreen.nscreen_geo_daily_ua` (`day`, `uid`, `geo`). Numeric ZIP3 is left-padded and mapped through `iceberg.jteixeira_ipa.tmp_zip3_to_state` (`zip3`, `state`), after collapsing duplicate/ambiguous keys. The provider-derived map is approximate. Persisted daily state files are not used.

Evaluation uses seven completed days before Europe/Paris today, configurable with `location_evidence_day`. Missing metadata dates remain explicit, and source-date presence does not prove complete rows. Daily geo snapshots can share a 15-day hourly lookback. Rank recognized states by distinct dates per UID before email joins; tied winners supply no state agreement. Current-window evidence is not historical vendor-day reconstruction. See [facility comparison](metrics/18_vendor_facility_state.md) and [cookie evidence](metrics/19_cookie_location_evidence.md). Both passed native fixtures, all vendor plans and full-population read-only measurement on October 29, 2026, and were published after full-build validation on October 29, 2026.

## Link freshness dates

[Link freshness](metrics/20_link_freshness.md) uses `last_seen_day` from retained eligible vendor records. The latest day is calculated within each source/email/NPI, then within each vendor. Endato, RocketReach and DRDB remain undated. Invalid source-day text contributes no parsed date. Future parsed dates remain visible but make the vendor age and link lags unknown until the evaluation date reaches them. The vendor baseline excludes records without eligible email/NPI keys and does not certify raw-delivery completeness. Reference, cookie and publication timestamps never fill missing vendor observation dates.

## Link stability dates

[Link stability](metrics/21_link_stability.md) unions exact `observed_days` and `conflict_days`, separately within each vendor. Dates do not come from references, cookies or publication timestamps. Counts represent known distinct days, not raw records or delivery frequency. Endato, RocketReach and DRDB retain zero known-day counts and NULL shares. `link_stability_has_undated_observations` flags any undated or invalid-day evidence across the entire vendor/email history, including another NPI whose overlap timing cannot be established. Known-day shares remain usable with that qualification. Calendar gaps are not filled.

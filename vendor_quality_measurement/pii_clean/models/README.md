# Model boundaries

The project uses Jinja SQL with `source()`, `ref()`, shared macros, source declarations and schema files.

| Layer | Contents |
|---|---|
| [Staging](staging/README.md) | One row-preserving model per vendor input table. Conversions and cleaned helpers only. |
| [Intermediate](intermediate/README.md) | Source-specific record transformations, enrichment joins, evidence, specific metrics and common metrics. |
| [Final](final/README.md) | Union of reviewed vendor metrics into `pii_clean`; scoring deferred. |

HealthLink, QuantumMedica and Medscape each have multiple staging inputs. DRDB's two tables stay separate in staging. Intermediate can combine tables within the same vendor; the cross-vendor union is stored in int_pii__metrics before downstream cookie enrichment.

For HealthLink, start with [email staging](staging/stg_healthlink__email.sql) and the [vendor CTE pipeline](intermediate/int_healthlink__metrics.sql). The provider staging table supplies names through a separate NPI join, without changing observation counts.

Exact-record CTEs combine only raw rows identical except for `day`. Metrics use `metric_row_id` (record plus email position); email–NPI deduplication is deferred.

Historical observation facts, `email_format_valid`, `email_role_account`, `email_domain_class`, three name comparisons, within-vendor email–NPI multiplicity, reassignment, linkage conflict, vendor name consistency and state sharing across conflicting NPIs are currently computed. Names use shared nickname and NPI-reference lookups. Facility-NPI overlap is published and validated. Specialty-code overlap has five published evidence columns. It uses dictionary-recognized exact NPPES taxonomy codes. NPI lifecycle status has eleven published evidence/status columns. It preserves uncertain dates and self-replacements without dropping or redirecting links. Vendor/facility state comparison and descriptive cookie-location evidence are published. Native Trino fixtures, all seven vendor plans and full-population read-only measurements passed on October 29, 2026. The October 29 cookie summaries used seven completed days before evaluation and preserve historical vendor records. All five groups passed full publication and integrity checks on October 29, 2026. Other claims enrichments await metric-specific review. Missing reference evidence is unknown.

Current vendor views and stored core have 124 fields. The complete canonical table has 154 fields and 75,656,369 records across all seven sources at snapshot `8811920360682490090`. It includes NPI identity, vendor specialty/profession, sequential history and registration supersession. Cookie processing runs in the separate [downstream model](../docs/cookie_stage.md). The [complete email lookup](../docs/email_lookup.md) adds six display/comparison fields for 160 outputs. [Publication checks](../docs/build_recovery.md).

The runner creates source staging and intermediate views. `build` also publishes the final `pii_clean` table; `final` refreshes cookie enrichment using stored core. See [commands and validation status](../README.md).

Shared name dependencies are `stg_npi__reference`, `int_npi__names`, `int_name__variants` and the `nicknames` seed view. Each vendor has one `int_<vendor>__metrics` model, with `name_inputs` and `name_metrics` CTEs inside it. CSV seeds are rendered to typed SQL values by the runner; the original nickname CSV is retained for review.

[Link freshness](../docs/metrics/20_link_freshness.md) adds five date/day-count columns in each vendor model. A narrow source/email/NPI aggregation reads eligible metric records and joins back after reference enrichment, preserving every output record. Source age and link lag use vendor observation dates only; missing and future-dated evidence stays unknown. The core union preserves these fields.

[Link stability](../docs/metrics/21_link_stability.md) adds six columns per vendor: three distinct-day counts, presence and overlap fractions, and an email-level incomplete-date flag. It reads narrow observation/conflict inputs separately from reference enrichment and joins the link summaries back to every original record. No link deduplication or scoring is applied to the output.

[Metric 22](../docs/metrics/22_npi_identity.md) adds twelve NPI structure, registry entity-type and provenance fields. It evaluates distinct identifiers from narrow metric inputs and joins back to preserve record grain. These fields are published in the canonical table and read directly by the complete lookup.

Vendor specialty/profession evidence uses same-day metadata joins in the existing vendor model files. QuantumMedica and Medscape metadata now have metric consumers. Eight new fields retain vendor labels, raw/day-specific provenance and conflict peer comparisons. These fields are published across all seven sources.

Medscape applies cumulative NPI opt-out exclusion in intermediate email eligibility, before all metric calculations. All raw attribution and opt-out rows remain available in staging. Other vendors retain their existing eligibility rules. See [the opt-out policy](../docs/medscape_optout.md).

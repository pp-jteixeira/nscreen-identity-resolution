# Model boundaries

The project uses Jinja SQL with `source()`, `ref()`, shared macros, source declarations and schema files.

| Layer | Contents |
|---|---|
| [Staging](staging/README.md) | One row-preserving model per vendor input table. Conversions and cleaned helpers only. |
| [Intermediate](intermediate/README.md) | Record versions, email positions, link collapse, enrichment joins, evidence, specific metrics and common metrics. |
| [Final](final/README.md) | Stored cookie-enriched source outputs combined in `pii_clean`; scoring deferred. |

HealthLink, QuantumMedica and Medscape each have multiple staging inputs. DRDB's two tables stay separate in staging and are merged at link grain in intermediate. Intermediate can combine tables within the same vendor; the cross-vendor union is stored in int_pii__metrics before downstream cookie enrichment.

For HealthLink, start with [email staging](staging/stg_healthlink__email.sql) and the [vendor CTE pipeline](intermediate/int_healthlink__metrics.sql). The provider staging table supplies names through a separate NPI join, without changing observation counts.

Version CTEs combine raw rows identical except for `day` and the volatile fields declared in [record_schemas.json](record_schemas.json). Metrics are computed at link grain: one row per source, email and NPI, keyed by `link_id`. Each link keeps its versions in `record_ids` and `attribute_versions`. Indicators that depend on one record's attributes have an all-version form and a `_latest` form; see the [data dictionary](../docs/data_dictionary.md#versions-volatile-fields-and-the-latest-version).

Computed metrics are historical observation facts, `email_format_valid`, `email_role_account`, `email_domain_class`, three name comparisons, within-vendor email–NPI multiplicity, reassignment, linkage conflict, vendor name consistency, and name, state, facility, NPPES specialty and vendor specialty/profession sharing across conflicting NPIs. Names use shared nickname and NPI-reference lookups. Specialty-code overlap uses dictionary-recognized exact NPPES taxonomy codes. NPI lifecycle status preserves uncertain dates and self-replacements without dropping or redirecting links. Vendor/facility state comparison and descriptive cookie-location evidence are also computed. Missing reference evidence is unknown.

Vendor models and stored core use 139 fields, including four [name-explanation fields](../docs/name_match_evidence.md). The final contract has 180 fields: core, 10 domain fields and 31 cookie fields. It includes NPI identity, vendor specialty/profession, sequential history and registration supersession. Cookie processing runs source by source in the separate [downstream model](../docs/cookie_stage.md), then combines enriched outputs. The [complete email lookup](../docs/email_lookup.md) adds six display/comparison helpers to published columns.

The runner creates source staging and intermediate views. `build` also publishes the final `pii_clean` table; `final` refreshes cookie enrichment using stored core. See [commands and validation](../README.md).

Shared name dependencies are `stg_npi__reference`, `int_npi__names`, `int_name__variants` and the `nicknames` seed view. Each vendor has one `int_<vendor>__metrics` model; the shared link metric chain in [link_metrics.sql](../macros/link_metrics.sql) supplies its `name_inputs` and `name_metrics` CTEs. CSV seeds are rendered to typed SQL values by the runner; the original nickname CSV is retained for review.

[Link freshness](../docs/metrics/20_link_freshness.md) adds five date/day-count columns in each vendor model. Source age and link lag use vendor observation dates only; missing and future-dated evidence stays unknown.

[Link stability](../docs/metrics/21_link_stability.md) adds six columns per vendor: three distinct-day counts, presence and overlap fractions, and an email-level incomplete-date flag. It reads narrow observation/conflict inputs separately from reference enrichment. No scoring is applied.

[Metric 22](../docs/metrics/22_npi_identity.md) adds twelve NPI structure, registry entity-type and provenance fields. It evaluates distinct identifiers from narrow link inputs and joins back by link.

Vendor specialty/profession evidence uses same-day metadata joins in the vendor model files. Medscape metadata joins by NPI, day and registration GUID, using each GUID's own days; DRDB uses the raw `specialty` labels of all versions. Eight fields retain vendor labels, raw/day-specific provenance and conflict peer comparisons.

Medscape applies cumulative NPI opt-out exclusion before grouping versions, ahead of all metric calculations. All raw attribution and opt-out rows remain available in staging. Other vendors keep their own eligibility rules. See [the opt-out policy](../docs/medscape_optout.md).

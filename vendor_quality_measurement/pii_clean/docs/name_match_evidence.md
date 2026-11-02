# Stored name-match evidence

Seven vendor models store name-comparison explanations alongside the nullable name indicators.

## Grain and contents

Rows have link grain: one source/email/NPI link, keyed by `link_id`. Comparisons cover every usable vendor name across the link's versions. `name_match_evidence` is a typed array of distinct comparisons with normalized source/registry first and last names, `first_name_match_kind`, `last_name_match_kind`, `match_class`, and the three comparison-level email/source, email/registry and vendor/registry booleans. `vendor_registry_match_classes` is the sorted distinct set of classes. `name_match_evaluated_at` records evaluation time; `name_match_definition_version` is `stored_name_comparisons_v1`.

The shared name join supplies these comparisons inside the `name_metrics` CTE of the [link metric chain](../macros/link_metrics.sql). Its input holds every distinct vendor name pair of the link's versions; comparisons are aggregated to one row per link. No additional reference join or model is introduced. All usable source-name pairs are retained. When none exist, source names are represented as null and comparisons remain `unknown`; raw names of each version remain in the `record_payload` of `attribute_versions`. HealthLink names come from its separate HCP reference and are not copied into the email payload. Unusable source names alongside usable names do not add redundant unknown comparisons. Missing or unusable registry variants remain explicit, even alongside a matching reference variant.

No best-match winner is selected. Repeated identical comparisons collapse, while distinct matching, partial and disagreeing comparisons remain. A link with classes `[exact, last_only]` still has `vendor_name_matches_registry_name = true`; its disagreeing comparison remains available, for example from an older version with a different surname. Array size measures distinct comparisons, not independent confirmations.

## Class rules

| Class | Meaning | Vendor/registry boolean |
|---|---|---|
| `exact` | Both parts agree exactly under the existing normalization rules. | true |
| `nickname` | First-name nickname expansions overlap; neither part requires an edit. | true |
| `token` | Shared tokens or a permitted first-token prefix establish agreement; no nickname/edit takes priority. | true |
| `edit` | Both parts agree, with at least one using the allowed edit-distance rule. | true |
| `first_only` | First names agree; last names disagree. | false |
| `last_only` | Last names agree; first names disagree. | false |
| `none` | Neither part agrees. | false |
| `unknown` | At least one complete usable name pair is missing. | null |

For complete agreements, precedence is edit, nickname, token, exact. Component kinds preserve the individual reasons. Both kinds become `unknown` when a complete name pair is unusable. First-name prefix matches belong to `token`. Exact last-name comparison uses letters only, so punctuation differences may be exact. [Metric 07](metrics/07_vendor_name_matches_registry_name.md) defines the normalization, nickname and edit boundaries.

The all-version booleans aggregate with `bool_or` across the link's distinct names: any true wins; otherwise any false gives false; all unknown gives null.

## Latest-version indicators

`email_matches_source_name_latest` and `vendor_name_matches_registry_name_latest` apply the same rules to the name pair of the latest version only: the version with the unique greatest `last_seen_day`, or the only version. They are NULL when `latest_record_id` is NULL, that is when several undated versions exist or the greatest day is tied. HealthLink takes names from its HCP reference by NPI, so its `_latest` values equal the all-version values. `email_matches_registry_name` does not use vendor names and has no `_latest` form. `name_match_evidence` and `vendor_registry_match_classes` explain the all-version indicators. The [integrity check](../tests/name_match_evidence.sql) reconstructs all three booleans from the stored evidence, verifies classes and component kinds, rejects duplicate/empty comparisons, and checks evaluation metadata.

## Examples and statistics

The [complete email lookup](email_lookup.md) shows stored comparisons for one email, and the [class statistics SQL](../sql/statistics/07_name_match_classes.sql) reports per-source class counts. Class counts overlap within a link: a link whose versions carry several names can hold several classes. Do not sum class counts as disjoint populations or treat repeated comparisons as independent confirmations. A source without vendor names gives 100% unknown, meaning comparison is unavailable, not that every name disagrees.

## Validation

Name fixtures cover all eight classes, duplicate references, multiple reference outcomes, unknown source/registry names, nullable aggregation and rejection of inconsistent evidence. Record-grain fixtures cover links with several versions, including the all-version and `_latest` indicators. These run through Trino-to-DuckDB translation. DuckDB does not execute Trino's custom array-sort comparator; native fixtures cover null-containing arrays, all eight classes and the integrity query.

## Publication and lookup

The final publication uses [source-scoped cookie builds](cookie_stage.md) from verified core; cookie publication preserves the four explanation fields. Refreshing cookies alone cannot create missing name evidence. For a full refresh from source data, use `tools/pipeline.py build --direct`; refresh cookies with `tools/pipeline.py cookies`.

The [complete email lookup](email_lookup.md) includes the four explanation fields and returns 171 outputs: 165 stored fields plus six helpers. Its SQL is regenerated from the [final schema](../models/final/schema.yml). The lookup preserves stored evidence and does not recompute name matches.

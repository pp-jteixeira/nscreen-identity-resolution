# Cookie-location evidence

**Question:** what UID-linked states were observed during the three completed days before evaluation?

**Target:** `cookie_location_status`, UID/day counts, `cookie_state_values`, vendor/facility comparisons (`cookie_vendor_state_evidence`, `cookie_vendor_state_evidence_latest`, `cookie_facility_state_evidence`) and coverage fields in `iceberg.jteixeira_ipa.pii_clean`, populated from source-scoped `int_cookie__metrics` evidence and link-specific comparisons. One row per source/email/NPI link; key: `source`, `link_id`. [Output reference](../../results/location_evidence_summary.md#output-columns).

## How it is computed

Hash normalized email with SHA-256 and match `iceberg.thirdparty.liveintent_idsync.hashedemail_sha256`. Parse `uids` as pipe-separated `type:uid` tokens, preserving UID strings and namespace labels. Reject malformed tokens; deduplicate hash/day/UID tuples. These identifiers are not verified browser cookies.

Join UID to same-day `iceberg.crossscreen.nscreen_geo_daily_ua.uid`, mapping numeric `geo` ZIP3 through `iceberg.jteixeira_ipa.tmp_zip3_to_state`. Collapse duplicate ZIP3 keys; ambiguous mappings remain unknown. This provider-derived lookup is not an authoritative postal boundary map.

Rank recognized states per UID by distinct observed dates **before** the email join. One deterministic winner is retained; tied winners establish no state agreement. Count mapped, observed, located and eligible UID-days separately. A primary state must appear on the mapping day. Duplicate mappings cannot add observations.

`cookie_state_values` contains only untied same-day primary states. Compare these separately with the link's vendor states and the usable facility state. Missing observations or references remain explicit unknowns, not mismatches. No scores or fractional votes are calculated.

`cookie_vendor_state_evidence` compares with `source_state_values`, the union of recognized states across all versions of the link. `cookie_vendor_state_evidence_latest` applies the same comparison to `source_state_values_latest`, the states of the link's latest version only; it is NULL when the link has no single latest version. Cookie evidence itself depends only on the email, so every version of a link shares it.

## Real examples

No executed examples exist yet for this definition.

**What differentiates outcomes:** A usable untied primary state can corroborate the vendor state or exclude it, so `observed` does not itself mean agreement. A tied primary state cannot supply agreement. A mapped UID without a qualifying state is different from having no mapping at all. `unknown_state` has observations but no recognized state. These counts are UID evidence, not independent confirmations or verified people.

## Statistics by source

No measurements exist yet for this definition. Cookie observations are limited to the stored three-day window.

[Statistics SQL 1](../../sql/statistics/19_cookie_location_evidence.sql) · [Statistics SQL 2](../../sql/statistics/19_cookie_location_evidence_statement_002.sql) · [Statistics SQL 3](../../sql/statistics/19_cookie_location_evidence_statement_003.sql)

Percentages use links. Location statuses partition the links within each source. Vendor-state agreement is a separate link-level outcome. Date presence does not prove complete ingestion. Snapshot days can share upstream history and are not independent confirmations.

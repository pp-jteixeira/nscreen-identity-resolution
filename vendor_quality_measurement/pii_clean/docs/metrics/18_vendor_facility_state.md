# Vendor state versus facility state

**Question:** do the vendor states reported for this link agree with its NPI’s preferred historical facility state?

**Target:** `vendor_state_evidence`, nullable `vendor_state_corroborated`, `facility_primary_state` and the latest-version companions `vendor_state_evidence_latest`, `vendor_state_corroborated_latest` and `source_state_values_latest` in `iceberg.jteixeira_ipa.pii__int_<vendor>__metrics` and `iceberg.jteixeira_ipa.pii_clean`. One row per source/email/NPI link; key: `source`, `link_id`. `location_evidence_version` is `link_vendor_facility_state_v1`.

## How it is computed

Read rank-1 rows from `bq_bi.analytics_prod.npi_facility_locations_with_ids`; join `npi_facility_provider_npi` to the link's `npi`. Normalize `state_code` with the existing recognized US state/DC/territory mapping. Group by NPI before joining so duplicate reference rows never multiply links.

A reference is usable only when every rank-1 row has a nonblank location and a recognized state, with exactly one distinct state. Conflicting states, missing states, missing locations and absent associations remain explicit.

Compare the link's `source_state_values`, the union of recognized states across all versions of the link:

```sql
contains(source_state_values, facility_primary_state)
```

| Outcome | Meaning |
|---|---|
| `corroborated` | One vendor state matches; boolean true. |
| `not_corroborated` | Known vendor states exclude the reference; false. |
| `mixed_vendor_states` | Multiple vendor states include the reference; null. |
| `unknown_vendor_state` | Usable reference without recognized vendor states; null. |
| `unknown_facility` | No usable reference; null. |

Because the unsuffixed columns use the union, a link whose versions report different states that include the reference is `mixed_vendor_states`. The `_latest` columns apply the same comparison to `source_state_values_latest`, the recognized states of the link's latest version (`latest_record_id`) only. All three `_latest` columns are NULL when the link has no single latest version.

HealthLink states come from its retained HCP reference by NPI, so its `_latest` columns equal the all-version columns. Other vendors use the states of the link's email-bearing versions. QuantumMedica has no usable states, and Haymarket has no state field. Unknowns stay unknown.

This mixed-source historical facility reference has no vendor-day alignment and can share vendor lineage. Agreement proves neither current attendance nor email ownership. Evaluation day defaults to Europe/Paris today; `location_evidence_day` fixes it.

## Real examples

No executed examples exist yet for this definition.

**What differentiates outcomes:** One matching vendor state gives true; known states excluding the usable facility state give false. A mixture including the facility state remains NULL. Missing vendor evidence and unusable facility evidence also remain NULL, with different status labels. None proves current attendance.

## Statistics by source

No measurements exist yet for this definition.

[Statistics SQL 1](../../sql/statistics/18_vendor_facility_state.sql) · [Statistics SQL 2](../../sql/statistics/18_vendor_facility_state_statement_002.sql)

Percentages use all links and partition each source population. Mixed evidence and missing evidence remain NULL for the boolean agreement flag. Geographic agreement does not establish attendance or ownership.

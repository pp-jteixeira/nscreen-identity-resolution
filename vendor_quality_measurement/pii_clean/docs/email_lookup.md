# PII Clean email lookup: all attributes and metrics

Last updated: 2026-10-30.

**Prepared metric 22 update:** the generated lookup requires 126 stored columns. Canonical `pii_clean` still has 114 pending publication. Validate this version against the candidate relation before publication; the published-table shortcut remains available.

Use the **complete lookup** to inspect every implemented metric for one email across all vendors, NPIs and retained history. Each output row remains one exact source record and email position, keyed by `source`, `metric_row_id`. Names, states and indicators stay attached to their own records; no email–NPI deduplication occurs.

## Run the complete lookup

After metric 22 publication, open [email_lookup_full.sql](../sql/email_lookup_full.sql), copy the entire statement into Trino, and replace `person@example.com` **once** in the opening `params` CTE. No table or view is created. No matching records produces no rows.

The query reads all **126 model columns** directly from `iceberg.jteixeira_ipa.pii_clean`, plus readable `name`/`state` and four name-comparison counts. Those six helpers use stored arrays. No vendor models, reference tables or enrichment joins are executed.

| Metric group | Included outputs |
|---|---|
| Published indicators/history | Email format, role/domain, name matching, multiplicity, reassignment, name conflicts, shared names/states and observation history. |
| Shared facility | `conflicting_npis_share_facility`, facility IDs and peer intersections. |
| Shared specialty | `conflicting_npis_share_specialty`, recognized taxonomy codes and peer intersections. |
| NPI lifecycle | `npi_registry_status`, uncertainty reason, dates, replacement and raw lifecycle evidence. |
| Vendor versus facility state | `vendor_state_evidence`, nullable `vendor_state_corroborated`, facility state and reference quality. |
| Cookie location | `cookie_location_status`, UID/day counts, states, ties, vendor/facility comparisons and source-date coverage. |
| Link freshness | Stored evaluation day, vendor/link latest observation dates, source age and link lag. |
| Link stability | Distinct email/link/conflict day counts, presence and overlap fractions, and incomplete-date flag. |
| NPI validity and entity type | Structural checks, registry classification, raw type evidence, counts and provenance. |

The email filter retains **every source, NPI and record for the selected email**. Stored metrics, peer comparisons and email-level counts are returned unchanged. Only the six display/count helpers are calculated at lookup time.

Evaluation dates come from the published rows: `npi_registry_status_as_of_day`, `cookie_location_window_start`/`cookie_location_window_end`, and `link_freshness_as_of_day`. The lookup does not reevaluate evidence for today. Reference changes affect results only after a pipeline refresh. Stored lifecycle and geographic evidence still does not reconstruct status or attendance on historical vendor dates.

The query scans the published table with an email filter. It avoids raw location/reference scans; runtime still depends on how efficiently the stored table can locate that email.

## Published-table shortcut

[The shorter query](../sql/email_lookup_published.sql) selects a smaller subset of the same stored attributes and indicators. Both queries read `pii_clean` directly. Replace its email once as well; use the complete query for all 126 model columns.

## Attributes

| Column | Meaning |
| --- | --- |
| `email`, `source`, `npi` | Email, vendor, and reported provider NPI for this record. |
| `name` | Usable normalized vendor first/last names from `source_name_values`, formatted for reading. HealthLink uses its HCP reference. Registry names never fill missing vendor names. |
| `state` | Recognized US state/DC/territory codes from `source_state_values`. HealthLink uses its HCP reference. Multiple states remain visible. |
| `first_seen_day`, `last_seen_day` | Earliest and latest valid source delivery dates for this exact record. Not a continuous activity interval. |
| `metric_row_id` | Exact source-record/email-position identifier; use with `source` for evidence inspection. |

Empty display strings or null names/states indicate missing usable normalized values. Original malformed or incomplete attributes may still exist in `record_payload`. Displayed names are normalized rather than original casing and spelling; consult raw payload when needed.

The pipeline normalizes stored states through the shared [state macro](../macros/state_consistency.sql); the lookup does not rerun normalization. It maps recognized full US state names and codes, DC and five territories to two-letter codes after whitespace/case normalization. Unrecognized or explicitly foreign values stay unknown. QuantumMedica has no recognized state in the saved measurements; Haymarket has no state field. See the [source-state inputs](00_source_map.md#state-comparison-inputs), including HealthLink’s separate HCP reference.

## Metrics and indicators

| Columns | Meaning and scope |
| --- | --- |
| `observation_count` | Retained observations of this exact source record; repeated snapshots are not independent confirmations. |
| `observed_day_count` | Distinct valid delivery days for this record; unknown when no valid date exists. |
| `undated_observation_count` | Observations of this record without a valid delivery date. |
| `email_format_valid` | Email format check. |
| `email_role_account` | Mailbox matches the role-account rules; does not prove shared ownership. |
| `email_domain_class` | Domain classification defined by the email-domain metric. |
| `email_matches_source_name` | Nullable fuzzy email-to-vendor-name comparison for this record. |
| `email_matches_registry_name` | Nullable fuzzy email-to-registry-name comparison. |
| `vendor_name_matches_registry_name` | Nullable fuzzy vendor-to-registry-name comparison. |
| `source_name_usable`, `registry_name_usable` | Whether usable names exist for the relevant comparison. |
| `registry_npi_present` | Whether the NPI exists in the registry-name reference. |
| `email_npi_count`, `email_has_multiple_npis` | Distinct reported NPIs for this source/email across retained history, and whether the count exceeds one. These values repeat across records for that source/email. |
| `has_been_reassigned` | Change in daily NPI sets for this source/email; nullable where dates prevent a conclusion. |
| `has_conflict_linkage` | Multiple NPIs on this record's exact observed days. Endato, RocketReach, and DRDB compare their available undated vendor snapshots instead. |
| `email_name_count` | Distinct usable normalized first/last pairs for this source/email across history; zero means no usable names. |
| `email_npi_has_name_conflict` | Incompatible usable names within this source/email/NPI history; null with no usable names. |
| `conflicting_npis_share_name` | Whether any conflict peer shares this record's name under fuzzy rules. False only for all known mismatches; otherwise may be null. |
| `conflicting_npis_share_state` | Whether any conflict peer shares a normalized state. False only for all known mismatches; otherwise may be null. |
| `link_freshness_as_of_day` | Date used to evaluate stored freshness. The lookup does not update it to today. |
| `source_latest_observed_day`, `source_age_days` | Latest observation among the vendor's eligible records and days from that date to evaluation. Unknown for undated vendors; future maxima make age null. |
| `link_last_observed_day`, `link_lag_days` | Latest observation within source/email/NPI and days behind the vendor maximum. Repeated on every record of the link. Undated links and future source maxima give null lag. No stale threshold. |
| `email_observed_day_count`, `link_observed_day_count`, `link_conflict_day_count` | Distinct known days for the vendor/email, vendor/email/NPI and this link's overlap with other NPIs. Repeated records do not inflate counts. |
| `link_presence_share`, `link_overlap_share` | Fractions from 0 to 1. Presence divides link days by email days; overlap divides conflict days by link days. Both are NULL for an undated link. Multiply by 100 for percentages. |
| `link_stability_has_undated_observations` | Any undated or invalid-day evidence for the vendor/email, including peer NPIs. Shares describe known days only. Zero known days does not mean confirmed absence. |
| `npi_format_valid`, `npi_checksum_valid`, `npi_structure_valid` | Separate format and prefixed-Luhn checks, plus their conjunction. Missing inputs stay unknown. Passing structure does not prove registry existence or activity. |
| `npi_structure_reason` | Missing, malformed, unsupported prefix, checksum failure or valid. |
| `npi_entity_type`, `npi_entity_type_reason` | Registry consensus classifies individual/organization or preserves unknown with its reason. Independent of structure and lifecycle. |
| `npi_entity_type_evidence`, `npi_entity_type_reference_row_count`, `npi_entity_type_variant_count` | Raw entity-code rows and counts of matched rows/normalized variants, including missing codes. |
| `npi_identity_as_of_day`, `npi_identity_reference_table`, `npi_identity_definition_version` | Evaluation date, reference relation and rule version. The date is not historical vendor-day or reference delivery evidence. |
| `name_comparison_count` | Number of peer name-comparison entries for this record, not unique NPIs or people. |
| `name_mismatch_count`, `shared_name_count`, `unknown_name_match_count` | Entries with `shares_name` false, true, or null, respectively. A null array element also counts as unknown. These counts sum to `name_comparison_count`. |

For entry outcome percentages, use `100.0 * outcome_count / nullif(name_comparison_count, 0)`. Null or empty arrays contribute zero comparisons; zero entries do not establish agreement. Keep nullable indicators unknown rather than converting them to false. Do not sum repeated email-level metrics across records. See the [metric index](metrics/README.md) for full definitions.

## Additional evidence and interpretation

All complete-query rows retain `record_payload`, original record IDs, exact `observed_days`/`conflict_days`, normalized name/state arrays and peer comparison details. All evidence groups are read unchanged from the published snapshot, including stored nulls, provenance and evaluation dates.

| Group | Meaning and limitations |
|---|---|
| [Shared facility](metrics/15_conflicting_npis_share_facility.md) | Exact retained facility-NPI overlap within conflict contexts. Missing facility sets remain unknown. |
| [Shared specialty](metrics/16_conflicting_npis_share_specialty.md) | Exact recognized NPPES taxonomy-code overlap; no broad-label fallback. Missing codes remain unknown. |
| [NPI lifecycle](metrics/17_npi_registry_status.md) | NPPES classification captured at publication, separate from registry-name presence. Missing matches are not_found; conflicting, malformed, future or self-referential evidence is unknown. No link is redirected. |
| [Vendor/facility state](metrics/18_vendor_facility_state.md) | Each record’s states versus its own NPI’s usable rank-1 facility state. Multiple states including the reference are mixed, not false. |
| [Cookie geography](metrics/19_cookie_location_evidence.md) | Untied same-day primary-state observations. No usable parsed mapping is not proof that no cookie exists. Missing dates and observed disagreement remain separate. |
| [Link freshness](metrics/20_link_freshness.md) | Vendor observation dates only. Zero lag can coexist with an old feed. Repeated delivery is not independent verification; missing links do not prove deletion. |
| [Link stability](metrics/21_link_stability.md) | Known-day persistence and overlap. Full presence over one day is weak historical evidence; shares do not establish switching frequency or ownership. |

The complete query also includes the detailed [lifecycle output reference](../results/registry_status_summary.md#output-columns) and [location output reference](../results/location_evidence_summary.md#output-columns). Tied UID primary states supply no agreement. Daily snapshots are not independent confirmations. Do not sum per-email UID/day counts repeated across source records.

For population coverage, percentages use all distinct source/email/NPI links within each vendor. Historical state changes can put one link in multiple record-level comparison groups. Cookie location-status groups partition emails and links within a vendor. No new hard filters, weights or identity scores are introduced by this lookup.

## Validation and publication status

The earlier enrichment-based lookup passed native validation and planning with 46 fragments, plus three synthetic records across two NPIs. Those checks describe the earlier query. The historical validation output is not retained.

The direct lookup passed native Trino schema validation on October 29, 2026. Native synthetic execution preserved all 103 stored fields across three matching records and verified the six helpers. Full execution for an existing email returned 17 records with 109 columns in 13.6 seconds. No email identifiers or result values were retained in the validation evidence. Query metadata and the standalone SQL are historical output, not retained: `../results/email_lookup_published_validation_20261029.json`. This sample does not guarantee the same runtime for every email.

The current local lookup tests check all 126 declared fields, including `computed_at` and evaluation dates, for exact preservation. They cover multiple vendors and NPIs, repeated email positions, unmatched emails, null/empty comparison arrays, all 132 unique output names, escaped email literals, and identical SQLTools-safe generated/checked-in SQL.

The freshness-only lookup passed native Trino validation on October 30, 2026. Native synthetic execution preserved all 108 stored fields and the six helper outputs. Full execution for an existing email returned 3 records with 114 columns in 51.6 seconds. Individual identifiers and values were not retained. Evidence is historical output, not retained: `../results/email_lookup_published_validation_20261030.json`.

The stability lookup passed native Trino validation on October 30, 2026. Native fixtures preserved all 114 stored fields and the six helpers. Full execution for an existing email returned 11 records with 120 columns in 8.1 seconds. Individual result values were not retained.

The prepared metric 22 lookup passed native fixtures for all 126 fields and six helpers. Full execution against the validated candidate returned 1 record with 132 outputs in 9.82 seconds. Canonical publication remains pending. [Candidate validation](../results/npi_identity_20261030/report.md).

The underlying metrics have their separately dated native and population validations. The October 29 location measurement retained 75,564,265 metric rows; usable locations accompanied 2,728,645 of 26,730,605 source/email/NPI links (10.21%). Mapping dates covered 6/7 days (85.71%), missing October 28; geo dates covered 7/7 (100%). These counts are dated measurements, not a guarantee of today’s reference contents or individual lookup results. Date presence does not establish full data completeness.

The October 30 stability publication contains 114 stored columns and preserves all 108 previous fields, including `computed_at`, freshness dates and reference evaluation dates. Stability uses stored dated history without an evaluation-day filter. [Stability publication report](../results/publication_stability_20261030/report.md). Running the lookup is read-only and returns stored evidence for the requested email.

## Regenerate and maintain

The complete standalone SQL is rendered from [its template](../sql/email_lookup_full.sql.j2) and the declared model columns. Display order retains the original base-column sequence. From the project directory:

```bash
../../.venv/bin/python tools/render_email_lookup.py
# Optional: render a different email to a separate file.
../../.venv/bin/python tools/render_email_lookup.py --email person@example.com --output /tmp/email_lookup.sql
```

Whenever published metrics, attributes or definitions change, update the output projection, reference, null handling, scope, denominators and validation date together. Regenerate the standalone file and validate it before marking it current. Keep the shorter shortcut explicitly labelled as a subset. Publish new columns before adding them to the lookup. Evaluation-day overrides are not supported by this lookup; dates belong to the stored publication. Preserve the [project README](../README.md) link. This maintenance does not imply a background watcher.

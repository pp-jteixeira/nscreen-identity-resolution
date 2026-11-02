# PII Clean email lookup: all attributes and metrics

The four [stored name-explanation fields](name_match_evidence.md) are included in the lookup.

Use the **complete lookup** to inspect every published metric for one email across all vendors, NPIs and retained history. Each output row is one source/email/NPI link, keyed by `link_id`, ordered by source, NPI and `link_id`. Each link merges every version of the source records that report it; `attribute_versions` shows the versions with their payloads. No cross-vendor deduplication occurs.

## Run the complete lookup

Open [email_lookup_full.sql](../sql/email_lookup_full.sql), copy the entire statement into Trino, and replace `person@example.com` **once** in the opening `params` CTE. No table or view is created. An email without links produces no rows.

The query reads all **165 model columns** directly from `iceberg.jteixeira_ipa.pii_clean`, plus readable `name`/`state` and four name-comparison counts. Those six helpers use stored arrays. No vendor models, reference tables or enrichment joins are executed.

| Metric group | Included outputs |
|---|---|
| Published indicators/history | Email format, role/domain, name matching (all-version and `_latest`), multiplicity, reassignment, name conflicts, shared names/states, observation history and versions. |
| Shared facility | `conflicting_npis_share_facility`, facility IDs and peer intersections. |
| Vendor specialty/profession | `conflicting_npis_share_vendor_specialty`, `conflicting_npis_share_vendor_profession`, normalized label arrays, raw/day-specific evidence and peer comparisons. |
| Shared NPPES specialty | `conflicting_npis_share_nppes_specialty`, recognized taxonomy codes and peer intersections. |
| NPI lifecycle | `npi_registry_status`, uncertainty reason, dates, replacement and raw lifecycle evidence. |
| Vendor versus facility state | `vendor_state_evidence`, nullable `vendor_state_corroborated`, their `_latest` forms, facility state and reference quality. |
| Cookie location | `cookie_location_status`, UID/day counts, states, ties, vendor/facility comparisons and source-date coverage. |
| Link freshness | Stored evaluation day, vendor/link latest observation dates, source age and link lag. |
| Link stability | Distinct email/link/conflict day counts, presence and overlap fractions, and incomplete-date flag. |
| Sequential history | Source/email versions, changes, swaps, flip-backs, sufficiency, evaluation cutoff and causal daily evidence. |
| Registration supersession | Medscape registration GUID, latest observed NPI set, link status and replacement evidence. |
| NPI validity and entity type | Structural checks, registry classification, raw type evidence, counts and provenance. |

The email filter retains **every stored source and NPI link for the selected email**. Medscape excludes cumulative vendor opt-out NPIs before computing metrics, so the stored table already reflects the exclusion. The lookup does not recompute opt-outs. Stored metrics, peer comparisons and email-level counts are returned unchanged. Only the six display/count helpers are calculated at lookup time.

Cookie evidence is refreshed source by source through [int_cookie__metrics](cookie_stage.md), then combined into final output. The core table has no cookie columns. Final publication stores actual cookie enrichment with its evaluation window, currently three completed days. The lookup reads stored values and never triggers a refresh.

Evaluation dates come from the published rows: `npi_registry_status_as_of_day`, `cookie_location_window_start`/`cookie_location_window_end`, `link_freshness_as_of_day`, and `sequence_as_of_day`. The lookup does not reevaluate evidence for today. Reference changes affect results only after a pipeline refresh. Stored lifecycle and geographic evidence still does not reconstruct status or attendance on historical vendor dates.

The query scans the published table with an email filter. It avoids raw location/reference scans; runtime still depends on how efficiently the stored table can locate that email.

## Published-table shortcut

[The shorter query](../sql/email_lookup_published.sql) selects a smaller subset of the same stored attributes and indicators. Both queries read `pii_clean` directly. Replace its email once as well; use the complete query for all 165 model columns.

## Attributes

| Column | Meaning |
| --- | --- |
| `email`, `source`, `npi` | Email, vendor, and reported provider NPI of this link. |
| `name` | Usable normalized vendor first/last names across the link versions, from `source_name_values`, formatted for reading. HealthLink uses its HCP reference. Registry names never fill missing vendor names. |
| `state` | Recognized US state/DC/territory codes across the link versions, from `source_state_values`. HealthLink uses its HCP reference. Multiple states remain visible; `source_state_values_latest` holds the latest version's states. |
| `first_seen_day`, `last_seen_day` | Earliest and latest valid source delivery dates across all versions of this link. Not a continuous activity interval. |
| `link_id` | SHA256 of source, email and NPI; the unique row key. |
| `record_count`, `record_ids`, `latest_record_id` | Number of merged versions, their record IDs and the latest version, if one is unique. |
| `email_origins`, `attribute_versions` | Source columns or positions of the email, and one entry per version with its days, counts and JSON identity payload. |

Empty display strings or null names/states indicate missing usable normalized values. Original malformed or incomplete attributes may still exist in the `record_payload` of each `attribute_versions` entry. Displayed names are normalized rather than original casing and spelling; consult the payload when needed.

The pipeline normalizes stored states through the shared [state macro](../macros/state_consistency.sql); the lookup does not rerun normalization. It maps recognized full US state names and codes, DC and five territories to two-letter codes after whitespace/case normalization. Unrecognized or explicitly foreign values stay unknown. QuantumMedica has no recognized state in the saved measurements; Haymarket has no state field. See the [source-state inputs](00_source_map.md#state-comparison-inputs), including HealthLink’s separate HCP reference.

## Metrics and indicators

| Columns | Meaning and scope |
| --- | --- |
| `observation_count` | Retained observations of this link, summed over its versions; repeated snapshots are not independent confirmations. |
| `observed_day_count` | Distinct valid delivery days of this link; unknown when no valid date exists. |
| `undated_observation_count` | Observations of this link without a valid delivery date. |
| `email_format_valid` | Email format check. |
| `email_role_account` | Mailbox matches the role-account rules; does not prove shared ownership. |
| `email_domain_class` | Domain classification defined by the email-domain metric. |
| `email_matches_source_name`, `email_matches_source_name_latest` | Nullable fuzzy email-to-vendor-name comparison over every usable vendor name of the link, and over the latest version only. The `_latest` value is NULL without a single latest version. |
| `email_matches_registry_name` | Nullable fuzzy email-to-registry-name comparison. |
| `vendor_name_matches_registry_name`, `vendor_name_matches_registry_name_latest` | Nullable fuzzy vendor-to-registry-name comparison over all versions, and over the latest version only. |
| `name_match_evidence` | Distinct stored source/registry name comparisons with component kinds, overall class and all three comparison-level booleans. Multiple outcomes remain together within the link. |
| `vendor_registry_match_classes` | Sorted distinct outcomes: exact, nickname, token, edit, first_only, last_only, none or unknown. Missing evidence is distinct from disagreement. |
| `name_match_evaluated_at`, `name_match_definition_version` | Stored comparison evaluation timestamp and rules version. The lookup does not refresh either value. |
| `source_name_usable`, `registry_name_usable` | Whether usable names exist for the relevant comparison. |
| `registry_npi_present` | Whether the NPI exists in the registry-name reference. |
| `email_npi_count`, `email_has_multiple_npis` | Distinct reported NPIs for this source/email across retained history, and whether the count exceeds one. These values repeat on every link of that source/email. |
| `has_been_reassigned` | Change in daily NPI sets for this source/email; nullable where dates prevent a conclusion. |
| `has_conflict_linkage` | Multiple NPIs on this link's exact observed days. Endato, RocketReach, and DRDB compare their available undated vendor snapshots instead. |
| `email_name_count` | Distinct usable normalized first/last pairs for this source/email across history; zero means no usable names. |
| `email_npi_has_name_conflict` | Incompatible usable names within this source/email/NPI history; null with no usable names. |
| `conflicting_npis_share_name` | Whether any conflict peer shares a name of this link under fuzzy rules. False only for all known mismatches; otherwise may be null. |
| `conflicting_npis_share_state` | Whether any conflict peer shares a normalized state. False only for all known mismatches; otherwise may be null. |
| `link_freshness_as_of_day` | Date used to evaluate stored freshness. The lookup does not update it to today. |
| `source_latest_observed_day`, `source_age_days` | Latest observation among the vendor's eligible links and days from that date to evaluation. Unknown for undated vendors; future maxima make age null. |
| `link_last_observed_day`, `link_lag_days` | Latest observation of this link and days behind the vendor maximum. Undated links and future source maxima give null lag. No stale threshold. |
| `email_observed_day_count`, `link_observed_day_count`, `link_conflict_day_count` | Distinct known days for the vendor/email, vendor/email/NPI and this link's overlap with other NPIs. Repeated versions do not inflate counts. |
| `link_presence_share`, `link_overlap_share` | Fractions from 0 to 1. Presence divides link days by email days; overlap divides conflict days by link days. Both are NULL for an undated link. Multiply by 100 for percentages. |
| `link_stability_has_undated_observations` | Any undated or invalid-day evidence for the vendor/email, including peer NPIs. Shares describe known days only. Zero known days does not mean confirmed absence. |
| `npi_format_valid`, `npi_checksum_valid`, `npi_structure_valid` | Separate format and prefixed-Luhn checks, plus their conjunction. Missing inputs stay unknown. Passing structure does not prove registry existence or activity. |
| `npi_structure_reason` | Missing, malformed, unsupported prefix, checksum failure or valid. |
| `npi_entity_type`, `npi_entity_type_reason` | Registry consensus classifies individual/organization or preserves unknown with its reason. Independent of structure and lifecycle. |
| `npi_entity_type_evidence`, `npi_entity_type_reference_row_count`, `npi_entity_type_variant_count` | Raw entity-code rows and counts of matched rows/normalized variants, including missing codes. |
| `npi_identity_as_of_day`, `npi_identity_reference_table`, `npi_identity_definition_version` | Evaluation date, reference relation and rule version. The date is not historical vendor-day or reference delivery evidence. |
| `name_comparison_count` | Number of peer name-comparison entries for this link, not unique NPIs or people. |
| `name_mismatch_count`, `shared_name_count`, `unknown_name_match_count` | Entries with `shares_name` false, true, or null, respectively. A null array element also counts as unknown. These counts sum to `name_comparison_count`. |

For entry outcome percentages, use `100.0 * outcome_count / nullif(name_comparison_count, 0)`. Null or empty arrays contribute zero comparisons; zero entries do not establish agreement. Keep nullable indicators unknown rather than converting them to false. Do not sum repeated email-level metrics across links. See the [metric index](metrics/README.md) for full definitions.

## Vendor specialty and profession outputs

`source_vendor_specialty_values` and `source_vendor_profession_values` summarize normalized labels across this link’s observation days; DRDB uses the raw `specialty` labels of all versions. `vendor_professional_evidence` retains those days, source tables, original labels and normalized arrays. The summary unions never replace date-specific comparisons.

`conflicting_npis_share_vendor_specialty` and `conflicting_npis_share_vendor_profession` use eligible peer links on the same conflict date, or the undated DRDB snapshot for specialty. Their `conflicting_npi_vendor_specialty_comparisons` and `conflicting_npi_vendor_profession_comparisons` arrays retain peer NPI and link IDs, evidence day, both value sets, intersections and nullable outcomes. `vendor_professional_definition_version` identifies the rules.

Any match gives true. False requires all eligible comparisons to have usable disjoint values. Missing labels, missing same-day metadata or no applicable conflict stay NULL. These are stored vendor-label metrics; they do not use registry taxonomy or credential-to-profession mappings. The lookup returns them unchanged after publication. Denominators and supported fields are documented in [metric 23](metrics/23_conflicting_npis_share_vendor_specialty.md) and [metric 24](metrics/24_conflicting_npis_share_vendor_profession.md).

## Additional evidence and interpretation

All complete-query rows retain `attribute_versions` with each version's payload, record IDs, exact `observed_days`/`conflict_days`, normalized name/state arrays and peer comparison details. All evidence groups are read unchanged from the published table, including stored nulls, provenance and evaluation dates.

[Stored name explanations](name_match_evidence.md) describe vendor-to-registry comparisons. `name_comparison_count` and its three outcome counts describe **conflicting-NPI peer comparisons**, not the registry-name array. Use `cardinality(name_match_evidence)` when inspecting the number of retained registry comparisons. Neither count measures independent confirmations.

| Group | Meaning and limitations |
|---|---|
| [Shared facility](metrics/15_conflicting_npis_share_facility.md) | Exact retained facility-NPI overlap within conflict contexts. Missing facility sets remain unknown. |
| [Shared NPPES specialty](metrics/16_conflicting_npis_share_specialty.md) | Exact recognized NPPES taxonomy-code overlap; no broad-label fallback. Missing codes remain unknown. |
| [NPI lifecycle](metrics/17_npi_registry_status.md) | NPPES classification captured at publication, separate from registry-name presence. Missing matches are not_found; conflicting, malformed, future or self-referential evidence is unknown. No link is redirected. |
| [Vendor/facility state](metrics/18_vendor_facility_state.md) | The link's states across versions, and separately the latest version's states, versus its own NPI’s usable rank-1 facility state. Multiple states including the reference are mixed, not false. |
| [Cookie geography](metrics/19_cookie_location_evidence.md) | Untied same-day primary-state observations. No usable parsed mapping is not proof that no cookie exists. Missing dates and observed disagreement remain separate. |
| [Link freshness](metrics/20_link_freshness.md) | Vendor observation dates only. Zero lag can coexist with an old feed. Repeated delivery is not independent verification; missing links do not prove deletion. |
| [Link stability](metrics/21_link_stability.md) | Known-day persistence and overlap. Full presence over one day is weak historical evidence; shares do not establish switching frequency or ownership. |

The complete query also includes the detailed [lifecycle output reference](../results/registry_status_summary.md#output-columns) and [location output reference](../results/location_evidence_summary.md#output-columns). Tied UID primary states supply no agreement. Daily snapshots are not independent confirmations. Do not sum per-email UID/day counts repeated across links.

For population coverage, percentages use all links within each vendor. A link whose versions report several states is `mixed_vendor_states` in the all-version comparison; the `_latest` comparison uses one version. Cookie location-status groups partition emails and links within a vendor. The lookup adds no hard filters, weights or identity scores.

## Validation and publication status

No full build of this definition has been published, so the lookup has no executed population cases yet. Local lookup tests check all 165 published fields, including `computed_at` and evaluation dates, for exact preservation. They cover multiple vendors and NPIs, repeated email positions, unmatched emails, null/empty comparison arrays, all 171 unique output names, escaped email literals, and identical SQLTools-safe generated/checked-in SQL. Running the lookup is read-only and returns stored evidence for the requested email.

## Regenerate and maintain

The complete standalone SQL is rendered from [its template](../sql/email_lookup_full.sql.j2) and the model columns marked as published in the final schema. Display order follows the base-column sequence of the template. From the project directory:

```bash
../../.venv/bin/python tools/render_email_lookup.py
# Optional: render a different email to a separate file.
../../.venv/bin/python tools/render_email_lookup.py --email person@example.com --output /tmp/email_lookup.sql
```

Whenever published metrics, attributes or definitions change, update the output projection, reference, null handling, scope, denominators and validation date together. Regenerate the standalone file and validate it before marking it current. Keep the shorter shortcut explicitly labelled as a subset. Mark a column `published: false` in the final schema until it exists in the warehouse. Evaluation-day overrides are not supported by this lookup; dates belong to the stored publication. Preserve the [project README](../README.md) link. This maintenance does not imply a background watcher.

## Sequential history and Medscape registration status

The complete lookup selects twenty stored sequence and registration fields. `sequence_as_of_day` applies to both groups. No lookup helper rebuilds histories or changes evaluation dates.

`n_versions_observed`, `n_npis_window`, `n_npi_changes`, `n_swaps` and `n_flipbacks` summarize all retained eligible dated history within source/email through the cutoff. `sequence_min_versions` controls `stability_history_sufficient` (default three). `sequence_history_status`, `sequence_has_undated_observations` and `sequence_definition_version` qualify these counts. Missing dated history yields NULL counts, false sufficiency and empty evidence. `sequence_daily_evidence` stores per-observed-day NPI sets, additions/removals/returns and cumulative counts. Each entry uses only observations through its own day. These are stored metrics, not display helpers. See [metric 25](metrics/25_sequential_history.md).

`registration_guid`, `registration_link_status`, `registration_latest_observed_day`, `registration_latest_npis` and `registration_link_last_observed_day` describe the Medscape registration/email context. Status is evaluated per link and registration GUID with that GUID's own days; `registration_guid` is the GUID most recently observed for the link. Status is latest_observed, superseded, ambiguous_latest or unknown. Other vendors are not_applicable. `registration_superseded_since_day` and `registration_superseded_by_npis` provide replacement evidence only for superseded links. `registration_supersession_definition_version` identifies the rules. Different GUIDs never replace each other’s claims. See [metric 26](metrics/26_registration_supersession.md).

The shorter lookup remains a subset of stored fields.

# PII Clean email lookup: all attributes and metrics

Last updated: 2026-10-29.

Use the **complete lookup** to inspect every implemented metric for one email across all vendors, NPIs and retained history. Each output row remains one exact source record and email position, keyed by `source`, `metric_row_id`. Names, states and indicators stay attached to their own records; no email–NPI deduplication occurs.

## Run the complete lookup

Open [email_lookup_full.sql](../sql/email_lookup_full.sql), copy the entire statement into Trino, and replace `person@example.com` **once** in the opening `params` CTE. No table or view is created. No matching records produces no rows.

The query returns all **103 model columns**, plus readable `name`/`state` and four name-comparison counts. It reads the published table’s base records, then computes the five unpublished evidence groups in read-only CTEs. It never selects unavailable stored columns from `iceberg.jteixeira_ipa.pii_clean`.

| Metric group | Included outputs |
|---|---|
| Published indicators/history | Email format, role/domain, name matching, multiplicity, reassignment, name conflicts, shared names/states and observation history. |
| Shared facility | `conflicting_npis_share_facility`, facility IDs and peer intersections. |
| Shared specialty | `conflicting_npis_share_specialty`, recognized taxonomy codes and peer intersections. |
| NPI lifecycle | `npi_registry_status`, uncertainty reason, dates, replacement and raw lifecycle evidence. |
| Vendor versus facility state | `vendor_state_evidence`, nullable `vendor_state_corroborated`, facility state and reference quality. |
| Cookie location | `cookie_location_status`, UID/day counts, states, ties, vendor/facility comparisons and source-date coverage. |

Filtering occurs before enrichment but retains **every source, NPI and record for the selected email**. Existing email-level counts retain their full within-email scope. Relationship summaries are recomputed from retained name/state evidence using the same intermediate rules. Current source references supply the additional fields; a cached stored score or prior unpublished table is not substituted.

Default evaluation uses Europe/Paris today. Cookie evidence uses the seven completed days before that date; current and future observations are excluded. Lifecycle and geographic references describe current readable evidence and cannot reconstruct status or attendance on historical vendor dates. Source references are not pinned and can change between runs.

The full query can scan large location/reference inputs. An email filter does not guarantee UID-level partition pruning.

## Published-table shortcut

[The shorter published-only query](../sql/email_lookup_published.sql) reads existing stored indicators without the five live enrichments. It is a subset, not the complete metric lookup. Replace its email once as well. Choose it when only stored indicators are needed.

## Attributes

| Column | Meaning |
| --- | --- |
| `email`, `source`, `npi` | Email, vendor, and reported provider NPI for this record. |
| `name` | Usable normalized vendor first/last names from `source_name_values`, formatted for reading. HealthLink uses its HCP reference. Registry names never fill missing vendor names. |
| `state` | Recognized US state/DC/territory codes from `source_state_values`. HealthLink uses its HCP reference. Multiple states remain visible. |
| `first_seen_day`, `last_seen_day` | Earliest and latest valid source delivery dates for this exact record. Not a continuous activity interval. |
| `metric_row_id` | Exact source-record/email-position identifier; use with `source` for evidence inspection. |

Empty display strings or null names/states indicate missing usable normalized values. Original malformed or incomplete attributes may still exist in `record_payload`. Displayed names are normalized rather than original casing and spelling; consult raw payload when needed.

State normalization is active through the shared [state macro](../macros/state_consistency.sql); no separate `state_normalization` setting is required. It maps recognized full US state names and codes, DC and five territories to two-letter codes after whitespace/case normalization. Unrecognized or explicitly foreign values stay unknown. QuantumMedica has no recognized state in the saved measurements; Haymarket has no state field. See the [source-state inputs](00_source_map.md#state-comparison-inputs), including HealthLink’s separate HCP reference.

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
| `name_comparison_count` | Number of peer name-comparison entries for this record, not unique NPIs or people. |
| `name_mismatch_count`, `shared_name_count`, `unknown_name_match_count` | Entries with `shares_name` false, true, or null, respectively. A null array element also counts as unknown. These counts sum to `name_comparison_count`. |

For entry outcome percentages, use `100.0 * outcome_count / nullif(name_comparison_count, 0)`. Null or empty arrays contribute zero comparisons; zero entries do not establish agreement. Keep nullable indicators unknown rather than converting them to false. Do not sum repeated email-level metrics across records. See the [metric index](metrics/README.md) for full definitions.

## Additional evidence and interpretation

All complete-query rows retain `record_payload`, original record IDs, exact `observed_days`/`conflict_days`, normalized name/state arrays and peer comparison details. The five new groups remain unpublished as warehouse columns, but are available as computed results in the complete query.

| Group | Meaning and limitations |
|---|---|
| [Shared facility](metrics/15_conflicting_npis_share_facility.md) | Exact retained facility-NPI overlap within conflict contexts. Missing facility sets remain unknown. |
| [Shared specialty](metrics/16_conflicting_npis_share_specialty.md) | Exact recognized NPPES taxonomy-code overlap; no broad-label fallback. Missing codes remain unknown. |
| [NPI lifecycle](metrics/17_npi_registry_status.md) | Current NPPES classification, separate from registry-name presence. Missing matches are not_found; conflicting, malformed, future or self-referential evidence is unknown. No link is redirected. |
| [Vendor/facility state](metrics/18_vendor_facility_state.md) | Each record’s states versus its own NPI’s usable rank-1 facility state. Multiple states including the reference are mixed, not false. |
| [Cookie geography](metrics/19_cookie_location_evidence.md) | Untied same-day primary-state observations. No usable parsed mapping is not proof that no cookie exists. Missing dates and observed disagreement remain separate. |

The complete query also includes the detailed [lifecycle output reference](../results/registry_status_summary.md#output-columns) and [location output reference](../results/location_evidence_summary.md#output-columns). Tied UID primary states supply no agreement. Daily snapshots are not independent confirmations. Do not sum per-email UID/day counts repeated across source records.

For population coverage, percentages use all distinct source/email/NPI links within each vendor. Historical state changes can put one link in multiple record-level comparison groups. Cookie location-status groups partition emails and links within a vendor. No new hard filters, weights or identity scores are introduced by this lookup.

## Validation and publication status

The complete SQL passed native Trino `EXPLAIN (TYPE VALIDATE)` and distributed planning with 46 fragments. Native synthetic execution checked three records across two NPIs, including duplicate email positions and all five enrichment groups. No real email-result rows were fetched during this validation. Exact SQL and native validation (local-only: `../results/email_lookup_full_validation.json`).

All 58 local tests passed. Lookup tests verify all stored fields except query-time `computed_at` remain identical in the synthetic lookup, that unrelated emails are excluded while conflict peers remain, that all 109 returned column names are unique, and that email literals are escaped. A separate SHA-256 assertion checks local fixture hashing against an independent digest. Local test output (local-only: `../results/email_lookup_full_local_tests.txt`).

The underlying metrics have their separately dated native and population validations. The October 29 location measurement retained 75,564,265 metric rows; usable locations accompanied 2,728,645 of 26,730,605 source/email/NPI links (10.21%). Mapping dates covered 6/7 days (85.71%), missing October 28; geo dates covered 7/7 (100%). These counts are dated measurements, not a guarantee of today’s reference contents or individual lookup results. Date presence does not establish full data completeness.

Warehouse tables and views remain unchanged. Query execution computes the unpublished groups for the requested email; it does not publish them.

## Regenerate and maintain

The complete standalone SQL is rendered from [its template](../sql/email_lookup_full.sql.j2) and the canonical metric macros. From the project directory:

```bash
../../.venv/bin/python tools/render_email_lookup.py
# Optional: fix evaluation day without reconstructing historical source versions.
../../.venv/bin/python tools/render_email_lookup.py --day 2026-10-29 --output /tmp/email_lookup_20261029.sql
```

Whenever metrics, attributes or definitions change, update the template/enrichment chain, output reference, null handling, scope, denominators and validation date together. Regenerate the standalone file and validate it before marking it current. Keep the published-only shortcut explicitly labelled as a subset. Unpublished fields may be computed in read-only CTEs; do not select nonexistent stored columns from the published table. Preserve the [project README](../README.md) link. This maintenance does not imply a background watcher.

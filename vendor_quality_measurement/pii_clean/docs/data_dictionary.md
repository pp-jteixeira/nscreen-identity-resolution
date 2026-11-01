# PII Clean data dictionary

Table: `iceberg.jteixeira_ipa.pii_clean`

Schema checked: **October 31, 2026**

Scope: **158 stored columns: 128 core fields and 30 cookie fields.**

This table preserves vendor-reported email–NPI attribution and descriptive quality evidence. One row represents one exact source record and one email position. The logical key is **`source, metric_row_id`**. Multiple rows may describe the same source/email/NPI link. Rows are neither unique people nor unique email–NPI links. No confidence score or scoring weights are assigned.

## Publication and verification

Live Trino column metadata confirms all 158 names, types and positions against the local final contract. Complete source-batch publication is verified at final snapshot `4233051104478921549`: 75,656,369 records across all seven sources, with every core field preserved and cookie integrity checks passing. The incomplete marker has been cleared. All four stored name-explanation fields are published and included in the generated 164-output email lookup.

Complete stored core snapshot `3003274000539755025` and current final snapshot `4233051104478921549` are documented in [build evidence](build_recovery.md) and [stored name evidence](name_match_evidence.md). Both contain the same complete record population. The historical final snapshot `8811920360682490090` has 154 fields and lacks the four name-explanation fields. Dictionary field definitions use schema metadata; the linked build evidence records the separate full-population validation. This dictionary does not provide per-field distributions or null counts.

## Reading the fields

- **Source scope:** email-level and link-level metrics are computed separately per vendor. Do not sum repeated email/link counts across record rows. Cookie mappings originate at email level and are repeated on record rows; do not sum them as unique cookies across links or vendors.
- **History:** raw records combine only when every original field except `day` agrees. Exact `observed_days` define known observation dates. First/last dates do not establish uninterrupted history or ownership. Repeated snapshots are not independent confirmations.
- **Eligibility:** only nonempty cleaned email/NPI keys enter metrics. Malformed nonempty values remain. Medscape excludes all NPIs in its cumulative retained opt-out feed before metrics. Missing-key observations remain in staging.
- **Unknown evidence:** nullable booleans distinguish missing or inapplicable evidence from false. Empty arrays often mean no usable evidence. Zero known dates does not prove no history. Do not replace unknown outcomes with false.
- **Conflict comparisons:** any known matching peer gives true. False requires all eligible comparisons to be known and disjoint. Missing evidence or no established conflict remains null. Endato, RocketReach and DRDB compare undated retained data within each vendor; other sources use exact overlapping conflict days.
- **References:** current registry/facility evidence generally has no historical vendor-day alignment. NPI-reference names and NPPES lifecycle/entity evidence use different relations. Date fields identify their own evaluations; cookie refreshes preserve core evaluation dates.
- **Cookie window:** defaults to three completed days before evaluation. Stored window bounds, missing-day arrays and statuses govern interpretation. Available partitions do not certify population completeness. Tied primary states do not establish state agreement.
- **Nullability:** Trino reports every physical column nullable. **Required** below means a local `not_null` test is declared; it is neither a warehouse `NOT NULL` constraint nor a null-profile result. **—** means no such final-contract test is declared. Nested members can still be null.

## Column reference

Fields follow physical column order. `array(row(...))` types are abbreviated here; the [nested evidence schemas](#nested-evidence-schemas) give their exact member names and types. Descriptions explain stored calculations; linked metric pages give detailed rules and examples.

### Identity and observation history

[Detailed definition](metrics/01_observation_counts.md).

| Field | Trino type | Meaning / interpretation | Required |
|---|---|---|---|
| `source` | `varchar` | Vendor label: healthlink, quantummedica, medscape, endato, rocketreach, drdb or haymarket. Metrics remain scoped to this source unless explicitly stated otherwise. | Yes |
| `email` | `varchar` | Lowercased, trimmed email from the vendor field or email position. Nonempty keys only. Malformed nonempty addresses remain eligible for descriptive checks. | Yes |
| `npi` | `varchar` | Trimmed vendor-reported NPI text. Nonempty keys only. Stored as text without repairing invalid identifiers. Structural validity, registry presence and lifecycle are separate indicators. | Yes |
| `first_seen_day` | `date` | Earliest valid source day for this exact raw record; unknown without dated observations. | — |
| `last_seen_day` | `date` | Latest valid source day for this exact raw record; not proof of continuous ownership. | — |
| `observed_day_count` | `bigint` | Distinct valid observation dates for this exact record; null without valid dates. | — |
| `observation_count` | `bigint` | Raw source-row observations represented by this exact record, including repeated snapshots. | Yes |
| `undated_observation_count` | `bigint` | Represented raw observations without a valid source day. | Yes |
| `invalid_day_observation_count` | `bigint` | Represented observations carrying a nonnull source day that could not be parsed. | Yes |
| `source_tables` | `array(varchar)` | Raw source table identities retained with this record. | Yes |
| `source_feeds` | `array(varchar)` | Retained vendor feed labels; may be an empty array. | Yes |
| `computed_at` | `timestamp(6) with time zone` | Query/materialization timestamp. Preserved through downstream cookie publication. Not a vendor observation date or independent confirmation. | Yes |
| `definition_version` | `varchar` | Exact-record definition identifier. | Yes |

### Email and name checks

[Detailed definition](metrics/07_vendor_name_matches_registry_name.md).

| Field | Trino type | Meaning / interpretation | Required |
|---|---|---|---|
| `email_format_valid` | `boolean` | True when cleaned email matches the configured format regex. False for a non-match. Does not establish mailbox existence, deliverability or ownership. | Yes |
| `email_role_account` | `boolean` | Exact mailbox-name list match; not proof of shared ownership. | Yes |
| `email_domain_class` | `varchar` | Ordered domain-text heuristic; institutional, free, custom or unknown. Not verified affiliation. | Yes |
| `email_matches_source_name` | `boolean` | Nullable fuzzy email-to-name comparison within the exact source record; HealthLink uses HCP-reference names. | — |
| `email_matches_registry_name` | `boolean` | Nullable fuzzy email-to-registry-name comparison; any usable registry name may match. | — |
| `vendor_name_matches_registry_name` | `boolean` | Nullable fuzzy first-and-last comparison between vendor and registry name pairs. | — |
| `name_match_evidence` | `array(row(...))` | Distinct normalized vendor/registry name comparisons used by the stored match indicators. Retains all usable vendor names, or unknown comparisons when none exist. Unusable vendor names are represented by null names. Missing reference evidence remains explicit. | Yes |
| `vendor_registry_match_classes` | `array(varchar)` | Sorted distinct match classes across retained name comparisons, including partial, disagreeing and unknown outcomes. No best-match selection. | Yes |
| `name_match_evaluated_at` | `timestamp(6) with time zone` | Evaluation time of the stored name comparisons, independent of vendor observation dates. | Yes |
| `name_match_definition_version` | `varchar` | Version of stored comparison rules and evidence selection. No scoring weights. | Yes |
| `source_name_usable` | `boolean` | True when at least one normalized source first/last-name pair is usable for comparison. HealthLink uses its HCP reference. Does not establish a name match. | Yes |
| `registry_name_usable` | `boolean` | True when at least one normalized registry first/last-name pair is usable for comparison. Independent of whether any pair matches. | Yes |
| `registry_npi_present` | `boolean` | True when this NPI joins to the registry-name input iceberg.npi.npi_reference. Separate from NPPES lifecycle and entity-type lookup presence. | Yes |

Email format, role/domain heuristics and email-to-name comparisons have separate definitions in [metrics 02–07](metrics/README.md). `vendor_registry_match_classes` retains exact, nickname, token, edit, first_only, last_only, none and unknown; it does not select a best comparison.

### Record identifiers and raw payload

[Detailed definition](metrics/01_observation_counts.md).

| Field | Trino type | Meaning / interpretation | Required |
|---|---|---|---|
| `record_id` | `varchar` | SHA256 of source table and raw payload excluding day. | Yes |
| `metric_row_id` | `varchar` | Unique record and email-position identifier. | Yes |
| `email_ordinal` | `bigint` | Original position among candidate email fields. | Yes |
| `email_origin` | `varchar` | Source column or array/token position. | — |
| `record_payload` | `varchar` | Raw identity fields, serialized as JSON; excludes only day. | — |

### Link multiplicity, conflict and names/states

[Detailed definition](metrics/08_email_npi_multiplicity.md).

| Field | Trino type | Meaning / interpretation | Required |
|---|---|---|---|
| `email_npi_count` | `bigint` | Distinct nonempty reported NPIs for this source and cleaned email across retained history; includes malformed NPIs. | Yes |
| `email_has_multiple_npis` | `boolean` | True when this source reports more than one NPI for this email. No cross-vendor pooling. | Yes |
| `has_been_reassigned` | `boolean` | Reported NPI set changes between actual observed days for this vendor and email; may coexist with conflict. Null when undated observations prevent classification. | — |
| `has_conflict_linkage` | `boolean` | Multiple reported NPIs on a day observed for this exact record. Endato, RocketReach and DRDB instead compare their complete current undated vendor data. Missing days in dated vendors can yield null. | — |
| `observed_days` | `array(date)` | Sorted distinct valid source delivery days for this exact record; empty when undated. Never an inferred date range. | Yes |
| `conflict_days` | `array(date)` | Actual days of this record with multiple reported NPIs for its vendor and email; empty for undated vendors even when conflict is true. | Yes |
| `source_name_values` | `array(row(...))` | Distinct usable normalized vendor first/last names and first-name variants for this metric row. HealthLink uses its HCP reference; registry names never fill missing vendor names. | Yes |
| `source_state_values` | `array(varchar)` | Sorted distinct recognized US state/DC/territory codes for this record; HealthLink uses its HCP reference by NPI without date alignment. Missing, unrecognized and explicitly foreign values give an empty array. | Yes |
| `email_name_count` | `bigint` | Distinct normalized usable first/last-name pairs within this vendor and email across retained history. Zero means no usable names; fuzzy aliases remain separate spellings. | Yes |
| `email_npi_has_name_conflict` | `boolean` | True when any two usable names for this vendor/email/NPI disagree under metric 07 fuzzy rules; false with one name or all names compatible; null with no usable names. | — |
| `conflicting_npis_share_name` | `boolean` | Record-local fuzzy name agreement with another NPI on overlapping conflict days, or in the undated vendor snapshot. True if any peer matches; false only if all comparisons are known mismatches; null for missing names or no established conflict. | — |
| `conflicting_npi_name_comparisons` | `array(row(...))` | Ordered peer comparison contexts with NPI, overlapping conflict days, usable vendor names and nullable shares_name. Empty without an established conflict; undated snapshot comparisons have empty days. | Yes |
| `conflicting_npis_share_state` | `boolean` | Record-local state overlap with other NPIs on overlapping conflict days or within the undated vendor snapshot. Any true wins; false requires all known mismatches; otherwise null, including no established conflict. | — |
| `conflicting_npi_state_comparisons` | `array(row(...))` | Ordered peer contexts with NPI, overlapping dates, normalized states and nullable shares_state, preserving manual-check details. | Yes |

[Reassignment](metrics/09_has_been_reassigned.md), [same-day conflict](metrics/10_has_conflict_linkage.md), [name history](metrics/11_email_name_count.md), [name conflict](metrics/12_email_npi_has_name_conflict.md), [peer names](metrics/13_conflicting_npis_share_name.md) and [peer states](metrics/14_conflicting_npis_share_state.md) use distinct scopes. Reassignment and conflict can coexist.

### Shared facilities between conflicting NPIs

[Detailed definition](metrics/15_conflicting_npis_share_facility.md).

| Field | Trino type | Meaning / interpretation | Required |
|---|---|---|---|
| `facility_npi_values` | `array(varchar)` | Sorted distinct ten-digit nonzero facility NPIs across all retained association ranks for this provider NPI. Missing or unusable reference IDs give an empty array; no historical date alignment. | Yes |
| `facility_reference_table` | `varchar` | Reference relation used for the association lookup. | Yes |
| `facility_definition_version` | `varchar` | all_ranked_facility_npis_v1: exact facility-NPI overlap, not provider-scoped cluster IDs. | Yes |
| `conflicting_npis_share_facility` | `boolean` | Any overlapping conflict peer shares a retained facility NPI. False only when all peer comparisons have usable disjoint facility sets; otherwise null, including missing evidence or no established conflict. Associations have no activity dates and do not establish coattendance. | — |
| `conflicting_npi_facility_comparisons` | `array(row(...))` | Ordered peer NPI/date contexts with retained facility NPIs, their exact intersection and nullable shares_facility. | Yes |

### Shared NPPES taxonomy between conflicting NPIs

[Detailed definition](metrics/16_conflicting_npis_share_specialty.md).

| Field | Trino type | Meaning / interpretation | Required |
|---|---|---|---|
| `specialty_code_values` | `array(varchar)` | Sorted distinct recognized NPPES taxonomy codes across all fifteen slots, joined by NPI without historical date alignment. Missing or unrecognized-only sets give an empty array. | Yes |
| `specialty_reference_table` | `varchar` | NPPES provider relation used for specialty-code evidence. Codes must also occur in iceberg.npi.npi_taxonomy. | Yes |
| `specialty_definition_version` | `varchar` | recognized_exact_taxonomy_all_slots_v1: exact code overlap across all fifteen primary/secondary slots; no broad-class or label fallback. | Yes |
| `conflicting_npis_share_nppes_specialty` | `boolean` | Any conflict peer shares an exact recognized taxonomy code. False requires known disjoint retained sets for all peers; otherwise null, including no established conflict. Current reference does not establish historical or same-day specialty. | — |
| `conflicting_npi_specialty_comparisons` | `array(row(...))` | Ordered peer contexts with NPI, exact overlapping conflict dates, recognized taxonomy codes, shared codes and nullable shares_specialty. | Yes |

### NPPES lifecycle

[Detailed definition](metrics/17_npi_registry_status.md).

| Field | Trino type | Meaning / interpretation | Required |
|---|---|---|---|
| `npi_registry_status` | `varchar` | Current readable NPPES lifecycle classification: active_as_reported, deactivated, reactivated, replaced, not_found or unknown. Not historical status on vendor delivery dates. | Yes |
| `npi_registry_status_reason` | `varchar` | Explicit classification or uncertainty reason, including malformed/future dates, contradictory records, self-replacement and ambiguous event ordering. | Yes |
| `npi_registry_replacement_npi` | `varchar` | Single agreed ten-digit nonzero nonself replacement NPI, if reported. Its registry presence and checksum are not validated; links are never automatically redirected. | — |
| `npi_registry_deactivation_date` | `date` | Parsed agreed deactivation date. Null if absent, invalid or reference variants conflict. | — |
| `npi_registry_reactivation_date` | `date` | Parsed agreed reactivation date. Null if absent, invalid or reference variants conflict. | — |
| `npi_registry_reference_row_count` | `bigint` | Number of readable NPPES records for this NPI, including duplicates; zero when unmatched. | Yes |
| `npi_registry_variant_count` | `bigint` | Distinct trimmed lifecycle tuples. More than one yields unknown rather than choosing an arbitrary record. | Yes |
| `npi_registry_lifecycle_evidence` | `array(row(...))` | Distinct original deactivation/reactivation strings, replacement NPI strings and reason codes. Empty without a reference match. | Yes |
| `npi_registry_status_as_of_day` | `date` | Date used to reject future events; Europe/Paris current date unless explicitly fixed. Does not reconstruct historical registry versions. | Yes |
| `npi_registry_reference_table` | `varchar` | iceberg.npi.nppes_npidata_latest; separate from the registry-name lookup. | Yes |
| `npi_registry_definition_version` | `varchar` | nppes_lifecycle_consensus_v1: normalized tuple agreement, date chronology and retained replacement evidence. | Yes |

### Vendor state versus own-NPI facility state

[Detailed definition](metrics/18_vendor_facility_state.md).

| Field | Trino type | Meaning / interpretation | Required |
|---|---|---|---|
| `facility_primary_state` | `varchar` | Single recognized rank-1 facility state when every retained rank-1 row has a recognized state and nonblank location; null for ambiguity or missing evidence. | — |
| `facility_reference_status` | `varchar` | usable, ambiguous_state, missing_state, missing_location or no_rank1_association; independent of vendor-state availability. | Yes |
| `facility_rank1_rows` | `bigint` | Raw rank-1 reference rows before per-NPI collapse; zero without a match. | Yes |
| `facility_rank1_state_count` | `bigint` | Distinct recognized rank-1 facility states before collapse. | Yes |
| `facility_rank1_unknown_state_rows` | `bigint` | Rank-1 reference rows with missing or unrecognized state. | Yes |
| `facility_rank1_missing_location_rows` | `bigint` | Rank-1 reference rows with blank or missing coordinates. | Yes |
| `vendor_state_evidence` | `varchar` | Record-state versus own-NPI facility reference: corroborated, not_corroborated, mixed_vendor_states, unknown_vendor_state or unknown_facility. | Yes |
| `vendor_state_corroborated` | `boolean` | True only for a single matching vendor state, false for known disjoint states, null for mixed or unknown evidence. | — |
| `location_evaluation_day` | `date` | Europe/Paris evaluation day, or explicit location_evidence_day. No historical vendor-day reconstruction. | Yes |
| `location_reference_table` | `varchar` | bq_bi.analytics_prod.npi_facility_locations_with_ids; only rank-1 rows are used. | Yes |
| `location_evidence_version` | `varchar` | record_vendor_facility_state_v1; record-grain descriptive comparison without scoring. | Yes |

### Cookie mappings and location evidence

[Detailed definition](metrics/19_cookie_location_evidence.md).

| Field | Trino type | Meaning / interpretation | Required |
|---|---|---|---|
| `cookie_count` | `bigint` | Distinct usable mapped UID strings within the stored completed-day window; not verified browser-cookie counts. | — |
| `cookie_mapping_days` | `bigint` | Distinct dates with a valid email-hash/UID mapping. | — |
| `cookie_mapped_uid_days` | `bigint` | Distinct UID/mapping-day tuples after token and row deduplication. | — |
| `cookie_observed_uid_days` | `bigint` | Mapped UID-days with any same-day geo observation, including unmapped ZIP3 states. | — |
| `cookie_located_uid_days` | `bigint` | Mapped UID-days whose ranked primary recognized state appears on that day; includes tied winners. | — |
| `cookie_eligible_uid_days` | `bigint` | Located mapped UID-days with an untied primary state; only these establish state comparisons. | — |
| `cookie_located_count` | `bigint` | Distinct UIDs with a located primary-state mapping day, including ties. | — |
| `cookie_primary_state_tied_count` | `bigint` | Distinct mapped UIDs with multiple recognized states tied for most observed dates. | — |
| `cookie_primary_state_multistate_count` | `bigint` | Distinct mapped UIDs with more than one recognized state in the window. | — |
| `cookie_eligible_observed_days` | `bigint` | Distinct mapping dates carrying untied primary-state observations. | — |
| `cookie_location_first_day` | `date` | First untied primary-state mapping date; null without usable observations. | — |
| `cookie_location_last_day` | `date` | Last untied primary-state mapping date; null without usable observations. | — |
| `cookie_uid_types` | `array(varchar)` | Sorted distinct mapping namespace labels; raw UID strings retain their prefixes for joins. | — |
| `cookie_state_values` | `array(varchar)` | Sorted distinct untied primary states observed on matching mapping dates. Tied states supply no agreement. | — |
| `cookie_location_window_days` | `bigint` | Completed calendar days before evaluation, three by default. | — |
| `cookie_mapping_available_days` | `bigint` | Dates present in mapping partition metadata; presence does not prove complete rows. | — |
| `cookie_location_available_days` | `bigint` | Dates present in geo partition metadata; presence does not prove complete rows. | — |
| `cookie_mapping_missing_days` | `array(date)` | Expected dates absent from mapping metadata; missing dates are not mismatches. | — |
| `cookie_location_missing_days` | `array(date)` | Expected dates absent from geo metadata. | — |
| `cookie_location_window_status` | `varchar` | all_source_days_present or missing_source_days; not a population-completeness guarantee. | — |
| `cookie_state_count` | `bigint` | Number of retained usable cookie_state_values. | — |
| `cookie_location_status` | `varchar` | no_mapping, observed, ambiguous_primary_state, unknown_state or no_state_observation. no_mapping means no valid parsed mapping, not proof that no cookie exists. | Yes |
| `cookie_vendor_state_evidence` | `varchar` | Untied observed primary states versus this exact record’s source_state_values; nullable evidence is represented by explicit unknown labels. | — |
| `cookie_facility_state_evidence` | `varchar` | Untied observed primary states versus this NPI’s usable rank-1 facility state. | — |
| `cookie_location_window_start` | `date` | Inclusive start of the stored cookie window: evaluation day minus cookie_location_window_days. Default window length is three completed days. Read the stored value for historical publications. | — |
| `cookie_location_window_end` | `date` | Evaluation day minus one, inclusive. | — |
| `cookie_mapping_table` | `varchar` | iceberg.thirdparty.liveintent_idsync. | — |
| `cookie_location_geo_table` | `varchar` | iceberg.crossscreen.nscreen_geo_daily_ua; snapshots may share a 15-day hourly lookback. | — |
| `cookie_zip_mapping_table` | `varchar` | iceberg.jteixeira_ipa.tmp_zip3_to_state; provider-derived mapping, not authoritative postal boundaries. | — |
| `cookie_location_evidence_version` | `varchar` | liveintent_primary_state_untied_v1; no scores or fractional votes. | — |

### Link freshness

[Detailed definition](metrics/20_link_freshness.md).

| Field | Trino type | Meaning / interpretation | Required |
|---|---|---|---|
| `link_freshness_as_of_day` | `date` | Evaluation day for stored link freshness, Europe/Paris today unless overridden. | Yes |
| `source_latest_observed_day` | `date` | Latest valid parsed observation day among retained eligible records for this vendor, including future dates. | — |
| `link_last_observed_day` | `date` | Latest observation day across this source/email/NPI link, propagated to every retained record. Null when undated. | — |
| `source_age_days` | `bigint` | Days from source_latest_observed_day to evaluation day. Null for undated or future-dated source evidence. | — |
| `link_lag_days` | `bigint` | Days from link_last_observed_day to source_latest_observed_day. Null for undated links or future-dated source evidence. No stale threshold. | — |

### Link presence and overlap

[Detailed definition](metrics/21_link_stability.md).

| Field | Trino type | Meaning / interpretation | Required |
|---|---|---|---|
| `email_observed_day_count` | `bigint` | Distinct known observation days across all NPIs for this source/email. Zero means no dated email history. | Yes |
| `link_observed_day_count` | `bigint` | Distinct known observation days for this source/email/NPI, across all records and email positions. | Yes |
| `link_conflict_day_count` | `bigint` | Distinct days this source/email/NPI overlapped another NPI. Zero counts known overlap days only. | Yes |
| `link_presence_share` | `double` | Link observed days divided by email observed days, as a fraction from zero to one. Null when this link has no dated observations. | — |
| `link_overlap_share` | `double` | Link conflict days divided by link observed days, as a fraction from zero to one. Null for undated links. | — |
| `link_stability_has_undated_observations` | `boolean` | True when any record for this source/email, including peer NPIs, contains undated or invalid-day observations. Shares cover known dates only. | Yes |

### NPI structure and entity type

[Detailed definition](metrics/22_npi_identity.md).

| Field | Trino type | Meaning / interpretation | Required |
|---|---|---|---|
| `npi_format_valid` | `boolean` | Ten ASCII digits beginning with 1 through 4. Null for missing input. | — |
| `npi_checksum_valid` | `boolean` | Luhn checksum including the 80840 prefix. Null unless input has exactly ten ASCII digits. | — |
| `npi_structure_valid` | `boolean` | Format and checksum both pass. Does not establish registry existence or activity. | — |
| `npi_structure_reason` | `varchar` | missing, malformed, unsupported_prefix, checksum_failure or valid, in that priority order. | Yes |
| `npi_entity_type` | `varchar` | Registry consensus: individual, organization or unknown. Independent of structure and lifecycle status. | Yes |
| `npi_entity_type_reason` | `varchar` | registry_consensus, not_found, conflicting_reference_records, missing_entity_type or unrecognized_entity_type. | Yes |
| `npi_entity_type_evidence` | `array(row(...))` | Distinct raw NPPES entity type codes, including null evidence. Empty array when no reference record exists. | Yes |
| `npi_entity_type_reference_row_count` | `bigint` | Number of NPPES reference rows for the identifier. Duplicate rows never multiply metric records. | Yes |
| `npi_entity_type_variant_count` | `bigint` | Number of distinct trimmed entity-code variants, counting missing as a variant. | Yes |
| `npi_identity_as_of_day` | `date` | Europe/Paris evaluation date for current registry evidence. Not the reference file delivery date or historical vendor-day evidence. | Yes |
| `npi_identity_reference_table` | `varchar` | Registry relation used for entity type evidence. | Yes |
| `npi_identity_definition_version` | `varchar` | Version of structural validation and entity-consensus rules. | Yes |

### Vendor specialty and profession

[Detailed definition](metrics/23_conflicting_npis_share_vendor_specialty.md).

| Field | Trino type | Meaning / interpretation | Required |
|---|---|---|---|
| `source_vendor_specialty_values` | `array(varchar)` | Distinct normalized vendor specialty labels across the exact record observation days. Comparisons use day-specific evidence, not this union. | Yes |
| `source_vendor_profession_values` | `array(varchar)` | Distinct normalized vendor profession labels across the exact record observation days. Credentials and registry classifications are excluded. | Yes |
| `vendor_professional_evidence` | `array(row(...))` | Per-observation-day vendor table provenance, raw specialty/profession labels and normalized values. Metadata joins match the delivery day and NPI, plus Medscape guid. Empty arrays preserve missing evidence. | Yes |
| `vendor_professional_definition_version` | `varchar` | Version of vendor-label normalization, same-day joins and conflict comparison rules. | Yes |
| `conflicting_npis_share_vendor_specialty` | `boolean` | Whether any conflicting peer NPI has an exact normalized vendor specialty overlap on the same conflict day, or in the undated DRDB snapshot. False requires all comparisons known and disjoint. Otherwise unknown or inapplicable. | — |
| `conflicting_npi_vendor_specialty_comparisons` | `array(row(...))` | Peer NPI, metric row ID, evidence day, own and peer specialty labels, shared labels and nullable shares_specialty. | Yes |
| `conflicting_npis_share_vendor_profession` | `boolean` | Whether any conflicting peer NPI has an exact normalized vendor profession overlap on the same conflict day. False requires all comparisons known and disjoint. Missing profession evidence stays unknown. | — |
| `conflicting_npi_vendor_profession_comparisons` | `array(row(...))` | Peer NPI, metric row ID, evidence day, own and peer profession labels, shared labels and nullable shares_profession. | Yes |

[Profession overlap](metrics/24_conflicting_npis_share_vendor_profession.md) is separate from specialty overlap and NPPES taxonomy. Unsupported vendor attributes remain unknown.

### Sequential email history

[Detailed definition](metrics/25_sequential_history.md).

| Field | Trino type | Meaning / interpretation | Required |
|---|---|---|---|
| `sequence_as_of_day` | `date` | Inclusive evaluation cutoff for sequential history and registration supersession. Defaults to Europe/Paris today. Daily evidence uses only observations through its own day. | — |
| `sequence_definition_version` | `varchar` | Sequence, delivery-version and cumulative-count rule version. | — |
| `sequence_history_status` | `varchar` | dated_history, incomplete_dates or no_dated_history. Known-date counts do not infer missing observations. | — |
| `sequence_has_undated_observations` | `boolean` | Any eligible record for this source/email has missing or invalid observation dates. | — |
| `sequence_min_versions` | `bigint` | Minimum observed delivery versions required by stability_history_sufficient. Default three. | — |
| `n_versions_observed` | `bigint` | Eligible delivery versions containing this source/email through evaluation. Consecutive equal HealthLink/QuantumMedica email/NPI content fingerprints collapse. Medscape and Haymarket use observed days. | — |
| `n_npis_window` | `bigint` | Distinct NPIs observed for this source/email across all retained dated history through sequence_as_of_day. No rolling window is applied. | — |
| `n_npi_changes` | `bigint` | Consecutive observed email-day transitions with any NPI addition or removal. Initial observation is not a change. | — |
| `n_swaps` | `bigint` | Observed transitions with both added and removed NPIs. Count transitions rather than individual NPIs. | — |
| `n_flipbacks` | `bigint` | Swap transitions that add at least one NPI observed previously for this source/email. | — |
| `stability_history_sufficient` | `boolean` | Whether n_versions_observed reaches sequence_min_versions. False without dated history. Does not establish ownership or independent confirmation. | — |
| `sequence_daily_evidence` | `array(row(...))` | Ordered observed-day NPI sets, previous observed day, added/removed/returned NPIs and cumulative versions, NPIs, changes, swaps, flipbacks and sufficiency. Each entry uses only its day and earlier observations. Repeated source copies do not increment content versions. | — |

### Medscape registration supersession

[Detailed definition](metrics/26_registration_supersession.md).

| Field | Trino type | Meaning / interpretation | Required |
|---|---|---|---|
| `registration_guid` | `varchar` | Cleaned Medscape registration GUID from the exact raw record. NULL for other sources. | — |
| `registration_link_status` | `varchar` | Medscape source/GUID/email/NPI status through sequence_as_of_day: latest_observed, superseded, ambiguous_latest or unknown. Other sources are not_applicable. Missing GUID, dates or incomplete registration chronology remain unknown. | — |
| `registration_latest_observed_day` | `date` | Latest eligible dated observation for this source/GUID/email through sequence_as_of_day. | — |
| `registration_latest_npis` | `array(varchar)` | Distinct NPIs on registration_latest_observed_day. Multiple NPIs are ambiguous and never arbitrarily resolved. | — |
| `registration_link_last_observed_day` | `date` | Last eligible dated observation of this source/GUID/email/NPI through sequence_as_of_day. | — |
| `registration_superseded_since_day` | `date` | First observed registration day after the old NPI last appeared, only when its current status is superseded. This classification is evaluated at sequence_as_of_day and is not a historical ownership claim. | — |
| `registration_superseded_by_npis` | `array(varchar)` | Unique latest observed registration NPI for a superseded link. Empty for unknown, ambiguous, latest or inapplicable links. | — |
| `registration_supersession_definition_version` | `varchar` | Registration supersession rule version. No links are removed or redirected. | — |

## Nested evidence schemas

Each structure below is one element of the named array. Names are literal SQL member names. Peer `npi` values identify comparison targets; nested peer arrays do not create additional final-table records. `conflict_days` contains actual overlapping dates, not a date range. Raw lifecycle strings remain text even where separately parsed date fields exist.

### `name_match_evidence`

| Member | Trino type |
|---|---|
| `source_first_name` | `varchar` |
| `source_last_name` | `varchar` |
| `registry_first_name` | `varchar` |
| `registry_last_name` | `varchar` |
| `first_name_match_kind` | `varchar` |
| `last_name_match_kind` | `varchar` |
| `match_class` | `varchar` |
| `email_matches_source_name` | `boolean` |
| `email_matches_registry_name` | `boolean` |
| `vendor_name_matches_registry_name` | `boolean` |

### `source_name_values`

| Member | Trino type |
|---|---|
| `first_name` | `varchar` |
| `last_name` | `varchar` |
| `first_variants` | `array(varchar)` |

### `conflicting_npi_name_comparisons`

| Member | Trino type |
|---|---|
| `npi` | `varchar` |
| `conflict_days` | `array(date)` |
| `names` | `array(row(first_name varchar, last_name varchar, first_variants array(varchar)))` |
| `shares_name` | `boolean` |

### `conflicting_npi_state_comparisons`

| Member | Trino type |
|---|---|
| `npi` | `varchar` |
| `conflict_days` | `array(date)` |
| `states` | `array(varchar)` |
| `shares_state` | `boolean` |

### `conflicting_npi_facility_comparisons`

| Member | Trino type |
|---|---|
| `npi` | `varchar` |
| `conflict_days` | `array(date)` |
| `facility_npis` | `array(varchar)` |
| `shared_facility_npis` | `array(varchar)` |
| `shares_facility` | `boolean` |

### `conflicting_npi_specialty_comparisons`

| Member | Trino type |
|---|---|
| `npi` | `varchar` |
| `conflict_days` | `array(date)` |
| `specialty_codes` | `array(varchar)` |
| `shared_specialty_codes` | `array(varchar)` |
| `shares_specialty` | `boolean` |

### `npi_registry_lifecycle_evidence`

| Member | Trino type |
|---|---|
| `deactivation_date` | `varchar` |
| `reactivation_date` | `varchar` |
| `replacement_npi` | `varchar` |
| `deactivation_reason` | `varchar` |

### `npi_entity_type_evidence`

| Member | Trino type |
|---|---|
| `entity_type_code` | `varchar` |

### `vendor_professional_evidence`

| Member | Trino type |
|---|---|
| `evidence_day` | `date` |
| `source_table` | `varchar` |
| `raw_specialties` | `array(varchar)` |
| `raw_professions` | `array(varchar)` |
| `specialties` | `array(varchar)` |
| `professions` | `array(varchar)` |

### `conflicting_npi_vendor_specialty_comparisons`

| Member | Trino type |
|---|---|
| `npi` | `varchar` |
| `metric_row_id` | `varchar` |
| `evidence_day` | `date` |
| `own_values` | `array(varchar)` |
| `peer_values` | `array(varchar)` |
| `shared_values` | `array(varchar)` |
| `shares_specialty` | `boolean` |

### `conflicting_npi_vendor_profession_comparisons`

| Member | Trino type |
|---|---|
| `npi` | `varchar` |
| `metric_row_id` | `varchar` |
| `evidence_day` | `date` |
| `own_values` | `array(varchar)` |
| `peer_values` | `array(varchar)` |
| `shared_values` | `array(varchar)` |
| `shares_profession` | `boolean` |

### `sequence_daily_evidence`

| Member | Trino type |
|---|---|
| `observed_day` | `date` |
| `previous_observed_day` | `date` |
| `npis` | `array(varchar)` |
| `added_npis` | `array(varchar)` |
| `removed_npis` | `array(varchar)` |
| `returned_npis` | `array(varchar)` |
| `versions_observed` | `bigint` |
| `npis_observed` | `bigint` |
| `changes` | `bigint` |
| `swaps` | `bigint` |
| `flipbacks` | `bigint` |
| `history_sufficient` | `boolean` |

## Joins, counts and dates

Use `source, metric_row_id` when joining record-level evidence. Use `source, email, npi` when explicitly aggregating links. Use `source, email` for vendor email-history metrics. Preserve the distinction between `record_id` (raw record) and `metric_row_id` (raw record plus email position). Reference joins are collapsed before attaching evidence to avoid multiplying records.

`observed_day_count` counts dates for one exact record; `email_observed_day_count` unions dates across its vendor/email; `link_observed_day_count` unions dates across its vendor/email/NPI. `link_presence_share = link_observed_day_count / email_observed_day_count`. `link_overlap_share = link_conflict_day_count / link_observed_day_count`. Shares are fractions from zero to one, with null for unavailable dated link history. `link_stability_has_undated_observations` qualifies known-date shares.

`source_age_days` compares the vendor's latest eligible observation with `link_freshness_as_of_day`. `link_lag_days` compares the link's latest observation with that vendor baseline. No freshness threshold is assigned. `n_npis_window` uses all retained eligible dated history through `sequence_as_of_day`; despite its name, it is not a rolling calendar window.

`registration_*` supersession uses Medscape source/GUID/email/NPI chronology. Other sources have `not_applicable` status. Old links remain stored. A unique latest NPI can supersede an older claim; multiple latest NPIs remain ambiguous. Missing GUID or chronology remains unknown.

## Definition sources and reproduction

Physical schema: live Trino `iceberg.information_schema.columns`, checked October 31, 2026. Semantics and local required tests: [final contract](../models/final/schema.yml), [vendor models](../models/intermediate/README.md), [source map](00_source_map.md), [metric definitions](metrics/README.md) and [cookie macro](../macros/cookie_location.sql). `cookie_location_window_start` uses the configured window length. All four name-explanation columns are published and verified in the complete final population.

Executed metadata query:

```sql
SELECT ordinal_position, column_name, data_type, is_nullable
FROM iceberg.information_schema.columns
WHERE table_schema = 'jteixeira_ipa' AND table_name = 'pii_clean'
ORDER BY ordinal_position
```

Executed publication-state check:

```sql
SHOW CREATE TABLE iceberg.jteixeira_ipa.pii_clean
```

These checks inspect schema and the table comment. They do not scan PII records. No query-result extracts are retained. The dictionary covers stored columns only; six display/count helpers in the [email lookup](email_lookup.md) are computed query outputs and are excluded.

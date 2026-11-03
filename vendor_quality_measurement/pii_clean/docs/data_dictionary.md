# PII Clean data dictionary

Table: `iceberg.jteixeira_ipa.pii_clean`

Scope: **194 contract columns: 139 core fields, 10 domain fields, 14 cross-source fields and 31 cookie fields.** The November 2 snapshot stores 165; the 29 fields of the claims-support, domain and cross-source sections are stored from the next build.

This table preserves vendor-reported email–NPI attribution and descriptive quality evidence. One row represents one **link**: a source, a cleaned email and a reported NPI. The key is **`link_id`**, the SHA256 of source, email and NPI; it is unique in the table. A link merges every *version* of the source records that report it. A version is one distinct identity of a source record: raw rows identical except for `day` and the schema's volatile fields. Rows are neither unique people nor cross-vendor links. No confidence score or scoring weights are assigned.

## Versions, volatile fields and the latest version

Each vendor model first groups raw staging rows into versions. Grouping ignores `day` and every field listed as `volatile` in [record_schemas.json](../models/record_schemas.json). Medscape's volatile fields are `email_address` (raw spelling), `huid`, `ip` (split on commas), `payer_status`, `practice_setting`, `source` and `validated`; other sources declare none. Volatile fields never split a version. Their sorted distinct values are kept as arrays inside the version's JSON payload. A `record_id` is the SHA256 of the source table and the identity payload; Medscape also includes the cleaned email.

Versions are then unfolded by email position and collapsed to one row per link. History columns cover all versions of the link. `attribute_versions` keeps one entry per version, so name, address and other attribute changes remain visible.

The **latest version** is the version with the unique greatest `last_seen_day`, or the only version of the link. `latest_record_id` is NULL when the link has several undated versions or when the greatest `last_seen_day` is tied.

Indicators that depend on one record's own attributes are published twice:

- The unsuffixed column is evaluated over **all versions** of the link. Name indicators are true when any usable vendor name of the link matches, false when every usable name fails, and NULL when none is usable. `source_state_values` is the union of recognized states across versions, so several states give `mixed_vendor_states`.
- The `_latest` column uses only the latest version: `email_matches_source_name_latest`, `vendor_name_matches_registry_name_latest`, `source_state_values_latest`, `vendor_state_evidence_latest`, `vendor_state_corroborated_latest` and `cookie_vendor_state_evidence_latest`. They are NULL when `latest_record_id` is NULL. HealthLink takes names and states from its HCP reference by NPI, so its `_latest` columns equal the all-version columns.

`email_matches_registry_name` does not use vendor names and has no `_latest` form. Cross-NPI peer comparisons compare the link's union of names, states and labels with each peer and also have no `_latest` form.

## Publication status

This dictionary describes the local final contract, [models/final/schema.yml](../models/final/schema.yml); it does not provide per-field distributions or null counts.

## Reading the fields

- **Source scope:** email-level and link-level metrics are computed separately per vendor. Email-level values repeat on every link of that source and email; do not sum them across links. Cookie mappings originate at email level and are repeated on each link; do not sum them as unique cookies across links or vendors.
- **History:** raw rows form one version when every identity field except `day` and volatile fields agrees. A link unions the history of all its versions. Exact `observed_days` define known observation dates. First/last dates do not establish uninterrupted history or ownership. Repeated snapshots are not independent confirmations.
- **Eligibility:** only nonempty cleaned email/NPI keys enter metrics. Malformed nonempty values remain. Medscape excludes all NPIs in its cumulative retained opt-out feed before metrics. Missing-key observations remain in staging.
- **Unknown evidence:** nullable booleans distinguish missing or inapplicable evidence from false. Empty arrays often mean no usable evidence. Zero known dates does not prove no history. Do not replace unknown outcomes with false.
- **Conflict comparisons:** any known matching peer gives true. False requires all eligible comparisons to be known and disjoint. Missing evidence or no established conflict remains null. Endato, RocketReach and DRDB compare every other NPI of the email within each vendor; other sources use exact overlapping conflict days. Peer comparisons use the link's union of names, states or labels.
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
| `link_id` | `varchar` | SHA256 of source, email and NPI. One row per link; unique within the table. | Yes (unique) |
| `first_seen_day` | `date` | Earliest valid source day across all versions of this link; unknown without dated observations. | — |
| `last_seen_day` | `date` | Latest valid source day across all versions of this link; not proof of continuous ownership. | — |
| `observed_day_count` | `bigint` | Distinct valid observation dates of this link; null without valid dates. | — |
| `observation_count` | `bigint` | Raw source-row observations represented by this link, summed over its versions, including repeated snapshots. | Yes |
| `undated_observation_count` | `bigint` | Represented raw observations without a valid source day, summed over versions. | Yes |
| `invalid_day_observation_count` | `bigint` | Represented observations carrying a nonnull source day that could not be parsed, summed over versions. | Yes |
| `source_tables` | `array(varchar)` | Raw source tables contributing versions to this link. A DRDB link can list both input tables. | Yes |
| `source_feeds` | `array(varchar)` | Vendor feed labels across versions; may be an empty array. | Yes |
| `computed_at` | `timestamp(6) with time zone` | Query/materialization timestamp. Preserved through downstream cookie publication. Not a vendor observation date or independent confirmation. | Yes |
| `definition_version` | `varchar` | Link grain definition identifier: `links_v1`. | Yes |

### Email and name checks

[Detailed definition](metrics/07_vendor_name_matches_registry_name.md).

| Field | Trino type | Meaning / interpretation | Required |
|---|---|---|---|
| `email_format_valid` | `boolean` | True when cleaned email matches the configured format regex. False for a non-match. Does not establish mailbox existence, deliverability or ownership. | Yes |
| `email_role_account` | `boolean` | Exact mailbox-name list match; not proof of shared ownership. | Yes |
| `email_domain_class` | `varchar` | Ordered domain-text heuristic; institutional, free, custom or unknown. Not verified affiliation. | Yes |
| `email_matches_source_name` | `boolean` | Nullable fuzzy email-to-name comparison over every usable vendor name of the link: true when any version matches. HealthLink uses HCP-reference names. | — |
| `email_matches_source_name_latest` | `boolean` | `email_matches_source_name` evaluated on the latest version only. Null when the link has no single latest version. | — |
| `email_matches_registry_name` | `boolean` | Nullable fuzzy email-to-registry-name comparison; any usable registry name may match. No `_latest` form. | — |
| `vendor_name_matches_registry_name` | `boolean` | Nullable fuzzy first-and-last comparison between vendor and registry name pairs: true when any version matches. | — |
| `vendor_name_matches_registry_name_latest` | `boolean` | `vendor_name_matches_registry_name` evaluated on the latest version only. Null when the link has no single latest version. | — |
| `name_match_evidence` | `array(row(...))` | Distinct normalized vendor/registry name comparisons used by the all-version match indicators. Retains all usable vendor names of the link, or unknown comparisons when none exist. Unusable vendor names are represented by null names. Missing reference evidence remains explicit. | Yes |
| `vendor_registry_match_classes` | `array(varchar)` | Sorted distinct match classes across retained name comparisons, including partial, disagreeing and unknown outcomes. No best-match selection. | Yes |
| `name_match_evaluated_at` | `timestamp(6) with time zone` | Evaluation time of the stored name comparisons, independent of vendor observation dates. | Yes |
| `name_match_definition_version` | `varchar` | Version of stored comparison rules and evidence selection. No scoring weights. | Yes |
| `source_name_usable` | `boolean` | True when at least one normalized source first/last-name pair of the link is usable for comparison. HealthLink uses its HCP reference. Does not establish a name match. | Yes |
| `registry_name_usable` | `boolean` | True when at least one normalized registry first/last-name pair is usable for comparison. Independent of whether any pair matches. | Yes |
| `registry_npi_present` | `boolean` | True when this NPI joins to the registry-name input iceberg.npi.npi_reference. Separate from NPPES lifecycle and entity-type lookup presence. | Yes |

Email format, role/domain heuristics and email-to-name comparisons have separate definitions in [metrics 02–07](metrics/README.md). `vendor_registry_match_classes` retains exact, nickname, token, edit, first_only, last_only, none and unknown; it does not select a best comparison.

### Versions and email origins

[Detailed definition](metrics/01_observation_counts.md).

| Field | Trino type | Meaning / interpretation | Required |
|---|---|---|---|
| `record_count` | `bigint` | Distinct versions merged into this link. | Yes |
| `record_ids` | `array(varchar)` | Sorted `record_id` values of the merged versions. A `record_id` is the SHA256 of the source table and the identity fields of one version; Medscape also includes the cleaned email. | Yes |
| `latest_record_id` | `varchar` | Version with the unique greatest `last_seen_day`, or the only version. Null when the link has several undated versions or the greatest day is tied. | — |
| `email_origins` | `array(varchar)` | Sorted source columns or array positions where this email appeared across versions, for example `email_2_address`, `emails[1]` or `email_token_3`. | Yes |
| `attribute_versions` | `array(row(...))` | One entry per version, ordered by `first_seen_day`, `last_seen_day`, `record_id`: record ID, first and last seen day, observed day count, observation count, email origins and the JSON identity payload. Volatile fields appear as arrays inside the payload. Name and address changes over time are visible here. | Yes |

### Link multiplicity, conflict and names/states

[Detailed definition](metrics/08_email_npi_multiplicity.md).

| Field | Trino type | Meaning / interpretation | Required |
|---|---|---|---|
| `email_npi_count` | `bigint` | Distinct nonempty reported NPIs for this source and cleaned email across retained history; includes malformed NPIs. | Yes |
| `email_has_multiple_npis` | `boolean` | True when this source reports more than one NPI for this email. No cross-vendor pooling. | Yes |
| `has_been_reassigned` | `boolean` | Reported NPI set changes between actual observed days for this vendor and email; may coexist with conflict. Null when undated observations prevent classification. | — |
| `has_conflict_linkage` | `boolean` | Multiple reported NPIs on a day observed for this link. Endato, RocketReach and DRDB instead compare their complete current undated vendor data. Missing days in dated vendors can yield null. | — |
| `observed_days` | `array(date)` | Sorted distinct valid source delivery days of this link across all versions; empty when undated. Never an inferred date range. | Yes |
| `conflict_days` | `array(date)` | Actual days of this link with multiple reported NPIs for its vendor and email; empty for undated vendors even when conflict is true. | Yes |
| `source_name_values` | `array(row(...))` | Distinct usable normalized vendor first/last names and first-name variants across the link versions. HealthLink uses its HCP reference; registry names never fill missing vendor names. | Yes |
| `source_state_values` | `array(varchar)` | Sorted distinct recognized US state/DC/territory codes across the link versions; HealthLink uses its HCP reference by NPI without date alignment. Missing, unrecognized and explicitly foreign values give an empty array. | Yes |
| `source_state_values_latest` | `array(varchar)` | Recognized state codes of the latest version. Null when the link has no single latest version. HealthLink uses its HCP reference. | — |
| `email_name_count` | `bigint` | Distinct normalized usable first/last-name pairs within this vendor and email across retained history. Zero means no usable names; fuzzy aliases remain separate spellings. | Yes |
| `email_npi_has_name_conflict` | `boolean` | True when any two usable names for this vendor/email/NPI disagree under metric 07 fuzzy rules; false with one name or all names compatible; null with no usable names. | — |
| `conflicting_npis_share_name` | `boolean` | Fuzzy agreement between any usable name of this link and a usable name of another NPI on overlapping conflict days, or in the undated vendor snapshot. True if any peer matches; false only if all comparisons are known mismatches; null for missing names or no established conflict. | — |
| `conflicting_npi_name_comparisons` | `array(row(...))` | Ordered peer comparison contexts with NPI, overlapping conflict days, usable vendor names and nullable shares_name. Empty without an established conflict; undated snapshot comparisons have empty days. | Yes |
| `conflicting_npis_share_state` | `boolean` | Overlap between the states of this link and those of other NPIs on overlapping conflict days or within the undated vendor snapshot. Any true wins; false requires all known mismatches; otherwise null, including no established conflict. | — |
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
| `npi_registry_status_as_of_day` | `date` | Date used to reject future events; America/New_York current date unless explicitly fixed. Does not reconstruct historical registry versions. | Yes |
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
| `vendor_state_evidence` | `varchar` | States across all link versions versus the own-NPI facility reference: corroborated, not_corroborated, mixed_vendor_states, unknown_vendor_state or unknown_facility. | Yes |
| `vendor_state_corroborated` | `boolean` | True only for a single matching vendor state, false for known disjoint states, null for mixed or unknown evidence. | — |
| `vendor_state_evidence_latest` | `varchar` | `vendor_state_evidence` using `source_state_values_latest`. Null when the link has no single latest version. | — |
| `vendor_state_corroborated_latest` | `boolean` | `vendor_state_corroborated` using `source_state_values_latest`. | — |
| `location_evaluation_day` | `date` | America/New_York evaluation day, or explicit location_evidence_day. No historical vendor-day reconstruction. | Yes |
| `location_reference_table` | `varchar` | bq_bi.analytics_prod.npi_facility_locations_with_ids; only rank-1 rows are used. | Yes |
| `location_evidence_version` | `varchar` | link_vendor_facility_state_v1; link-grain descriptive comparison without scoring. | Yes |

### Facility claims support

[Detailed definition](metrics/27_facility_claims_support.md). Core fields.

| Field | Trino type | Meaning / interpretation | Required |
|---|---|---|---|
| `facility_claim_count` | `bigint` | Claim count of the NPI's rank-1 claims-association row; null without a rank-1 row or without claim support. | — |
| `facility_sources` | `array(varchar)` | Sorted source labels (Claims, CMS, Healthlink, NPPES) supporting the rank-1 association; empty without a rank-1 row. | — |
| `facility_claims_backed` | `boolean` | True when Claims is among the sources, false when it is not, null without a rank-1 row. Descriptive, not a threshold. | — |
| `facility_claims_reference_table` | `varchar` | bq_bi.analytics_prod.npi_facility_association; only rank-1 rows are used. | — |
| `facility_claims_definition_version` | `varchar` | facility_claims_support_v1. | — |

### Domain evidence

[Detailed definition](metrics/28_domain_evidence.md). Domain fields are computed downstream of stored core, per source.

| Field | Trino type | Meaning / interpretation | Required |
|---|---|---|---|
| `email_domain` | `varchar` | Lowercase text after the first @ of the cleaned email; null without a domain. | — |
| `domain_email_count` | `bigint` | Distinct cleaned emails of this source on the domain. Counts include every domain class. | — |
| `domain_npi_count` | `bigint` | Distinct NPIs of this source reported with any email on the domain. | — |
| `domain_npis_with_state` | `bigint` | Domain NPIs with a usable `facility_primary_state`. Null for free-provider and unknown domains. | — |
| `domain_state_count` | `bigint` | Distinct `facility_primary_state` values across the domain's NPIs. Null for free-provider and unknown domains. | — |
| `domain_top_state_share` | `double` | Share of `domain_npis_with_state` in the most common facility state. Null without usable states. | — |
| `domain_npis_with_facility` | `bigint` | Domain NPIs with at least one retained facility NPI. Null for free-provider and unknown domains. | — |
| `domain_top_facility_npi` | `varchar` | Facility NPI shared by the most domain NPIs, ties broken by greater NPI text. Null without facilities. | — |
| `domain_top_facility_share` | `double` | Share of `domain_npis_with_facility` whose facility NPIs include `domain_top_facility_npi`. | — |
| `domain_evidence_version` | `varchar` | domain_evidence_v1; per-source domain aggregates over links, without scoring. | — |

### Cross-source evidence

[Detailed definition](metrics/29_cross_source_evidence.md). Cross-source fields are computed downstream of stored core by reading every other source; they are never null.

| Field | Trino type | Meaning / interpretation | Required |
|---|---|---|---|
| `xsrc_npi_agree_sources` | `array(varchar)` | Sorted other sources that report this email with this same NPI. Empty array when none. | — |
| `xsrc_npi_disagree_sources` | `array(varchar)` | Sorted other sources that report this email but never this NPI. | — |
| `xsrc_state_agree_sources` | `array(varchar)` | Sorted other sources that agree on the NPI and whose recognized vendor states overlap this link's. Unknown states appear in no state array. | — |
| `xsrc_state_disagree_sources` | `array(varchar)` | Sorted other sources that agree on the NPI and whose recognized vendor states are disjoint from this link's. | — |
| `xsrc_name_agree_sources` | `array(varchar)` | Sorted other sources that agree on the NPI and share at least one usable vendor name with this link. | — |
| `xsrc_name_disagree_sources` | `array(varchar)` | Sorted other sources that agree on the NPI, with usable names on both sides, where every name pair disagrees. | — |
| `xsrc_npi_agree_count` | `bigint` | Number of sources in `xsrc_npi_agree_sources`. | — |
| `xsrc_npi_disagree_count` | `bigint` | Number of sources in `xsrc_npi_disagree_sources`. | — |
| `xsrc_state_agree_count` | `bigint` | Number of sources in `xsrc_state_agree_sources`. | — |
| `xsrc_state_disagree_count` | `bigint` | Number of sources in `xsrc_state_disagree_sources`. | — |
| `xsrc_name_agree_count` | `bigint` | Number of sources in `xsrc_name_agree_sources`. | — |
| `xsrc_name_disagree_count` | `bigint` | Number of sources in `xsrc_name_disagree_sources`. | — |
| `xsrc_email_source_count` | `bigint` | Other sources that report this email at all: NPI-agreeing plus NPI-disagreeing sources. | — |
| `cross_source_evidence_version` | `varchar` | cross_source_evidence_v1; per-link agreement with every other source, without scoring or lineage adjustment. | — |

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
| `cookie_vendor_state_evidence` | `varchar` | Untied observed primary states versus this link’s source_state_values; nullable evidence is represented by explicit unknown labels. | — |
| `cookie_vendor_state_evidence_latest` | `varchar` | `cookie_vendor_state_evidence` using `source_state_values_latest`. Null when the link has no single latest version. | — |
| `cookie_facility_state_evidence` | `varchar` | Untied observed primary states versus this NPI’s usable rank-1 facility state. | — |
| `cookie_location_window_start` | `date` | Inclusive start of the stored cookie window: evaluation day minus cookie_location_window_days. Default window length is three completed days. | — |
| `cookie_location_window_end` | `date` | Evaluation day minus one, inclusive. | — |
| `cookie_mapping_table` | `varchar` | iceberg.thirdparty.liveintent_idsync. | — |
| `cookie_location_geo_table` | `varchar` | iceberg.crossscreen.nscreen_geo_daily_ua; snapshots may share a 15-day hourly lookback. | — |
| `cookie_zip_mapping_table` | `varchar` | iceberg.jteixeira_ipa.tmp_zip3_to_state; provider-derived mapping, not authoritative postal boundaries. | — |
| `cookie_location_evidence_version` | `varchar` | liveintent_primary_state_untied_v1; no scores or fractional votes. | — |

### Link freshness

[Detailed definition](metrics/20_link_freshness.md).

| Field | Trino type | Meaning / interpretation | Required |
|---|---|---|---|
| `link_freshness_as_of_day` | `date` | Evaluation day for stored link freshness, America/New_York today unless overridden. | Yes |
| `source_latest_observed_day` | `date` | Latest valid parsed observation day among the eligible links of this vendor, including future dates. | — |
| `link_last_observed_day` | `date` | Latest observation day of this source/email/NPI link. Null when undated. | — |
| `source_age_days` | `bigint` | Days from source_latest_observed_day to evaluation day. Null for undated or future-dated source evidence. | — |
| `link_lag_days` | `bigint` | Days from link_last_observed_day to source_latest_observed_day. Null for undated links or future-dated source evidence. No stale threshold. | — |

### Link presence and overlap

[Detailed definition](metrics/21_link_stability.md).

| Field | Trino type | Meaning / interpretation | Required |
|---|---|---|---|
| `email_observed_day_count` | `bigint` | Distinct known observation days across all NPIs for this source/email. Zero means no dated email history. | Yes |
| `link_observed_day_count` | `bigint` | Distinct known observation days of this source/email/NPI link, across all versions and email positions. | Yes |
| `link_conflict_day_count` | `bigint` | Distinct days this source/email/NPI overlapped another NPI. Zero counts known overlap days only. | Yes |
| `link_presence_share` | `double` | Link observed days divided by email observed days, as a fraction from zero to one. Null when this link has no dated observations. | — |
| `link_overlap_share` | `double` | Link conflict days divided by link observed days, as a fraction from zero to one. Null for undated links. | — |
| `link_stability_has_undated_observations` | `boolean` | True when any link of this source/email, including peer NPIs, contains undated or invalid-day observations. Shares cover known dates only. | Yes |

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
| `npi_entity_type_reference_row_count` | `bigint` | Number of NPPES reference rows for the identifier. Duplicate rows never multiply links. | Yes |
| `npi_entity_type_variant_count` | `bigint` | Number of distinct trimmed entity-code variants, counting missing as a variant. | Yes |
| `npi_identity_as_of_day` | `date` | America/New_York evaluation date for current registry evidence. Not the reference file delivery date or historical vendor-day evidence. | Yes |
| `npi_identity_reference_table` | `varchar` | Registry relation used for entity type evidence. | Yes |
| `npi_identity_definition_version` | `varchar` | Version of structural validation and entity-consensus rules. | Yes |

### Vendor specialty and profession

[Detailed definition](metrics/23_conflicting_npis_share_vendor_specialty.md).

| Field | Trino type | Meaning / interpretation | Required |
|---|---|---|---|
| `source_vendor_specialty_values` | `array(varchar)` | Distinct normalized vendor specialty labels across the link observation days. DRDB uses the raw `specialty` labels of all versions. Comparisons use day-specific evidence, not this union. | Yes |
| `source_vendor_profession_values` | `array(varchar)` | Distinct normalized vendor profession labels across the link observation days. Credentials and registry classifications are excluded. | Yes |
| `vendor_professional_evidence` | `array(row(...))` | Per-observation-day vendor table provenance, raw specialty/profession labels and normalized values. Metadata joins match the delivery day and NPI, plus Medscape guid using each GUID's own days. Empty arrays preserve missing evidence. | Yes |
| `vendor_professional_definition_version` | `varchar` | Version of vendor-label normalization, same-day joins and conflict comparison rules. | Yes |
| `conflicting_npis_share_vendor_specialty` | `boolean` | Whether any conflicting peer NPI has an exact normalized vendor specialty overlap on the same conflict day, or in the undated DRDB snapshot. False requires all comparisons known and disjoint. Otherwise unknown or inapplicable. | — |
| `conflicting_npi_vendor_specialty_comparisons` | `array(row(...))` | Peer NPI, peer link ID, evidence day, own and peer specialty labels, shared labels and nullable shares_specialty. | Yes |
| `conflicting_npis_share_vendor_profession` | `boolean` | Whether any conflicting peer NPI has an exact normalized vendor profession overlap on the same conflict day. False requires all comparisons known and disjoint. Missing profession evidence stays unknown. | — |
| `conflicting_npi_vendor_profession_comparisons` | `array(row(...))` | Peer NPI, peer link ID, evidence day, own and peer profession labels, shared labels and nullable shares_profession. | Yes |

[Profession overlap](metrics/24_conflicting_npis_share_vendor_profession.md) is separate from specialty overlap and NPPES taxonomy. Unsupported vendor attributes remain unknown.

### Sequential email history

[Detailed definition](metrics/25_sequential_history.md).

| Field | Trino type | Meaning / interpretation | Required |
|---|---|---|---|
| `sequence_as_of_day` | `date` | Inclusive evaluation cutoff for sequential history and registration supersession. Defaults to America/New_York today. Daily evidence uses only observations through its own day. | — |
| `sequence_definition_version` | `varchar` | Sequence, delivery-version and cumulative-count rule version. | — |
| `sequence_history_status` | `varchar` | dated_history, incomplete_dates or no_dated_history. Known-date counts do not infer missing observations. | — |
| `sequence_has_undated_observations` | `boolean` | Any eligible link of this source/email has missing or invalid observation dates. | — |
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
| `registration_guid` | `varchar` | Cleaned Medscape registration GUID most recently observed for this link. NULL for other sources. | — |
| `registration_link_status` | `varchar` | Medscape source/GUID/email/NPI status through sequence_as_of_day: latest_observed, superseded, ambiguous_latest or unknown. Other sources are not_applicable. Missing GUID, dates or incomplete registration chronology remain unknown. | — |
| `registration_latest_observed_day` | `date` | Latest eligible dated observation for this source/GUID/email through sequence_as_of_day. | — |
| `registration_latest_npis` | `array(varchar)` | Distinct NPIs on registration_latest_observed_day. Multiple NPIs are ambiguous and never arbitrarily resolved. | — |
| `registration_link_last_observed_day` | `date` | Last eligible dated observation of this source/GUID/email/NPI through sequence_as_of_day. | — |
| `registration_superseded_since_day` | `date` | First observed registration day after the old NPI last appeared, only when its current status is superseded. This classification is evaluated at sequence_as_of_day and is not a historical ownership claim. | — |
| `registration_superseded_by_npis` | `array(varchar)` | Unique latest observed registration NPI for a superseded link. Empty for unknown, ambiguous, latest or inapplicable links. | — |
| `registration_supersession_definition_version` | `varchar` | Registration supersession rule version. No links are removed or redirected. | — |

## Nested evidence schemas

Each structure below is one element of the named array. Names are literal SQL member names. Peer `npi` values identify comparison targets; nested peer arrays do not create additional final-table rows. `conflict_days` contains actual overlapping dates, not a date range. Raw lifecycle strings remain text even where separately parsed date fields exist.

### `attribute_versions`

| Member | Trino type |
|---|---|
| `record_id` | `varchar` |
| `first_seen_day` | `date` |
| `last_seen_day` | `date` |
| `observed_day_count` | `bigint` |
| `observation_count` | `bigint` |
| `email_origins` | `array(varchar)` |
| `record_payload` | `varchar` |

`record_payload` is JSON text with every identity field of the version except `day`. Top-level timestamps, dates and decimals are serialized as strings. Volatile fields appear as sorted distinct arrays.

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
| `link_id` | `varchar` |
| `evidence_day` | `date` |
| `own_values` | `array(varchar)` |
| `peer_values` | `array(varchar)` |
| `shared_values` | `array(varchar)` |
| `shares_specialty` | `boolean` |

### `conflicting_npi_vendor_profession_comparisons`

| Member | Trino type |
|---|---|
| `npi` | `varchar` |
| `link_id` | `varchar` |
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

Use `link_id` (or `source, email, npi`) when joining link-level evidence. Use `source, email` for vendor email-history metrics. A `record_id` identifies one version; `record_ids` and `attribute_versions` list the versions of a link. Reference joins are collapsed before attaching evidence to avoid multiplying links.

`observed_day_count` counts dates across all versions of one link and equals `link_observed_day_count`; `email_observed_day_count` unions dates across its vendor/email. `link_presence_share = link_observed_day_count / email_observed_day_count`. `link_overlap_share = link_conflict_day_count / link_observed_day_count`. Shares are fractions from zero to one, with null for unavailable dated link history. `link_stability_has_undated_observations` qualifies known-date shares. Email-level metrics count links, not versions.

`source_age_days` compares the vendor's latest eligible observation with `link_freshness_as_of_day`. `link_lag_days` compares the link's latest observation with that vendor baseline. No freshness threshold is assigned. `n_npis_window` uses all retained eligible dated history through `sequence_as_of_day`; despite its name, it is not a rolling calendar window.

`registration_*` supersession is evaluated per link and registration GUID, using that GUID's own days; a link reports its most recently observed GUID. Other sources have `not_applicable` status. Old links remain stored. A unique latest NPI can supersede an older claim; multiple latest NPIs remain ambiguous. Missing GUID or chronology remains unknown.

## Definition sources and reproduction

Semantics and local required tests: [final contract](../models/final/schema.yml), [vendor models](../models/intermediate/README.md), [source map](00_source_map.md), [metric definitions](metrics/README.md) and [cookie macro](../macros/cookie_location.sql). `cookie_location_window_start` uses the configured window length.

Compare the published physical schema with this contract:

```sql
SELECT ordinal_position, column_name, data_type, is_nullable
FROM iceberg.information_schema.columns
WHERE table_schema = 'jteixeira_ipa' AND table_name = 'pii_clean'
ORDER BY ordinal_position
```

Check the publication state and table comment:

```sql
SHOW CREATE TABLE iceberg.jteixeira_ipa.pii_clean
```

These checks inspect schema and the table comment. They do not scan PII records. The dictionary covers stored columns only; six display/count helpers in the [email lookup](email_lookup.md) are computed query outputs and are excluded.

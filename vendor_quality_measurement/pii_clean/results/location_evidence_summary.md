# Vendor/facility state and cookie-location measurements

**Status:** native Trino fixtures, all seven vendor plans and full-population read-only measurements passed on October 29, 2026. The location-validation checkpoint passed 55 local tests; the latest complete suite passed 58, including the complete email lookup. Metrics remain unpublished; warehouse views and tables were not changed.

Both measurements retained all 75,564,265 exact-record/email-position rows and 26,730,605 distinct source/email/NPI links from the same saved `iceberg.jteixeira_ipa.pii_clean` snapshot. Each measurement rechecked that the input snapshot stayed unchanged. The saved vendor-row count is not a count of independent identity confirmations.

Usable untied same-day primary-state observations accompany 2,728,645 (10.21%) of all source/email/NPI links. This is evidence availability, not an ownership-accuracy or advertising-reach estimate.

## Scope and source window

Evaluation day: October 29, 2026. Cookie window: October 22–28, inclusive; evaluation-day and future rows are excluded. Every historical vendor record remains. Current-window cookie evidence and undated facility references are retrospective comparisons, not historical attendance reconstructions.

Source-date coverage was unchanged before and after the population scan:

| Source | Dates present | Dates missing |
|---|---:|---|
| LiveIntent mappings | 6/7 (85.71%) | October 28 |
| UID geography | 7/7 (100%) | None |

Positive partition file counts establish date presence only, not logical-row completeness or individual UID coverage. Geo snapshots can share a 15-day hourly lookback, so days are not independent confirmations. Raw source/reference snapshots are not pinned for later reproduction.

Coverage, executed cookie SQL and aggregate results (local-only: `location_evidence_cookie.json`) · Earlier partition/token inspection (local-only: `location_source_inspection.json`)

## Vendor state versus own-NPI facility state

Read rank-1 `bq_bi.analytics_prod.npi_facility_locations_with_ids` rows, normalize recognized states and collapse per NPI before joining. A usable reference has one distinct recognized state and no missing state/location rows. Duplicates do not multiply records. HealthLink vendor states come from its HCP reference across retained history; other vendor states belong to their exact source record. The mixed-source facility reference can share vendor lineage.

Percentages use all distinct email–NPI links in each vendor. One historical link can have several record-state outcomes; outcome columns can overlap. They are not exclusive link classifications. Record-level outcomes do partition records.

| Vendor | Links | Agreement, n (%) | Disagreement, n (%) | Mixed, n (%) | Unknown facility, n (%) | Unknown vendor state, n (%) |
|---|---:|---:|---:|---:|---:|---:|
| HealthLink | 7,688,451 | 2,494,102 (32.44%) | 254,820 (3.31%) | 67,246 (0.87%) | 4,869,682 (63.34%) | 2,601 (0.03%) |
| QuantumMedica | 1,705,723 | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 921,625 (54.03%) | 784,098 (45.97%) |
| Medscape | 3,659,306 | 795,002 (21.73%) | 449,459 (12.28%) | 0 (0.00%) | 2,366,162 (64.66%) | 50,457 (1.38%) |
| Endato | 5,427,459 | 696,254 (12.83%) | 952,801 (17.56%) | 0 (0.00%) | 3,777,928 (69.61%) | 476 (0.00877%) |
| RocketReach | 3,199,535 | 895,708 (27.99%) | 151,318 (4.73%) | 0 (0.00%) | 1,984,594 (62.03%) | 167,915 (5.25%) |
| DRDB | 826,886 | 261,222 (31.59%) | 36,685 (4.44%) | 0 (0.00%) | 529,129 (63.99%) | 0 (0.00%) |
| Haymarket | 4,223,245 | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 2,447,670 (57.96%) | 1,775,575 (42.04%) |

QuantumMedica and Haymarket provide no usable vendor states in this saved population. They therefore cannot produce a vendor-state agreement or disagreement, even when a facility reference exists. Missing facility evidence and missing vendor state remain separate outcomes. Disagreement alone does not establish a bad identity link.

Executed facility queries and results (local-only: `location_evidence_facility.json`)

## Cookie/UID evidence availability

Hash normalized email with SHA-256 and join historical `iceberg.thirdparty.liveintent_idsync.hashedemail_sha256`. Parse pipe-separated namespace/UID tokens; reject malformed tokens and deduplicate hash/day/UID tuples. Namespace labels remain auditable, and UID string prefixes remain intact. These identifiers are not verified browser cookies.

Join exact UID to same-day `iceberg.crossscreen.nscreen_geo_daily_ua`, reconstructing state through `iceberg.jteixeira_ipa.tmp_zip3_to_state`. Duplicate ZIP3 rows collapse; conflicting or missing state mappings remain unknown. This provider-derived map is approximate, particularly near borders. Persisted state-table files are not read.

Rank recognized states per UID by distinct observed dates before email joins. The primary state must occur on its mapping date. Ties retain diagnostic counts but earn no agreement. Located UID-day counts include tied winners; eligible UID-day counts exclude them. Only untied same-day primary states enter `cookie_state_values`. No identity scores, cross-source votes or fractional weights are calculated.

Availability percentages below use all distinct emails within the vendor. Mapped means at least one usable parsed UID mapping. Usable location requires at least one untied same-day primary-state observation. Dates missing from the mapping source may reduce coverage; no_mapping does not prove that no cookie exists.

| Vendor | Distinct emails | Mapped emails, n (%) | Usable location, n (%) | Any tied UID, n (%) | Any multistate UID, n (%) |
|---|---:|---:|---:|---:|---:|
| HealthLink | 7,688,331 | 945,350 (12.30%) | 831,785 (10.82%) | 12,031 (0.16%) | 198,921 (2.59%) |
| QuantumMedica | 1,705,695 | 152,521 (8.94%) | 132,843 (7.79%) | 1,881 (0.11%) | 31,607 (1.85%) |
| Medscape | 3,550,052 | 690,616 (19.45%) | 608,507 (17.14%) | 8,967 (0.25%) | 149,258 (4.20%) |
| Endato | 5,324,318 | 571,564 (10.73%) | 506,730 (9.52%) | 7,676 (0.14%) | 123,578 (2.32%) |
| RocketReach | 3,163,679 | 155,616 (4.92%) | 136,876 (4.33%) | 1,956 (0.06%) | 31,938 (1.01%) |
| DRDB | 819,454 | 71,989 (8.78%) | 63,030 (7.69%) | 912 (0.11%) | 15,360 (1.87%) |
| Haymarket | 4,223,245 | 467,700 (11.07%) | 409,659 (9.70%) | 5,933 (0.14%) | 99,423 (2.35%) |

An email with some tied UIDs can still have other usable untied evidence. Do not sum these email counts across vendors to infer globally unique emails; vendors can report the same email. Do not sum repeated per-email UID/day counts across record rows.

### Cookie location status at link grain

Percentages use all distinct source/email/NPI links in the vendor. These status groups are exclusive and partition each vendor’s links.

| Vendor | No usable mapping, n (%) | Mapped/no same-day observation, n (%) | Unknown usable state, n (%) | Only tied located evidence, n (%) | Usable observation, n (%) |
|---|---:|---:|---:|---:|---:|
| HealthLink | 6,743,094 (87.70%) | 112,091 (1.46%) | 983 (0.01%) | 491 (0.00639%) | 831,792 (10.82%) |
| QuantumMedica | 1,553,202 (91.06%) | 19,429 (1.14%) | 168 (0.00985%) | 81 (0.00475%) | 132,843 (7.79%) |
| Medscape | 2,943,480 (80.44%) | 83,883 (2.29%) | 758 (0.02%) | 407 (0.01%) | 630,778 (17.24%) |
| Endato | 4,839,998 (89.18%) | 65,554 (1.21%) | 633 (0.01%) | 299 (0.00551%) | 520,975 (9.60%) |
| RocketReach | 3,042,054 (95.08%) | 18,690 (0.58%) | 171 (0.00534%) | 93 (0.00291%) | 138,527 (4.33%) |
| DRDB | 753,679 (91.15%) | 9,019 (1.09%) | 73 (0.00883%) | 44 (0.00532%) | 64,071 (7.75%) |
| Haymarket | 3,755,545 (88.93%) | 57,278 (1.36%) | 491 (0.01%) | 272 (0.00644%) | 409,659 (9.70%) |

Unknown usable state includes unknown ZIP3 mapping and cases where only a discarded secondary state was observed on mapping dates. Only tied located evidence means located primary-state days exist but none is eligible. A separate tie count also identifies ties without a matching located day.

### Cookie-state comparisons

The following counts concern links with at least one record in the named comparison outcome. Percentages use all distinct links within that vendor. Vendor-state outcomes may overlap at link grain when historical states differ. The comparisons concern retained usable state sets; agreement does not establish coverage of every mapped UID.

| Vendor | Cookie/vendor agreement, n (%) | Cookie/vendor disagreement, n (%) | Cookie/facility agreement, n (%) | Cookie/facility disagreement, n (%) |
|---|---:|---:|---:|---:|
| HealthLink | 184,486 (2.40%) | 367,121 (4.77%) | 63,638 (0.83%) | 119,459 (1.55%) |
| QuantumMedica | 0 (0.00%) | 0 (0.00%) | 13,254 (0.78%) | 30,490 (1.79%) |
| Medscape | 156,722 (4.28%) | 211,773 (5.79%) | 62,818 (1.72%) | 71,016 (1.94%) |
| Endato | 110,392 (2.03%) | 251,746 (4.64%) | 24,884 (0.46%) | 110,574 (2.04%) |
| RocketReach | 30,739 (0.96%) | 40,318 (1.26%) | 17,256 (0.54%) | 20,909 (0.65%) |
| DRDB | 16,386 (1.98%) | 23,914 (2.89%) | 7,189 (0.87%) | 8,267 (1.00%) |
| Haymarket | 0 (0.00%) | 0 (0.00%) | 48,731 (1.15%) | 55,562 (1.32%) |

Mixed-state evidence and explicit unknown-reference/unknown-cookie outcomes remain in the machine-readable results. Unknowns are not folded into disagreement. In particular, cookie geography can be compared with a usable facility reference even when the vendor supplies no state.

## Original-state diagnostic examples

Truncated, nonrandom sample: up to 500 stored records per selected vendor. These grouped examples preserve original state text without exporting email, UID or hash identifiers. Sample counts are not population prevalence estimates. Executed sample SQL and aggregate results (local-only: `location_facility_examples.json`).

| Vendor | Original state text | Normalized states | Facility state | Outcome | Sample records, n (% of 500) |
|---|---|---|---|---|---:|
| Endato | `"CA"` | CA | CA | corroborated | 8 (1.60%) |
| Endato | `"OH"` | OH | CA | not_corroborated | 3 (0.60%) |
| Endato | `"FL"` | FL | Unknown | unknown_facility | 45 (9.00%) |
| Medscape | `"IL"` | IL | IL | corroborated | 94 (18.80%) |
| Medscape | `"MA"` | MA | CT | not_corroborated | 53 (10.60%) |
| Medscape | `"TX"` | TX | Unknown | unknown_facility | 72 (14.40%) |
| QuantumMedica | `NULL` | None | Unknown | unknown_facility | 265 (53.00%) |
| QuantumMedica | `NULL` | None | CA | unknown_vendor_state | 38 (7.60%) |
| RocketReach | `"CA "` | CA | CA | corroborated | 27 (5.40%) |
| RocketReach | `"OK "` | OK | FL | not_corroborated | 4 (0.80%) |
| RocketReach | `"CA "` | CA | Unknown | unknown_facility | 40 (8.00%) |
| RocketReach | `NULL` | None | CA | unknown_vendor_state | 6 (1.20%) |

Trailing whitespace in RocketReach state text normalizes before comparison. QuantumMedica sample rows retain missing state as unknown. Missing facility state is not treated as vendor disagreement.

## Output columns

Eleven facility-comparison fields and thirty cookie-evidence fields are appended to existing record outputs. Local model and schema metadata agree on 103 total columns. Existing source attributes and indicators remain; no identity score is produced.

### Vendor/facility state

| Column | Meaning |
|---|---|
| `facility_primary_state` | Single recognized rank-1 facility state when every retained rank-1 row has a recognized state and nonblank location; null for ambiguity or missing evidence. |
| `facility_reference_status` | usable, ambiguous_state, missing_state, missing_location or no_rank1_association; independent of vendor-state availability. |
| `facility_rank1_rows` | Raw rank-1 reference rows before per-NPI collapse; zero without a match. |
| `facility_rank1_state_count` | Distinct recognized rank-1 facility states before collapse. |
| `facility_rank1_unknown_state_rows` | Rank-1 reference rows with missing or unrecognized state. |
| `facility_rank1_missing_location_rows` | Rank-1 reference rows with blank or missing coordinates. |
| `vendor_state_evidence` | Record-state versus own-NPI facility reference: corroborated, not_corroborated, mixed_vendor_states, unknown_vendor_state or unknown_facility. |
| `vendor_state_corroborated` | True only for a single matching vendor state, false for known disjoint states, null for mixed or unknown evidence. |
| `location_evaluation_day` | Europe/Paris evaluation day, or explicit location_evidence_day. No historical vendor-day reconstruction. |
| `location_reference_table` | bq_bi.analytics_prod.npi_facility_locations_with_ids; only rank-1 rows are used. |
| `location_evidence_version` | record_vendor_facility_state_v1; record-grain descriptive comparison without scoring. |

### Cookie evidence

| Column | Meaning |
|---|---|
| `cookie_count` | Distinct usable mapped UID strings within the seven completed days; not verified browser-cookie counts. |
| `cookie_mapping_days` | Distinct dates with a valid email-hash/UID mapping. |
| `cookie_mapped_uid_days` | Distinct UID/mapping-day tuples after token and row deduplication. |
| `cookie_observed_uid_days` | Mapped UID-days with any same-day geo observation, including unmapped ZIP3 states. |
| `cookie_located_uid_days` | Mapped UID-days whose ranked primary recognized state appears on that day; includes tied winners. |
| `cookie_eligible_uid_days` | Located mapped UID-days with an untied primary state; only these establish state comparisons. |
| `cookie_located_count` | Distinct UIDs with a located primary-state mapping day, including ties. |
| `cookie_primary_state_tied_count` | Distinct mapped UIDs with multiple recognized states tied for most observed dates. |
| `cookie_primary_state_multistate_count` | Distinct mapped UIDs with more than one recognized state in the window. |
| `cookie_eligible_observed_days` | Distinct mapping dates carrying untied primary-state observations. |
| `cookie_location_first_day` | First untied primary-state mapping date; null without usable observations. |
| `cookie_location_last_day` | Last untied primary-state mapping date; null without usable observations. |
| `cookie_uid_types` | Sorted distinct mapping namespace labels; raw UID strings retain their prefixes for joins. |
| `cookie_state_values` | Sorted distinct untied primary states observed on matching mapping dates. Tied states supply no agreement. |
| `cookie_location_window_days` | Seven completed calendar days before location_evaluation_day. |
| `cookie_mapping_available_days` | Dates present in mapping partition metadata; presence does not prove complete rows. |
| `cookie_location_available_days` | Dates present in geo partition metadata; presence does not prove complete rows. |
| `cookie_mapping_missing_days` | Expected dates absent from mapping metadata; missing dates are not mismatches. |
| `cookie_location_missing_days` | Expected dates absent from geo metadata. |
| `cookie_location_window_status` | all_source_days_present or missing_source_days; not a population-completeness guarantee. |
| `cookie_state_count` | Number of retained usable cookie_state_values. |
| `cookie_location_status` | no_mapping, observed, ambiguous_primary_state, unknown_state or no_state_observation. no_mapping means no valid parsed mapping, not proof that no cookie exists. |
| `cookie_vendor_state_evidence` | Untied observed primary states versus this exact record’s source_state_values; nullable evidence is represented by explicit unknown labels. |
| `cookie_facility_state_evidence` | Untied observed primary states versus this NPI’s usable rank-1 facility state. |
| `cookie_location_window_start` | Evaluation day minus seven; current and future days are excluded. |
| `cookie_location_window_end` | Evaluation day minus one, inclusive. |
| `cookie_mapping_table` | iceberg.thirdparty.liveintent_idsync. |
| `cookie_location_geo_table` | iceberg.crossscreen.nscreen_geo_daily_ua; snapshots may share a 15-day hourly lookback. |
| `cookie_zip_mapping_table` | iceberg.jteixeira_ipa.tmp_zip3_to_state; provider-derived mapping, not authoritative postal boundaries. |
| `cookie_location_evidence_version` | liveintent_primary_state_untied_v1; no scores or fractional votes. |

## Validation and publication

- The saved location-validation checkpoint passed 55 local tests, including duplicate/conflicting facility rows, missing states/locations/ranks, duplicate UID tokens, namespace labels, ZIP3 padding/ambiguity, ties, majority states, exact mapping dates, missing dates and evaluation/future exclusion.
- Native Trino checked all 18 synthetic records and both independent invariant queries, returning zero failures. Cases explicitly separate vendor-state disagreement from facility-state agreement.
- Both full-population measurements retained 75,564,265 metric rows with unique source/metric-row keys and zero invariant failures. Cookie location-status groups also partitioned all 26,730,605 distinct source/email/NPI links.
- Both runs used the same saved input snapshot, and each verified it stayed unchanged. Source-date availability also matched before and after the cookie scan. This is read-only enrichment, not a full raw-source rebuild or before/after checksum comparison of every original attribute.
- All seven production vendor queries planned successfully: HealthLink 117, QuantumMedica 102, Medscape 102, Endato 93, RocketReach 93, DRDB 110, Haymarket 102 fragments; each is below the 150-stage limit. Native planning does not prove performance of a full future source rebuild.
- The [complete email lookup](../docs/email_lookup.md) passed native validation, planning with 46 fragments and three synthetic record checks across all five new groups. No real email-result rows were fetched. The latest complete local suite (local-only: `email_lookup_full_local_tests.txt`) passed 58 tests; native lookup evidence (local-only: `email_lookup_full_validation.json`) records its own validation.
- New fields remain unpublished as stored warehouse columns. The complete lookup computes them in read-only CTEs; the published-only shortcut remains a subset. No warehouse tables or views were changed by these read-only validations. A future complete local build includes all five additions: facility relatedness, specialty relatedness, lifecycle, vendor/facility state and cookie location.

### Reproduce read-only checks

From the project directory; this measurement tool fixes evaluation to October 29, 2026:

```bash
../../.venv/bin/python tools/measure_location_evidence.py native
../../.venv/bin/python tools/measure_location_evidence.py plans
../../.venv/bin/python tools/measure_location_evidence.py facility
../../.venv/bin/python tools/measure_location_evidence.py cookie
```

Live measurement outputs contain aggregate counts and validation results only. Raw mapping payloads are not exported.

[Vendor-state definition](../docs/metrics/18_vendor_facility_state.md) · [Cookie definition](../docs/metrics/19_cookie_location_evidence.md) · Local tests (local-only: `location_evidence_local_tests.txt`) · Native evidence (local-only: `location_evidence_native.json`) · Vendor plans (local-only: `location_evidence_plans.json`)

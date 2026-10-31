# Metrics

All **26 metric pages** contain executed real examples, explanations and population statistics. The documentation was refreshed **October 31, 2026**, against `iceberg.jteixeira_ipa.pii_clean` snapshot **`8811920360682490090`**: **75,656,369 metric records across seven sources**.

The refresh executed **32 published-population statistics queries** and **28 example queries** in native Trino. Each page links the exact snapshot-pinned SQL and displays selected results. Pages 23 and 24 include shared, disjoint, unknown and not-applicable vendor-label examples. Page 19 uses the published three-day cookie window, October 28–30, including the missing October 30 input flags. No metric page relies on the old candidate or partial publication for its current results.

| Order | Metric | Question |
|---|---|---|
| 01 | [Observation counts](01_observation_counts.md) | How often does the same exact source record recur? |
| 02 | [Email format](02_email_format_valid.md) | Does the email match the documented format pattern? |
| 03 | [Role accounts](03_email_role_account.md) | Does the mailbox name match a potentially shared inbox name? |
| 04 | [Domain classification](04_email_domain_class.md) | Does the domain text suggest institutional, free-provider or other usage? |
| 05 | [Email matches source name](05_email_matches_source_name.md) | Does the mailbox text resemble the vendor name? |
| 06 | [Email matches registry name](06_email_matches_registry_name.md) | Does the mailbox text resemble a registry name for the NPI? |
| 07 | [Vendor name matches registry name](07_vendor_name_matches_registry_name.md) | Do vendor and registry name pairs agree under fuzzy comparison? |
| 08 | [Email–NPI multiplicity](08_email_npi_multiplicity.md) | How many distinct NPIs does this vendor report for an email? |
| 09 | [Has been reassigned](09_has_been_reassigned.md) | Does the email's reported NPI set change between observed days? |
| 10 | [Has conflict linkage](10_has_conflict_linkage.md) | Does this record overlap other NPIs on an observed day, or in the undated vendor data? |
| 11 | [Email name count](11_email_name_count.md) | How many usable normalized names does this vendor report for an email? |
| 12 | [Email–NPI name conflict](12_email_npi_has_name_conflict.md) | Does one vendor/email/NPI carry names that disagree under fuzzy matching? |
| 13 | [Conflicting NPIs share a name](13_conflicting_npis_share_name.md) | Does this record share a fuzzy-matching name with another NPI in its conflict context? |
| 14 | [Conflicting NPIs share a state](14_conflicting_npis_share_state.md) | Does this record share a recognized state with another NPI in its conflict context? |
| 15 | [Conflicting NPIs share a facility](15_conflicting_npis_share_facility.md) | Do retained facility NPIs overlap in this conflict context? |
| 16 | [Conflicting NPIs share an NPPES specialty](16_conflicting_npis_share_specialty.md) | Do conflicting NPIs share an exact recognized NPPES taxonomy code? |
| 17 | [NPI registry status](17_npi_registry_status.md) | What lifecycle status does stored NPPES evidence report? |
| 18 | [Vendor versus facility state](18_vendor_facility_state.md) | Does this exact record agree with its own NPI’s preferred facility state? |
| 19 | [Cookie-location evidence](19_cookie_location_evidence.md) | What untied primary states accompany historical email–UID mappings in the evaluation window? |
| 20 | [Link freshness](20_link_freshness.md) | How old is the vendor evidence, and how far does each link trail its vendor? |
| 21 | [Link stability](21_link_stability.md) | On what share of observed email days did this NPI appear, and how often did another NPI overlap? |
| 22 | [NPI validity and entity type](22_npi_identity.md) | Is the identifier structurally valid, and does NPPES identify an individual or organization? |
| 23 | [Conflicting NPIs share vendor specialty](23_conflicting_npis_share_vendor_specialty.md) | Do conflicting NPIs share exact normalized vendor specialty labels on eligible dates? |
| 24 | [Conflicting NPIs share vendor profession](24_conflicting_npis_share_vendor_profession.md) | Do conflicting NPIs share exact normalized vendor profession labels on eligible dates? |
| 25 | [Sequential history](25_sequential_history.md) | How often does a vendor change an email’s NPI set, swap NPIs or return to earlier NPIs? |
| 26 | [Registration supersession](26_registration_supersession.md) | Which Medscape registration claims have been superseded by a unique latest NPI? |

## Counting units and dates

A metric record is one exact source record and email position, keyed by `source, metric_row_id`. Other denominators are explicitly named: source/emails, source/email/NPI links, source/NPIs or Medscape GUID/email/NPI/status links. Counts across vendors can overlap and must not be added as globally distinct people or emails. Unknown, false, not applicable and zero-denominator percentages are separate outcomes.

Extraction reads stored evidence without changing evaluation dates. For example, Medscape sequence/freshness evidence remains evaluated on October 30 while cookie evidence uses an October 31 evaluation. Name displays on pages 06 and 07 additionally read the current name-reference view; these display names are not pinned with the stored indicators. Selected examples explain behavior and do not establish prevalence or ownership.

## Reproduction and maintenance

[Example SQL](../../sql/examples/) and [statistics SQL](../../sql/statistics/README.md) are read-only. Current page queries pin the verified snapshot and preserve metric names, scope and denominators. The two raw NPPES diagnostics and the dated partial-history query are separately identified in the statistics index; they are not the basis of current metric-page populations.

The pipeline overview and [build evidence](../build_recovery.md) document publication validation. The 120-test local suite is a separate build checkpoint; this documentation refresh verified queries against the warehouse. Future publications do not automatically refresh these pages. Refresh SQL, displayed results, dates, snapshot IDs and interpretation together. Keep query results in memory and retain selected findings in Markdown rather than exporting result dumps. Use the [page template](_template.md) when adding a metric.

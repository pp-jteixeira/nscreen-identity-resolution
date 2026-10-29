# Metrics

Read these pages in order. Each explains its question, calculation, examples, limitations, exact columns and source statistics. “How it is computed” gives the grouping scope and short SQL expressions. These are calculation excerpts, not standalone queries; named helper values are explained locally. Full SQL stays linked. Counts describe source-record email positions; they do not establish ownership or scoring weights.

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
| 15 | [Conflicting NPIs share a facility](15_conflicting_npis_share_facility.md) | Do retained facility NPIs overlap in this conflict context? Implemented and measured read-only; publication pending. |
| 16 | [Conflicting NPIs share a specialty](16_conflicting_npis_share_specialty.md) | Do conflicting NPIs share an exact recognized NPPES taxonomy code? Implemented and measured read-only; publication pending. |
| 17 | [NPI registry status](17_npi_registry_status.md) | What lifecycle status does current readable NPPES evidence report? Implemented and measured read-only; publication pending. |
| 18 | [Vendor versus facility state](18_vendor_facility_state.md) | Does this exact record agree with its own NPI’s preferred facility state? Native and full-population read-only checks passed; publication pending. |
| 19 | [Cookie-location evidence](19_cookie_location_evidence.md) | What untied primary states accompany historical email–UID mappings in the evaluation window? Native and full-population read-only checks passed; publication pending. |

One metric-output row represents one exact source record and email position, keyed by `source`, `metric_row_id`. Only raw rows identical except for `day` combine. Email–NPI deduplication is deferred until after metrics and indicators. Repeated source records and distinct observed dates are different counting units. See the [pipeline overview](../../README.md) for row meaning and the [source map](../00_source_map.md) for inputs and available history.

Every statistics section links a standalone query under [statistics SQL](../../sql/statistics/README.md). These queries produce population statistics; calculation macros define the indicators themselves. Pages 01–07 link equivalent direct aggregations of their saved grouped extraction. Pages 08–19 link the original executed statements, exported without result rows. Historical relations and evaluation dates remain explicit; running a query against changed inputs does not reproduce the original measurement automatically.

Use the [page template](_template.md) for each new metric. Statistics identify their measurement date and output relation. Pages 01–07 use saved October 29 published-table row populations. Pages 08–10 retain the October 28 baseline; their Medscape population differs from the October 29 table. Pages 11–13 preserve dated prototype measurements. References to `pii__evidence` describe the original measurement relation, not a managed current output or a guarantee that the table still exists. Use `pii_clean` for stored metrics and the [complete lookup](../email_lookup.md) for all implemented groups.

Historical metric-specific validation logs retain their original suite sizes. The latest complete local suite (local-only: `../../results/email_lookup_full_local_tests.txt`) passed 58 tests. The [pipeline overview](../../README.md) distinguishes the 41 stored columns, 103 local model columns and 109 complete-lookup outputs. Saved measurements are dated evidence; they are not automatically refreshed.

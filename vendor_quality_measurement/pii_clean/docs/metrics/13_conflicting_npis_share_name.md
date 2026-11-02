# Conflicting NPIs share a name

**Question:** does this link share a fuzzy-matching vendor name with another NPI in its conflict context? A shared name does not establish which NPI is correct.

**Where:** `conflicting_npis_share_name` in `iceberg.jteixeira_ipa.pii__int_<vendor>__metrics` and `iceberg.jteixeira_ipa.pii_clean`; key: `source`, `link_id` (one source/email/NPI link).

## How it is computed

Within the same vendor/email, compare this link's `source_name_values` with the links of other NPIs whose `conflict_days` overlap. Both sides use the union of usable names across all versions of the link. Endato, RocketReach and DRDB instead compare every other NPI of the email in one current snapshot per vendor, including both DRDB feeds. Never infer overlap from date bounds or use names from unrelated dates.

Both first and last names must agree under [metric 07's fuzzy rules](07_vendor_name_matches_registry_name.md). Each peer comparison is true for any matching name pair, false when usable names exist on both sides but none match, or null when either side lacks usable names.

```sql
CASE WHEN has_conflict_linkage AND cardinality(conflicting_npi_name_comparisons) > 0
     THEN any_match(conflicting_npi_name_comparisons, p -> p.shares_name)
END AS conflicting_npis_share_name
```

Any true wins; otherwise a missing comparison leaves null. False requires every peer comparison to be a known mismatch. Without an established conflict, the result is null: not applicable when `has_conflict_linkage = false`, unknown timing when that flag is null. This metric has no `_latest` form.

HealthLink's HCP-reference names have no date alignment. Registry names never fill missing names. A true result can coexist with disagreeing peers.

`conflicting_npi_name_comparisons` retains peer NPIs, names, overlapping days and outcomes for [full manual inspection](../../sql/conflicting_names_debug.sql). Undated comparisons have empty day arrays.

## Real examples

No examples have been executed against this definition yet.

Cases worth contrasting: a conflict whose peer carries a matching name (true), a conflict with known fuzzy disagreement such as different first names on the same surname (false), a conflict where one side lacks usable names (NULL, unknown) and a link without a conflict (NULL, not applicable). Agreement does not identify the correct NPI.

## Statistics by source

No measurements exist yet for this definition. [Statistics SQL](../../sql/statistics/13_conflicting_npis_share_name.sql) reports, per source, conflict links and the shared, disjoint and unknown shares.

Percentages use links with `has_conflict_linkage = true`, not all links. A zero conflict denominator is shown as —. Links without an established conflict are not counted as unknown conflicts.

# Vendor name matches registry name

**Question:** do a vendor-supplied name and a registry name for the same NPI agree under fuzzy comparison? Agreement does not prove they identify the same person.

**Where:** `vendor_name_matches_registry_name` and `vendor_name_matches_registry_name_latest` in `iceberg.jteixeira_ipa.pii__int_<vendor>__metrics`; key: `source`, `link_id` (one source/email/NPI link). Vendors: `healthlink`, `quantummedica`, `medscape`, `endato`, `rocketreach`, `drdb`, `haymarket`. Vendor [name inputs](../00_source_map.md#name-comparison-inputs) join the [registry name pairs](../../models/intermediate/int_npi__names.sql) by trimmed NPI.

## How it is computed

Compare normalized first and last names separately. Both parts must agree:

- First names: exact names, a shared space-separated token, a first-token prefix of at least three characters, overlapping nickname expansions, or allowed edits.
- Last names: equal letters-only forms, a shared space/hyphen-separated token, or allowed edits.
- Allowed edits: at most one when both parts have at least five letters; at most two when both have at least eight. These lengths apply to the compared name parts, not the email.

For each name pair, `fk` and `lk` are the first- and last-name match classes (`none` means disagreement). Missing usable names produce null.

```sql
CASE WHEN source_name_usable AND registry_name_usable
     THEN fk <> 'none' AND lk <> 'none'
END AS vendor_registry_match
```

**All versions.** `vendor_name_matches_registry_name` aggregates comparisons of every distinct vendor name pair across the link's versions with every registry name of the NPI:

```sql
bool_or(vendor_registry_match) AS vendor_name_matches_registry_name
```

Any qualifying pair gives true; usable comparisons without a match give false; all-null comparisons stay unknown. Usability requires one first-name letter and two last-name letters.

**Latest version.** `vendor_name_matches_registry_name_latest` applies the same rule to the name of the link's latest version only (`latest_record_id`, see [observation counts](01_observation_counts.md)). It is null when the link has no single latest version. A link can be true over all versions and false for its latest version when only an earlier vendor name agrees with the registry.

**Limits:** common names, shared tokens and broad nickname mappings can produce false matches. Only this link's vendor names and current readable registry variants contribute; HealthLink uses its separate HCP reference by NPI, so its latest column equals the all-version column. No historical as-of alignment is implied. Endato compares its returned person's name, not the NPI-holder name supplied as input. No score or filtering is applied.

## Stored comparison explanations

Stored core also retains `name_match_evidence`, `vendor_registry_match_classes`, `name_match_evaluated_at` and `name_match_definition_version`. They describe the all-version comparisons. The array keeps distinct comparisons and their component kinds; the class set includes every outcome, including `first_only`, `last_only`, `none` and `unknown`. Exact/nickname/token/edit comparisons make the boolean true. No scoring weights are added. [Stored evidence documentation](../name_match_evidence.md) describes the classes.

## Real examples

No examples have been executed against this definition yet.

Cases worth contrasting:

- **Exact versus fuzzy agreement:** an exact match, a nickname match such as JIM/JAMES, and a first-token prefix match such as HYUN/HYUNSUK, each with an exact last-name match.
- **Permissive edit rule:** MITCHELL/MICHELLE has edit distance two and both have eight letters, so the rule accepts the pair with a matching surname. This is a possible false match, not confirmed shared identity.
- **One matching part is insufficient:** a matching first name with a failing last name gives false.
- **Unknown differs from disagreement:** a missing usable registry name or vendor name gives NULL, rather than false.
- **All versions versus latest:** a link whose earlier version matched and whose latest version does not.

## Statistics by source

No measurements exist yet for this definition. [Statistics SQL](../../sql/statistics/07_vendor_name_matches_registry_name.sql) reports, per source, metric rows (links) and the match, no-match and unknown shares.

Percentages use all links within each source. Categories partition links. Distinct-email outcomes cannot be inferred by adding link counts. Unknown is NULL, not disagreement.

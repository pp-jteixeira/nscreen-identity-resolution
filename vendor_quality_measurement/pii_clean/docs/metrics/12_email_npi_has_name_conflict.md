# Email–NPI name conflict

**Principle:** flag incompatible usable names reported for the same vendor/email/NPI link across all its versions and retained history.

**Where:** `iceberg.jteixeira_ipa.pii__int_<vendor>__metrics` and `iceberg.jteixeira_ipa.pii_clean`. Inputs: `source`, `email`, `npi`, `source_name_values`. Output: nullable boolean `email_npi_has_name_conflict`, one value per link.

## How it is computed

Collect the link's distinct usable names, across all its versions, into `pair_names`. Compare every pair. In this excerpt, `has_disagreeing_pair` means at least one pair fails the fuzzy first/last-name rules below; it is false when there is only one name or all pairs agree.

```sql
CASE WHEN cardinality(pair_names) = 0 THEN NULL
     ELSE has_disagreeing_pair
END AS email_npi_has_name_conflict
```

Both first and last names must agree under [metric 07's fuzzy rules](07_vendor_name_matches_registry_name.md): nicknames, shared tokens, permitted first-name prefixes and small spelling differences. First-name-only agreement is insufficient. Missing/partial names do not create disagreement; registry names never fill missing vendor names.

Every pair is checked: a compound surname cannot hide disagreement between SMITH and JONES. Different names attached only to different NPIs do not create this flag. The separate `has_conflict_linkage` metric checks competing NPIs at the observation time or within current undated vendor data.

HealthLink uses its retained HCP names without date alignment. This metric includes name changes between versions; `attribute_versions` shows when each name was observed. A true result does not establish an incorrect identity. Vendors remain separate.

## Real examples

No examples have been executed against this definition yet.

Cases worth contrasting: a link with several spellings that remain compatible under fuzzy matching (false), a link with an incompatible pair (true), and a link without usable names (NULL, rather than false). Parsing matters: a full name such as RICHARD SALZER JR can yield JR as a last name, so this flag compares parsed name pairs rather than proving that two people share the email.

## Statistics by source

No measurements exist yet for this definition. [Statistics SQL](../../sql/statistics/12_email_npi_has_name_conflict.sql) reports, per source, links, conflicting links and unknown links.

Percentages use the source's links. A missing usable name pair leaves unknown; conflicting spellings do not prove different people.

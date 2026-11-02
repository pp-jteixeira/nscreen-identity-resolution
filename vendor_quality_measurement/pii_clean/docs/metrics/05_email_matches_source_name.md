# Email matches source name

**Question:** does the email's mailbox text resemble a name supplied by this vendor? A match is name evidence, not proof of ownership.

**Where:** `email_matches_source_name` and `email_matches_source_name_latest` in `iceberg.jteixeira_ipa.pii__int_<vendor>__metrics`, keyed by `source`, `link_id` (one source/email/NPI link). Vendors: `healthlink`, `quantummedica`, `medscape`, `endato`, `rocketreach`, `drdb`, `haymarket`. Inputs and name parsing are listed in the [source map](../00_source_map.md#name-comparison-inputs).

## How it is computed

Normalize each paired first/last name: uppercase, supported accents removed, spaces/hyphens/apostrophes retained; empty, `NULL`, `NaN` and `\N` become missing. Expand first names through the [nickname list](../../seeds/nicknames.csv). Reduce the email mailbox to lowercase letters:

```sql
regexp_replace(lower(regexp_extract(email, '^([^@]*)@', 1)), '[^a-z]', '') AS local_letters
```

For each usable name, compute `source_match` using these rules:

- Both first and last names occur anywhere; each needs two letters.
- Or the local part starts with the first initial and ends with the last name, or the reverse. It must be longer than the last name.
- Or a local part of six or more letters differs by at most one insertion, deletion or substitution from first+last, last+first, initial+last or last+initial.

A usable name needs at least one first-name letter and two last-name letters. `source_name_usable` records availability.

**All versions.** A link can merge several source record versions with different names. `email_matches_source_name` compares the email with every distinct vendor name pair across the link's versions: any matching name gives true; usable names with no match give false; no usable name leaves unknown.

```sql
bool_or(source_match) AS email_matches_source_name
```

**Latest version.** `email_matches_source_name_latest` applies the same rule to the name of the link's latest version only (`latest_record_id`, see [observation counts](01_observation_counts.md)). It is null when the link has no single latest version. Comparing the two columns shows whether the current vendor name still supports the email.

Names stay paired within their version. HealthLink alone attaches distinct HCP-reference names by NPI across retained history, without date alignment; its latest column therefore equals the all-version column. Repeated observations add no weight. `source_name_values` lists the usable names across all versions.

Format validation is separate. RocketReach and DRDB full-name parsing can mistake titles or suffixes for name parts.

## Real examples

No examples have been executed against this definition yet.

Cases worth contrasting: a mailbox accepted by the initial/surname rule (for example `gtarbour` against a name starting with G and ending with ARBOUR), a usable nonmatching name (false), an empty vendor-name array (NULL), and a link whose versions carry different names so that the all-version and latest columns differ. Registry evidence never fills a missing vendor name, and mailbox resemblance does not prove ownership.

## Statistics by source

No measurements exist yet for this definition. [Statistics SQL](../../sql/statistics/05_email_matches_source_name.sql) reports, per source, metric rows (links) and the match, no-match and unknown shares.

Percentages use all links within each source. Categories partition links. Distinct-email outcomes cannot be inferred by adding link counts. Unknown is NULL, not disagreement.

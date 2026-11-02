# Email matches registry name

**Question:** does the email's mailbox text resemble a name recorded for its NPI? This does not establish mailbox ownership or validate the vendor attribution.

**Where:** `email_matches_registry_name` in `iceberg.jteixeira_ipa.pii__int_<vendor>__metrics`; key: `source`, `link_id` (one source/email/NPI link). Vendors: `healthlink`, `quantummedica`, `medscape`, `endato`, `rocketreach`, `drdb`, `haymarket`.

**Inputs and join:** cleaned `email` and `npi`; `iceberg.npi.npi_reference.npi`, `first_name`, `last_name`. The [registry model](../../models/intermediate/int_npi__names.sql) retains distinct normalized name pairs per trimmed NPI. The join is left-sided and uses NPI only. Unmatched links remain; duplicate reference names cannot multiply links or observation counts.

## How it is computed

After the NPI join, apply the [email-to-name rules](05_email_matches_source_name.md#email-matches-source-name) to each registry name: first/last text, initials, nickname variants, then the one-edit rule. A usable name has at least one first-name letter and two last-name letters. Each comparison produces `registry_match`. Within `source`, `link_id`, keep any true result; all false gives false, and all null stays unknown:

```sql
bool_or(registry_match) AS email_matches_registry_name
```

Both inputs, the email and the NPI, are fixed for a link, so the result is the same for every version and this metric has no `_latest` form.

`registry_npi_present` distinguishes an absent NPI from an existing NPI with unusable names. `registry_name_usable` records whether comparison is possible. Reference presence does not establish NPI validity or active status.

**Limits:** all readable registry name variants contribute, regardless of `last_update_date` or deactivation. This is not an as-of join: a historical vendor link can match a name recorded later. The same email can match multiple NPIs sharing names or initials.

## Real examples

No examples have been executed against this definition yet.

Cases worth contrasting: a link whose vendor supplied no usable name (NULL source-name match) but whose registry name matches, a usable registry name without mailbox agreement (false), and an NPI absent from the registry (NULL). The one-edit fallback is permissive: `austin` differs from initial-plus-surname `maustin` by one deletion, so surname-only mailboxes can match. The registry flag aggregates all usable reference variants; displayed names are inspection evidence.

## Statistics by source

No measurements exist yet for this definition. [Statistics SQL](../../sql/statistics/06_email_matches_registry_name.sql) reports, per source, metric rows (links) and the match, no-match and unknown shares.

Percentages use all links within each source. Categories partition links. Distinct-email outcomes cannot be inferred by adding link counts. Unknown is NULL, not disagreement.

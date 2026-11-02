# Email–NPI multiplicity

**Principle:** count how many distinct reported NPIs one vendor associates with an email across its retained history.

**Where:** `iceberg.jteixeira_ipa.pii__int_<vendor>__metrics` and `iceberg.jteixeira_ipa.pii_clean`. Inputs: `source`, cleaned `email`, trimmed `npi`. Outputs: `email_npi_count` and `email_has_multiple_npis`.

## How it is computed

Group retained links by `source`, `email` and count different nonempty, trimmed NPIs. Then flag counts above one:

```sql
count(DISTINCT npi) AS email_npi_count
```

```sql
email_npi_count > 1 AS email_has_multiple_npis
```

Every link for the same vendor/email receives the same count. Each link is one email–NPI pair, so the count equals the email's number of links within the vendor. Vendors are never pooled. DRDB's two inputs belong to one vendor. Versions, duplicate email slots and repeated dates cannot increase the distinct-NPI count. Missing email/NPI keys remain in staging; malformed nonempty NPIs still count because validity is a separate question.

Multiplicity does not distinguish historical changes from same-day conflicts or establish ownership. See [reassignment](09_has_been_reassigned.md) and [conflict](10_has_conflict_linkage.md).

## Real examples

No examples have been executed against this definition yet.

Cases worth contrasting: a dated email whose two NPIs follow each other without overlap (reassigned, no conflict), an undated email with two competing NPIs (conflict, unknown reassignment), and an email with a single NPI. Multiplicity alone cannot distinguish these situations.

## Statistics by source

No measurements exist yet for this definition. [Statistics SQL](../../sql/statistics/08_email_npi_multiplicity.sql) reports, per source, distinct emails, emails with multiple NPIs, affected links and the maximum NPIs per email.

Email percentages use distinct emails within each source. Affected-link percentages use that source's links. Multiplicity does not identify overlap timing or ownership.

# Email format

**Question:** does the email match the format pattern below? A match does not prove that a mailbox exists, receives mail, or belongs to the NPI holder.

**Where:** source views `iceberg.jteixeira_ipa.pii__int_<vendor>__metrics`, column `email_format_valid`. Input: `email`; key: `source`, `link_id` (one source/email/NPI link). Emails are lowercased and trimmed before this check.

## How it is computed

Trim and lowercase the vendor email value; convert blanks to null. Then test the cleaned `email` against the format pattern:

```sql
-- Cleaning step. raw_email represents the vendor's email field or slot.
lower(nullif(trim(cast(raw_email AS varchar)), '')) AS email
```

```sql
regexp_like(email, '^[a-z0-9._%+-]+@[a-z0-9.-]+[.][a-z]{2,}$') AS email_format_valid
```

A match gives true, a non-match false, and a null input null. Metric views exclude blank/null email keys. The result depends only on the link's cleaned email, so all versions of a link share it.

This rule can reject legitimate formats and accept malformed-looking ones. It does not test domain or mailbox existence. Role accounts and test addresses are not excluded by this flag. This indicator does not filter rows or assign scores.

## Real examples

No examples have been executed against this definition yet.

Cases worth contrasting: a conventional address (true), an address without `@` (false) and an address with repeated dots in the domain, which this permissive pattern still accepts. Format agreement does not establish a real domain or mailbox.

## Statistics by source

No measurements exist yet for this definition. [Statistics SQL](../../sql/statistics/02_email_format_valid.sql) reports, per source, metric rows (links) and invalid links.

Percentages use all links within each source. An email linked to several NPIs counts once per link. This indicator does not remove links.

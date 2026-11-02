# Role accounts

**Question:** does this email use a potentially shared mailbox name? A match does not prove shared ownership or incorrect attribution.

**Where:** column `email_role_account` in each source view `iceberg.jteixeira_ipa.pii__int_<vendor>__metrics`. Substitute `healthlink`, `quantummedica`, `medscape`, `endato`, `rocketreach`, `drdb` or `haymarket`. Input: cleaned `email`; row key: `source`, `link_id` (one source/email/NPI link).

## How it is computed

From the trimmed, lowercase email, extract the mailbox before `@` and compare it with the exact role-name list. Suffixes and plus tags remain part of the mailbox, so they do not match.

```sql
coalesce(regexp_extract(email, '^([^@]+)@', 1) IN (
    'admin', 'info', 'office', 'contact', 'frontdesk', 'billing',
    'reception', 'appointments', 'scheduling', 'support', 'noreply'
), false) AS email_role_account
```

**Limits:** false means outside this list, not confirmed personal ownership. Missing emails return false; metric views exclude empty email/NPI keys. The result depends only on the link's email. Format validity is separate. No filtering or scoring.

## Real examples

No examples have been executed against this definition yet.

Cases worth contrasting: an exact role mailbox such as `info@` (true) and a role word with added punctuation or a suffix, such as `office.oa@` (false, because the mailbox text is outside the exact list). A false flag does not prove personal ownership; format validity remains separate.

## Statistics by source

No measurements exist yet for this definition. [Statistics SQL](../../sql/statistics/03_email_role_account.sql) reports, per source, metric rows (links) and flagged links.

Percentages use all links within each source. An email linked to several NPIs counts once per link. This indicator does not remove links.

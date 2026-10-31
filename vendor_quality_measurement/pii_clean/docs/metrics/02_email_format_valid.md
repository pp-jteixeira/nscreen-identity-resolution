# Email format

**Question:** does the email match the format pattern below? A match does not prove that a mailbox exists, receives mail, or belongs to the NPI holder.

**Where:** source views `iceberg.jteixeira_ipa.pii__int_<vendor>__metrics`, column `email_format_valid`. Input: `email`; key: `source`, `metric_row_id`. Emails are lowercased and trimmed before this check.

## How it is computed

Trim and lowercase the vendor email value; convert blanks to null. Then test the cleaned `email` against the format pattern:

```sql
-- Cleaning step; raw_email represents the vendor's email field or slot.
lower(nullif(trim(cast(raw_email AS varchar)), '')) AS email
```

```sql
regexp_like(email, '^[a-z0-9._%+-]+@[a-z0-9.-]+[.][a-z]{2,}$') AS email_format_valid
```

A match gives true, a non-match false, and a null input null. Metric views exclude blank/null email keys.

This rule can reject legitimate formats and accept malformed-looking ones. It does not test domain or mailbox existence. Role accounts and test addresses are not excluded by this flag. This indicator does not filter rows or assign scores.

## Real examples

Executed October 31, 2026, against canonical snapshot `8811920360682490090`. These selected cases explain outcomes; they do not measure prevalence.

[Executed example SQL](../../sql/examples/02_email_format_valid.sql):

```sql
WITH selected AS (
    SELECT *
    FROM iceberg.jteixeira_ipa.pii_clean FOR VERSION AS OF 8811920360682490090
    WHERE (source = 'endato' AND metric_row_id IN (
        'E2D7F6ECD9E1A822A2486BDE5556AAAC8D2BCA39374213AEE006E8C9B5AADE31'))
       OR (source = 'medscape' AND metric_row_id IN (
        '1DB726D2A317E497F5864411FDC282F4EA7A5D2125946A98BD145F6BDF457BF7',
        '75941F2B89381BA06B01E0E4ADE6298599723535231BA3603A1C420DEB763599'))
)
SELECT m.source,
       m.email,
       m.email_format_valid
FROM selected m
ORDER BY m.source, m.metric_row_id
```

| source | email | email_format_valid |
|---|---|---|
| endato | chris.peetz@gmail.com | true |
| medscape | pmoyer@pol..net | true |
| medscape | obrusilnurldiognosticconsultants.com | false |

**What differentiates these cases:** The address without `@` fails. Repeated dots can still pass this regex, demonstrating its permissiveness. Format agreement does not establish a real domain or mailbox. Blank email keys are excluded upstream.

## Statistics by source

Measured **October 31, 2026** from `iceberg.jteixeira_ipa.pii_clean` snapshot `8811920360682490090`. These are exact published-population counts across retained eligible history, not a sample. Stored evaluation dates remain unchanged.

[Executed statistics SQL](../../sql/statistics/02_email_format_valid.sql)

| Source | Metric records | Invalid records, n (%) |
|---|---|---|
| HealthLink | 11,156,016 | 503 (0.004509%) |
| QuantumMedica | 1,705,723 | 528 (0.030955%) |
| Medscape | 47,164,366 | 13,456 (0.028530%) |
| Endato | 5,427,459 | 358 (0.006596%) |
| RocketReach | 4,864,145 | 212 (0.004358%) |
| DRDB | 1,115,415 | 1,317 (0.118073%) |
| Haymarket | 4,223,245 | 225 (0.005328%) |

Percentages use all metric records within each source. Repeated records can count one email multiple times. This indicator does not remove records.

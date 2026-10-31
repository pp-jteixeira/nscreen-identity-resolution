# Role accounts

**Question:** does this email use a potentially shared mailbox name? A match does not prove shared ownership or incorrect attribution.

**Where:** column `email_role_account` in each source view `iceberg.jteixeira_ipa.pii__int_<vendor>__metrics`. Substitute `healthlink`, `quantummedica`, `medscape`, `endato`, `rocketreach`, `drdb` or `haymarket`. Input: cleaned `email`; row key: `source`, `metric_row_id`.

## How it is computed

From the trimmed, lowercase email, extract the mailbox before `@` and compare it with the exact role-name list. Suffixes and plus tags remain part of the mailbox, so they do not match.

```sql
coalesce(regexp_extract(email, '^([^@]+)@', 1) IN (
    'admin', 'info', 'office', 'contact', 'frontdesk', 'billing',
    'reception', 'appointments', 'scheduling', 'support', 'noreply'
), false) AS email_role_account
```

**Limits:** false means outside this list, not confirmed personal ownership. Missing emails return false; metric views exclude empty email/NPI keys. Format validity is separate. No filtering or scoring.

## Real examples

Executed October 31, 2026, against canonical snapshot `8811920360682490090`. These selected cases explain outcomes; they do not measure prevalence.

[Executed example SQL](../../sql/examples/03_email_role_account.sql):

```sql
WITH selected AS (
    SELECT *
    FROM iceberg.jteixeira_ipa.pii_clean FOR VERSION AS OF 8811920360682490090
    WHERE (source = 'endato' AND metric_row_id IN (
        'AA0491CD7AC32FC75FFE7748AA65628DEF3A37C570A2B2BF2D7AF4AABD426BDE'))
       OR (source = 'medscape' AND metric_row_id IN (
        'AB540EC836F806841DCEAF1D2D7CA8466CC6C031BD90119941498B57FA3E5872'))
)
SELECT m.source,
       m.email,
       m.email_role_account,
       m.email_format_valid
FROM selected m
ORDER BY m.source, m.metric_row_id
```

| source | email | email_role_account | email_format_valid |
|---|---|---|---|
| endato | info@jahantel.com | true | true |
| medscape | office.oa@midconetwork.com | false | true |

**What differentiates these cases:** An exact role mailbox matches. Adding punctuation or a suffix changes the mailbox text and leaves it outside the exact list. A false flag does not prove personal ownership; format validity remains separate.

## Statistics by source

Measured **October 31, 2026** from `iceberg.jteixeira_ipa.pii_clean` snapshot `8811920360682490090`. These are exact published-population counts across retained eligible history, not a sample. Stored evaluation dates remain unchanged.

[Executed statistics SQL](../../sql/statistics/03_email_role_account.sql)

| Source | Metric records | Flagged records, n (%) |
|---|---|---|
| HealthLink | 11,156,016 | 44 (0.000394%) |
| QuantumMedica | 1,705,723 | 622 (0.036465%) |
| Medscape | 47,164,366 | 23,813 (0.050489%) |
| Endato | 5,427,459 | 2,253 (0.041511%) |
| RocketReach | 4,864,145 | 109 (0.002241%) |
| DRDB | 1,115,415 | 2,658 (0.238297%) |
| Haymarket | 4,223,245 | 2,294 (0.054318%) |

Percentages use all metric records within each source. Repeated records can count one email multiple times. This indicator does not remove records.

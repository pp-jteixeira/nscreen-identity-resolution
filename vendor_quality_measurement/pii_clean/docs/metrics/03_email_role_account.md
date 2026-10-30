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

## Real examples: contrasting outcomes

Selected real records, queried October 30, 2026, from `iceberg.jteixeira_ipa.pii_clean` at snapshot `8096642935433856886`. These examples explain outcomes; they are not prevalence estimates. Only the mailbox before `@` is shown; domains are omitted.

[Runnable example SQL](../../sql/examples/03_email_role_account.sql):

```sql
WITH selected AS (
    SELECT *
    FROM iceberg.jteixeira_ipa.pii_clean FOR VERSION AS OF 8096642935433856886
    WHERE (source = 'endato' AND metric_row_id IN (
        'AA0491CD7AC32FC75FFE7748AA65628DEF3A37C570A2B2BF2D7AF4AABD426BDE'))
       OR (source = 'medscape' AND metric_row_id IN (
        'AB540EC836F806841DCEAF1D2D7CA8466CC6C031BD90119941498B57FA3E5872'))
)
SELECT m.source,
       split_part(m.email, '@', 1) AS mailbox,
       m.email_role_account,
       m.email_format_valid
FROM selected m
ORDER BY m.source, m.metric_row_id
```

**Result:** 2 rows.

| source | mailbox | email_role_account | email_format_valid |
|---|---|---|---|
| endato | info | true | true |
| medscape | office.oa | false | true |

**What differentiates these cases:** An exact role mailbox matches. Adding punctuation or a suffix changes the mailbox text and leaves it outside the exact list. A false flag does not prove personal ownership; format validity remains separate.

Stored indicators are unchanged by display helpers. Reproduction requires the pinned snapshot to remain available.

## Statistics by source

[Statistics SQL](../../sql/statistics/03_email_role_account.sql). This standalone read-only equivalent calculates the displayed row counts and percentages from the published table. The saved October 29 tables were derived from the linked grouped-population extraction; this equivalent has been checked locally, not executed against Trino.

Measured October 29, 2026, on `iceberg.jteixeira_ipa.pii_clean` at exact source-record/email-position grain. Percentages use all metric rows within each vendor. Counts are exact and cover all retained history; email–NPI links remain undeduplicated. These are saved measurements, not live counts.

| Source | Metric rows | Flagged rows, n (%) |
|---|---:|---:|
| HealthLink | 11,156,016 | 44 (0.00039%) |
| QuantumMedica | 1,705,723 | 622 (0.03647%) |
| Medscape | 47,072,262 | 23,761 (0.05048%) |
| Endato | 5,427,459 | 2,253 (0.04151%) |
| RocketReach | 4,864,145 | 109 (0.00224%) |
| DRDB | 1,115,415 | 2,658 (0.23830%) |
| Haymarket | 4,223,245 | 2,294 (0.05432%) |

Flagged means `email_role_account = true`. Repeated records and email positions can count the same email more than once. Distinct-email counts are not reconstructed by summing grouped distinct counts, because groups can overlap.

Derived row statistics (historical output, not retained: `../../results/documentation_row_statistics.json`) · [Executed population SQL](../../results/metric_population_20261029/grouped.sql) · Measurement metadata (historical output, not retained: `../../results/metric_population_20261029/analysis_metadata.json`) · Published-table validation (historical output, not retained: `../../results/final_build.json`)

[Profile SQL](../../sql/email_role_profile.sql) · [Rule SQL](../../macros/email_role_account.sql)

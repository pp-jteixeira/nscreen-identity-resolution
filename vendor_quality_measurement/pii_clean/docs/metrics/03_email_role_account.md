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

Executed November 2, 2026, against `iceberg.jteixeira_ipa.pii_clean` snapshot `2837737034249693554`. These selected cases explain outcomes; they do not measure prevalence.

```sql
SELECT source,
       email,
       npi,
       email_role_account
FROM iceberg.jteixeira_ipa.pii_clean FOR VERSION AS OF 2837737034249693554
WHERE (source = 'drdb' AND link_id IN (
        '000FD3D7339BD6795D199248BABD21AC33B16C71D09C90709D9A9E05104AA7F2',
        '0389220BB2B4B4BF9BAC84AA3FF83E0C86DE0BDD1C01B44696E4114C13259D5B'))
   OR (source = 'healthlink' AND link_id IN (
        '03EA387A669581741A0FBECCF42FE88D588AE803BFCB3B3BE0137999B60FE0FF',
        '01596A51E2EE2310348171C7A88D6AC394037DFCC32D7310A886206E6804CC14'))
   OR (source = 'medscape' AND link_id IN (
        '00121166A8D8808711A466C74E5B7A9392883425403541F7AC1135830A769E41',
        '00C5708BA2F64F65710C53020A6DE829DD7E3F6A50AEDB5D77F172EC76235545'))
ORDER BY source, email, npi
```

| source | email | npi | email_role_account |
|---|---|---|---|
| drdb | billing28301@nc.rr.com | 1619003852 | false |
| drdb | reception@smilesbychang.com | 1104989615 | true |
| healthlink | officenursefl@gmail.com | 1033143912 | false |
| healthlink | scheduling@w2ortho.com | 1477977486 | true |
| medscape | office@jmartinmdpc.com | 1366547002 | true |
| medscape | officemanager@mtwnheart.com | 1568529006 | false |

**What differentiates these cases:** `reception@`, `scheduling@` and `office@` are exact role mailboxes, so they are flagged. `billing28301@`, `officenursefl@` and `officemanager@` contain a role word but carry digits or additional text, so the mailbox is outside the exact list and the flag is false. A false flag does not prove personal ownership. Format validity remains separate.

## Statistics by source

Measured **November 2, 2026** from `iceberg.jteixeira_ipa.pii_clean` snapshot `2837737034249693554`. These are exact published-population counts across retained eligible history, not a sample.

Source data period (first to last observed day): HealthLink 2026-01-07 to 2026-10-03; QuantumMedica 2025-09-14 to 2026-10-15; Medscape 2024-01-10 to 2026-11-01; Haymarket 2021-07-06 (a single day). Endato, RocketReach and DRDB are undated.

[Statistics SQL](../../sql/statistics/03_email_role_account.sql) reports, per source, links and flagged links.

| Source | Links | Role-account links, n (%) |
|---|---:|---:|
| HealthLink | 7,688,451 | 37 (0.000481%) |
| QuantumMedica | 1,705,723 | 622 (0.036465%) |
| Medscape | 3,661,537 | 2,602 (0.071063%) |
| Endato | 5,427,459 | 2,253 (0.041511%) |
| RocketReach | 3,199,535 | 100 (0.003125%) |
| DRDB | 826,886 | 1,875 (0.226754%) |
| Haymarket | 4,223,245 | 2,294 (0.054318%) |

Percentages use all links within each source. An email linked to several NPIs counts once per link. This indicator does not remove links.

Exact role mailboxes are rare in every source. DRDB has the highest share (0.2268%), followed by Medscape (0.0711%) and Haymarket (0.0543%). HealthLink has 37 flagged links (0.0005%), the lowest share.

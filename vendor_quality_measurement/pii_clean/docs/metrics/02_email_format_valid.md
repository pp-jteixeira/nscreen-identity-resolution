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

Executed November 2, 2026, against `iceberg.jteixeira_ipa.pii_clean` snapshot `2837737034249693554`. These selected cases explain outcomes; they do not measure prevalence.

```sql
SELECT source,
       email,
       npi,
       email_format_valid
FROM iceberg.jteixeira_ipa.pii_clean FOR VERSION AS OF 2837737034249693554
WHERE (source = 'healthlink' AND link_id IN (
        '000003E1464D72618D55F78C6D464B854F2B8213906F0546468EE5C189A1376A'))
   OR (source = 'medscape' AND link_id IN (
        '0294ECEC72913C0A6B1D4BE62E26B0A4988BC2CE0055CBA0DA0F7753AA432EF3',
        '00B591EA1F1EBE58D013ED2D3CE15670C48EF1C905F79984EC94173D49F52497'))
   OR (source = 'drdb' AND link_id IN (
        '0329091836A2527C77EDBB7997A87217ED1F2CDEC45F02EC8BA6D3317D91DA68'))
   OR (source = 'quantummedica' AND link_id IN (
        '5EA70FE29098FF018E738CB9D27794B2458B5211B0799BBCE987FB03AED9CCCB'))
ORDER BY source, email, npi
```

| source | email | npi | email_format_valid |
|---|---|---|---|
| drdb | http://secure.eyehub.com/secure/index.cfm?fuseaction=site.appointments&domain=visionsource-emeraldcoasteyecare.com | 1265668842 | false |
| healthlink | csteele@hotmail.com | 1720286941 | true |
| medscape | jpwlswemw@aol..com | 1578541421 | true |
| medscape | ny | 1669559613 | false |
| quantummedica | email | npi | false |

**What differentiates these cases:** A conventional address passes. The Medscape address `jpwlswemw@aol..com` also passes although its domain contains repeated dots, which shows the permissiveness of the pattern. The other four values fail because they lack the `@name.tld` shape: Medscape `ny`, a DRDB web address, and a QuantumMedica link whose stored email is the literal text `email` (with `npi` as its NPI value). Format agreement does not establish a real domain or mailbox. Blank email keys are excluded upstream.

## Statistics by source

Measured **November 2, 2026** from `iceberg.jteixeira_ipa.pii_clean` snapshot `2837737034249693554`. These are exact published-population counts across retained eligible history, not a sample.

Source data period (first to last observed day): HealthLink 2026-01-07 to 2026-10-03; QuantumMedica 2025-09-14 to 2026-10-15; Medscape 2024-01-10 to 2026-11-01; Haymarket 2021-07-06 (a single day). Endato, RocketReach and DRDB are undated.

[Statistics SQL](../../sql/statistics/02_email_format_valid.sql) reports, per source, links and invalid links.

| Source | Links | Invalid links, n (%) |
|---|---:|---:|
| HealthLink | 7,688,451 | 372 (0.004838%) |
| QuantumMedica | 1,705,723 | 528 (0.030955%) |
| Medscape | 3,661,537 | 1,496 (0.040857%) |
| Endato | 5,427,459 | 358 (0.006596%) |
| RocketReach | 3,199,535 | 212 (0.006626%) |
| DRDB | 826,886 | 1,163 (0.140648%) |
| Haymarket | 4,223,245 | 225 (0.005328%) |

Percentages use all links within each source. An email linked to several NPIs counts once per link. This indicator does not remove links.

Every source has fewer than 0.15% invalid links. DRDB has the highest share (0.1406%, 1,163 links) and HealthLink the lowest (0.0048%). Medscape has the largest count of invalid links after DRDB (1,496).

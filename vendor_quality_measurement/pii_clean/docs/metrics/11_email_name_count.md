# Email name count

**Principle:** count distinct usable normalized first/last-name pairs reported for an email within one vendor, across all retained history. This counts name spellings, not people.

**Where:** `iceberg.jteixeira_ipa.pii__int_<vendor>__metrics` and `iceberg.jteixeira_ipa.pii_clean`. Inputs: `source`, `email`, `source_name_values`; output: bigint `email_name_count`. Every link for the same vendor/email receives the same count, across all its NPIs.

## How it is computed

Each link's `source_name_values` already holds the usable names of all its versions. Combine them across each vendor/email into `email_names`, including all its NPIs. Remove repeated first/last-name pairs and count the remaining spellings:

```sql
cast(cardinality(array_distinct(transform(email_names,
    n -> ROW(n.first_name, n.last_name)))) AS bigint) AS email_name_count
```

Names use the existing uppercase, accent and whitespace normalization. A usable pair has at least one first-name letter and two last-name letters. Missing, partial and punctuation-only names do not contribute. Zero means no usable names were observed. Versions, email slots, dates and registry-name matches cannot inflate the count.

HealthLink uses its HCP-name reference by NPI across retained HCP history, without date alignment. Other vendors use the names of every version of each link; both DRDB feeds contribute. Registry names do not fill missing vendor names. `source_name_values` retains each link's normalized pairs and first-name variants for inspection.

## Real examples

Executed November 2, 2026, against `iceberg.jteixeira_ipa.pii_clean` snapshot `2837737034249693554`. These selected cases explain outcomes; they do not measure prevalence.

```sql
SELECT source, email, npi, email_name_count,
       transform(source_name_values, n -> n.first_name || ' ' || n.last_name) AS link_names,
       email_npi_count, record_count
FROM iceberg.jteixeira_ipa.pii_clean
WHERE (source = 'medscape' AND link_id IN ('001B3FAFCB6C15A16FE008A248CDAA336337B490832693299EB9C7A35BA856C2', '000079952FA31C8C7313E567F6212C3370FD86580B7D34D7A11477881D36A574'))
   OR (source = 'endato' AND link_id IN ('0001AD8FDD1A0D74815ABCB405188FF07C832BEB35497658C038CBE3CDD9D023', '6E08CC6FDFC7C2E346A8D6190692ED9037A039DDB46F0C7D40AE70FA1D521C03'))
   OR (source = 'healthlink' AND link_id IN ('000003E1464D72618D55F78C6D464B854F2B8213906F0546468EE5C189A1376A'))
   OR (source = 'haymarket' AND link_id IN ('00002F95A062B49A66DC511705A527F648D6B7EBDCD336743F84F8280A853434'))
   OR (source = 'quantummedica' AND link_id IN ('5EA70FE29098FF018E738CB9D27794B2458B5211B0799BBCE987FB03AED9CCCB'))
ORDER BY source, email, npi
```

| source | email | npi | email_name_count | link_names | email_npi_count | record_count |
|---|---|---|---|---|---|---|
| endato | cpd13461@hotmail.com | 1063461606 | 2 | ['JOSEPH WILNISE'] | 2 | 1 |
| endato | cpd13461@hotmail.com | 1528328184 | 2 | ['PAUL HEYDEN'] | 2 | 1 |
| haymarket | liliane.vaal@bwmc.umms.org | 1225097603 | 0 | [] | 1 | 1 |
| healthlink | csteele@hotmail.com | 1720286941 | 1 | ['CHARLOTTE STEELE'] | 1 | 3 |
| medscape | drkotesh@hotmail.com | 1164600235 | 0 | [] | 1 | 1 |
| medscape | nowsayahhh@aol.com | 1255415253 | 2 | ['LINDA ALVAREZ-THULL', 'LINDA THULL'] | 1 | 2 |
| quantummedica | email | npi | 1 | ['FIRSTNAME LASTNAME'] | 1 | 1 |

**What differentiates these cases:**

- **Names from different NPIs:** the Endato email `cpd13461@hotmail.com` has two links. One reports PAUL HEYDEN and the other JOSEPH WILNISE, so both links receive `email_name_count` 2 although each link has one name.
- **Spellings of one NPI:** the Medscape link for `nowsayahhh@aol.com` reports LINDA ALVAREZ-THULL and LINDA THULL across its 2 versions, so the count is 2. This counts spellings, not people.
- **Versions do not inflate the count:** the HealthLink link for `csteele@hotmail.com` merges 3 versions that all report CHARLOTTE STEELE, so the count is 1.
- **No usable names:** the Haymarket link and the Medscape link for `drkotesh@hotmail.com` have empty name arrays, so the count is 0. Registry names do not fill this gap.
- **Placeholder text:** the only QuantumMedica link with a usable name has the email value `email`, the NPI value `npi` and the name FIRSTNAME LASTNAME. Every other QuantumMedica link has count 0.

## Statistics by source

Measured **November 2, 2026** from `iceberg.jteixeira_ipa.pii_clean` snapshot `2837737034249693554`. These are exact published-population counts across retained eligible history, not a sample. Source data period (first to last observed day): HealthLink 2026-01-07 to 2026-10-03, QuantumMedica 2025-09-14 to 2026-10-15, Medscape 2024-01-10 to 2026-11-01 and Haymarket 2021-07-06 (a single day). Endato, RocketReach and DRDB are undated.

[Statistics SQL](../../sql/statistics/11_email_name_count.sql)

| Source | Distinct emails | Zero names: emails, n (%) | One name | Two names | Three names | Four or more | Multiple names: emails, n (%) | Maximum names per email | Links in multiple-name emails, n (%) |
|---|---|---|---|---|---|---|---|---|---|
| HealthLink | 7,688,331 | 515 (0.006698%) | 7,687,651 | 165 | 0 | 0 | 165 (0.002146%) | 2 | 257 (0.003343%) |
| QuantumMedica | 1,705,695 | 1,705,694 (99.999941%) | 1 | 0 | 0 | 0 | 0 (0.000000%) | 1 | 0 (0.000000%) |
| Medscape | 3,551,989 | 44,685 (1.258028%) | 3,503,127 | 4,143 | 31 | 3 | 4,177 (0.117596%) | 6 | 4,725 (0.129044%) |
| Endato | 5,324,318 | 215 (0.004038%) | 5,296,089 | 27,244 | 466 | 304 | 28,014 (0.526152%) | 2,155 | 66,200 (1.219724%) |
| RocketReach | 3,163,679 | 1,908 (0.060310%) | 3,140,495 | 18,295 | 1,828 | 1,153 | 21,276 (0.672508%) | 24 | 48,322 (1.510282%) |
| DRDB | 819,454 | 56 (0.006834%) | 806,022 | 13,250 | 126 | 0 | 13,376 (1.632306%) | 3 | 15,462 (1.869907%) |
| Haymarket | 4,223,245 | 191,914 (4.544231%) | 4,031,331 | 0 | 0 | 0 | 0 (0.000000%) | 1 | 0 (0.000000%) |

Percentages use distinct source/emails, except the last column, which uses the source's links. Multiple means at least two normalized spellings, not two verified people. Zero usable names is an observed lack of vendor evidence.

QuantumMedica has no usable vendor names: 1,705,694 of its 1,705,695 emails have count 0, and the remaining one is the placeholder row shown above. Haymarket has no usable name for 191,914 emails (4.544231%) and never more than one. Endato and RocketReach carry one name per link, so their multiple-name emails come from several NPIs sharing an email; Endato has an email with 2,155 names and RocketReach one with 24. DRDB has the highest share of multiple-name emails among sources with names per link (1.632306%), and HealthLink the lowest (0.002146%).

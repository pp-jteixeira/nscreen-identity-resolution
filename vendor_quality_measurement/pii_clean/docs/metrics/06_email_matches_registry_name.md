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

Executed November 2, 2026, against `iceberg.jteixeira_ipa.pii_clean` snapshot `2837737034249693554`. These selected cases explain outcomes; they do not measure prevalence. Registry names come from the current readable name view; the stored indicators come from the pinned snapshot.

```sql
SELECT m.source,
       m.email,
       m.npi,
       r.registry_names,
       m.registry_npi_present,
       m.registry_name_usable,
       m.email_matches_source_name,
       m.email_matches_registry_name
FROM iceberg.jteixeira_ipa.pii_clean FOR VERSION AS OF 2837737034249693554 m
LEFT JOIN (SELECT npi, array_join(array_agg(first_name || ' ' || last_name ORDER BY first_name, last_name), ' / ') AS registry_names FROM iceberg.jteixeira_ipa.pii__int_npi__names GROUP BY npi) r ON m.npi = r.npi
WHERE (source = 'quantummedica' AND link_id IN (
        '00000BA286ADECF777EA438FAA70261EEA429A67DBD4E6C1A467307C957CEE9A'))
   OR (source = 'healthlink' AND link_id IN (
        '000003E1464D72618D55F78C6D464B854F2B8213906F0546468EE5C189A1376A',
        '0000734A2570E79F4EA5699809A46672FA8C95FCF021875C8A269185CB474986'))
   OR (source = 'endato' AND link_id IN (
        '00000359411756A423CF6FA62F7ADEA5FAF7F0213AB36334DF4DE1CD16782DF9',
        '00065EC76B50D0617B4D5317E5FE902D1DA9B6C36AEF41DD481F40A624E52E45',
        '002BFBA3EE1E118F9AE4EDEF4804651DA35F7C09D5B232F07DB7FED088B98E3E'))
ORDER BY m.source, m.email
```

| source | email | npi | registry_names | registry_npi_present | registry_name_usable | email_matches_source_name | email_matches_registry_name |
|---|---|---|---|---|---|---|---|
| endato | hhutch2@gmail.com | 1922407774 | HOLLY HUTCHINSON | true | true | false | false |
| endato | sivabudh@gmail.com | 1023040839 |  | true | false | false | NULL |
| endato | sonia_zavala@aya.yale.edu | 1740365550 | NULL | false | false | false | NULL |
| healthlink | csteele@hotmail.com | 1720286941 | CHARLOTTE STEELE | true | true | true | true |
| healthlink | melbecker777@gmail.com | 1891942769 | MELISSA VERTIN | true | true | true | false |
| quantummedica | angiescanales@yahoo.com | 1942511381 | ANGELA CANALES | true | true | NULL | true |

**What differentiates these cases:** Registry resemblance can be true when the vendor supplied no usable name: the QuantumMedica link has a NULL source-name match but a true registry match (`angiescanales` against ANGELA CANALES). `csteele@hotmail.com` matches both. `melbecker777@gmail.com` matches the vendor's name but not the registry name MELISSA VERTIN, and `hhutch2@gmail.com` matches neither. A usable registry name without mailbox agreement gives false. An NPI absent from the registry (`registry_npi_present` false) leaves NULL, and so does an NPI whose registry entry has no usable name. The one-edit fallback is permissive, so surname-only mailboxes can match. The registry flag aggregates all usable reference variants; displayed names are inspection evidence.

## Statistics by source

Measured **November 2, 2026** from `iceberg.jteixeira_ipa.pii_clean` snapshot `2837737034249693554`. These are exact published-population counts across retained eligible history, not a sample.

Source data period (first to last observed day): HealthLink 2026-01-07 to 2026-10-03; QuantumMedica 2025-09-14 to 2026-10-15; Medscape 2024-01-10 to 2026-11-01; Haymarket 2021-07-06 (a single day). Endato, RocketReach and DRDB are undated.

[Statistics SQL](../../sql/statistics/06_email_matches_registry_name.sql) reports, per source, links and the match, no-match and unknown counts.

| Source | Links | Match, n (%) | No match, n (%) | Unknown, n (%) |
|---|---:|---:|---:|---:|
| HealthLink | 7,688,451 | 5,140,636 (66.861790%) | 2,498,748 (32.500019%) | 49,067 (0.638191%) |
| QuantumMedica | 1,705,723 | 1,132,034 (66.366813%) | 557,151 (32.663627%) | 16,538 (0.969560%) |
| Medscape | 3,661,537 | 1,769,046 (48.314301%) | 1,831,609 (50.022955%) | 60,882 (1.662744%) |
| Endato | 5,427,459 | 1,368,039 (25.205884%) | 4,015,015 (73.975962%) | 44,405 (0.818154%) |
| RocketReach | 3,199,535 | 1,882,787 (58.845645%) | 1,284,456 (40.145084%) | 32,292 (1.009272%) |
| DRDB | 826,886 | 592,272 (71.626802%) | 227,040 (27.457231%) | 7,574 (0.915967%) |
| Haymarket | 4,223,245 | 2,595,107 (61.448176%) | 1,574,520 (37.282232%) | 53,618 (1.269592%) |

Percentages use all links within each source. Categories partition links. Distinct-email outcomes cannot be inferred by adding link counts. Unknown is NULL, not disagreement.

Registry comparison does not depend on vendor names, so QuantumMedica, which has no usable vendor names, still has a registry result for 99.03% of its links (66.37% match). Unknown ranges from 0.64% (HealthLink) to 1.66% (Medscape). Endato has the lowest match share (25.21%) and Haymarket the highest (61.45%). Match exceeds no-match in every source except Endato (25.21% against 73.98%) and Medscape (48.31% against 50.02%).

# Email matches registry name

**Question:** does the email's mailbox text resemble a name recorded for its NPI? This does not establish mailbox ownership or validate the vendor attribution.

**Where:** `email_matches_registry_name` in `iceberg.jteixeira_ipa.pii__int_<vendor>__metrics`; key: `source`, `metric_row_id`. Vendors: `healthlink`, `quantummedica`, `medscape`, `endato`, `rocketreach`, `drdb`, `haymarket`.

**Inputs and join:** cleaned `email` and `npi`; `iceberg.npi.npi_reference.npi`, `first_name`, `last_name`. The [registry model](../../models/intermediate/int_npi__names.sql) retains distinct normalized name pairs per trimmed NPI. The join is left-sided and uses NPI only. Unmatched metric rows remain; duplicate reference names cannot multiply final metric rows or historical observation counts.

## How it is computed

After the NPI join, apply the [email-to-name rules](05_email_matches_source_name.md#email-matches-source-name) to each registry name: first/last text, initials, nickname variants, then the one-edit rule. A usable name has at least one first-name letter and two last-name letters. Each comparison produces `registry_match`. Within `source`, `metric_row_id`, keep any true result; all false gives false, and all null stays unknown:

```sql
bool_or(registry_match) AS email_matches_registry_name
```

`registry_npi_present` distinguishes an absent NPI from an existing NPI with unusable names. `registry_name_usable` records whether comparison is possible. Reference presence does not establish NPI validity or active status.

**Limits:** all readable registry name variants contribute, regardless of `last_update_date` or deactivation. This is not an as-of join: a historical vendor link can match a name recorded later. The same email can match multiple NPIs sharing names or initials.

## Real examples: contrasting outcomes

Selected real records, queried October 30, 2026, from `iceberg.jteixeira_ipa.pii_clean` at snapshot `8096642935433856886`. These examples explain outcomes; they are not prevalence estimates. Domains are omitted. The stored flag comes from the pinned publication; displayed normalized registry names come from the current readable name view, not a historical name snapshot.

[Runnable example SQL](../../sql/examples/06_email_matches_registry_name.sql):

```sql
WITH selected AS (
    SELECT *
    FROM iceberg.jteixeira_ipa.pii_clean FOR VERSION AS OF 8096642935433856886
    WHERE (source = 'endato' AND metric_row_id IN (
        '3AB5531256593B67A556B04342AE72261F03C9B3416FD46E7250A59C2C6AB8C4',
        '943C32434D8F3C31FB2CE056B12EAA4B99EC80176D39E205E3F44D254A4D8156'))
       OR (source = 'quantummedica' AND metric_row_id IN (
        'DDC68949352F656A5940211F39FA5D49EBDFA57F7AB2B41CCF7C1E1F7278BABA'))
)
SELECT m.source,
       split_part(m.email, '@', 1) AS mailbox,
       concat(r.first_name, ' ', r.last_name) AS registry_name,
       m.registry_npi_present,
       m.registry_name_usable,
       m.email_matches_source_name,
       m.email_matches_registry_name
FROM selected m
LEFT JOIN iceberg.jteixeira_ipa.pii__int_npi__names r ON m.npi = r.npi
ORDER BY m.source, m.metric_row_id
```

**Result:** 3 rows.

| source | mailbox | registry_name | registry_npi_present | registry_name_usable | email_matches_source_name | email_matches_registry_name |
|---|---|---|---|---|---|---|
| endato | dawney24 | NULL | false | false | false | NULL |
| endato | sav1999 | EMILY SANDERS | true | true | false | false |
| quantummedica | austin | MARTIN AUSTIN | true | true | NULL | true |

**What differentiates these cases:** Registry resemblance can be true even when the vendor supplied no usable name: the QuantumMedica row has a NULL source-name match but a true registry-name match. A usable registry name without mailbox agreement gives false. An absent registry NPI leaves NULL. The displayed `austin`/MARTIN AUSTIN pair also passes the one-edit fallback: `austin` differs from initial-plus-surname `maustin` by one deletion. This permissive rule can accept surname-only mailboxes. The registry flag aggregates all usable reference variants; displayed names are inspection evidence.

Stored indicators are unchanged by display helpers. Reproduction requires the pinned snapshot to remain available.

## Statistics by source

[Statistics SQL](../../sql/statistics/06_email_matches_registry_name.sql). This standalone read-only equivalent calculates the displayed row counts and percentages from the published table. The saved October 29 tables were derived from the linked grouped-population extraction; this equivalent has been checked locally, not executed against Trino.

Measured October 29, 2026, on `iceberg.jteixeira_ipa.pii_clean` at exact source-record/email-position grain. Percentages use all metric rows within each vendor. Counts are exact and cover all retained history; email–NPI links remain undeduplicated. These are saved measurements, not live counts.

| Source | Metric rows | Match, n (%) | No match, n (%) | Unknown, n (%) |
|---|---:|---:|---:|---:|
| HealthLink | 11,156,016 | 7,492,209 (67.15846%) | 3,594,122 (32.21690%) | 69,685 (0.62464%) |
| QuantumMedica | 1,705,723 | 1,132,034 (66.36681%) | 557,151 (32.66363%) | 16,538 (0.96956%) |
| Medscape | 47,072,262 | 23,738,814 (50.43058%) | 22,793,387 (48.42212%) | 540,061 (1.14730%) |
| Endato | 5,427,459 | 1,368,039 (25.20588%) | 4,015,015 (73.97596%) | 44,405 (0.81815%) |
| RocketReach | 4,864,145 | 2,881,550 (59.24063%) | 1,932,277 (39.72491%) | 50,318 (1.03447%) |
| DRDB | 1,115,415 | 783,767 (70.26685%) | 320,825 (28.76284%) | 10,823 (0.97031%) |
| Haymarket | 4,223,245 | 2,595,107 (61.44818%) | 1,574,520 (37.28223%) | 53,618 (1.26959%) |

Unknown is null, not false. Name outcomes can differ across records sharing the same email/NPI. These row counts do not establish distinct-email outcome counts.

Derived row statistics (historical output, not retained: `../../results/documentation_row_statistics.json`) · [Executed population SQL](../../results/metric_population_20261029/grouped.sql) · Measurement metadata (historical output, not retained: `../../results/metric_population_20261029/analysis_metadata.json`) · Published-table validation (historical output, not retained: `../../results/final_build.json`)

[Profile SQL](../../sql/name_match_profile.sql) · [Rule SQL](../../macros/name_matching.sql)

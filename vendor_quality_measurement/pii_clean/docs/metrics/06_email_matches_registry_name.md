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

## Real examples

Executed October 31, 2026, against canonical snapshot `8811920360682490090`. These selected cases explain outcomes; they do not measure prevalence. Registry-name displays additionally use the current readable name view; those names are not snapshot-pinned with the stored indicators.

[Executed example SQL](../../sql/examples/06_email_matches_registry_name.sql):

```sql
WITH selected AS (
    SELECT *
    FROM iceberg.jteixeira_ipa.pii_clean FOR VERSION AS OF 8811920360682490090
    WHERE (source = 'endato' AND metric_row_id IN (
        '3AB5531256593B67A556B04342AE72261F03C9B3416FD46E7250A59C2C6AB8C4',
        '943C32434D8F3C31FB2CE056B12EAA4B99EC80176D39E205E3F44D254A4D8156'))
       OR (source = 'quantummedica' AND metric_row_id IN (
        'DDC68949352F656A5940211F39FA5D49EBDFA57F7AB2B41CCF7C1E1F7278BABA'))
)
SELECT m.source,
       m.email,
       m.npi,
       concat(r.first_name, ' ', r.last_name) AS registry_name,
       m.registry_npi_present,
       m.registry_name_usable,
       m.email_matches_source_name,
       m.email_matches_registry_name
FROM selected m
LEFT JOIN iceberg.jteixeira_ipa.pii__int_npi__names r ON m.npi = r.npi
ORDER BY m.source, m.metric_row_id
```

| source | email | npi | registry_name | registry_npi_present | registry_name_usable | email_matches_source_name | email_matches_registry_name |
|---|---|---|---|---|---|---|---|
| endato | dawney24@yahoo.com | 1972990125 | NULL | false | false | false | NULL |
| endato | sav1999@yahoo.com | 1003479874 | EMILY SANDERS | true | true | false | false |
| quantummedica | austin@gwinnettmedicalcenter.org | 1760533418 | MARTIN AUSTIN | true | true | NULL | true |

**What differentiates these cases:** Registry resemblance can be true even when the vendor supplied no usable name: the QuantumMedica row has a NULL source-name match but a true registry-name match. A usable registry name without mailbox agreement gives false. An absent registry NPI leaves NULL. The displayed `austin`/MARTIN AUSTIN pair also passes the one-edit fallback: `austin` differs from initial-plus-surname `maustin` by one deletion. This permissive rule can accept surname-only mailboxes. The registry flag aggregates all usable reference variants; displayed names are inspection evidence.

## Statistics by source

Measured **October 31, 2026** from `iceberg.jteixeira_ipa.pii_clean` snapshot `8811920360682490090`. These are exact published-population counts across retained eligible history, not a sample. Stored evaluation dates remain unchanged.

[Executed statistics SQL](../../sql/statistics/06_email_matches_registry_name.sql)

| Source | Metric records | Match, n (%) | No match, n (%) | Unknown, n (%) |
|---|---|---|---|---|
| HealthLink | 11,156,016 | 7,492,209 (67.158464%) | 3,594,122 (32.216895%) | 69,685 (0.624641%) |
| QuantumMedica | 1,705,723 | 1,132,034 (66.366813%) | 557,151 (32.663627%) | 16,538 (0.969560%) |
| Medscape | 47,164,366 | 23,786,545 (50.433297%) | 22,837,391 (48.420859%) | 540,430 (1.145844%) |
| Endato | 5,427,459 | 1,368,039 (25.205884%) | 4,015,015 (73.975962%) | 44,405 (0.818154%) |
| RocketReach | 4,864,145 | 2,881,550 (59.240627%) | 1,932,277 (39.724905%) | 50,318 (1.034468%) |
| DRDB | 1,115,415 | 783,767 (70.266851%) | 320,825 (28.762837%) | 10,823 (0.970311%) |
| Haymarket | 4,223,245 | 2,595,107 (61.448176%) | 1,574,520 (37.282232%) | 53,618 (1.269592%) |

Percentages use all metric records within each source. Categories partition records. Distinct-email outcomes cannot be inferred by adding record counts. Unknown is NULL, not disagreement. Names and outcomes can differ between records sharing an email/NPI.

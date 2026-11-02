# 26. Medscape registration supersession

Registration supersession distinguishes historical Medscape claims from the latest observed claim for the same registration and email. It does not declare the latest NPI correct.

## How it is computed

The [macro](../../macros/sequential_history.sql) runs inside `int_medscape__metrics`, after cumulative NPI opt-outs. A link can carry several cleaned registration GUIDs. Each link is expanded to one row per (link, GUID) with that GUID's own observed days, and eligible observations are grouped by source, GUID and email. Unknown GUIDs are never grouped into a synthetic registration.

Within each GUID/email, the maximum observed day through `sequence_as_of_day` supplies `registration_latest_observed_day`. Distinct NPIs on that day become `registration_latest_npis`. Each (link, GUID) also retains `registration_link_last_observed_day`, the last day that GUID reported the link. No future dated observation participates.

```sql
CASE WHEN cardinality(latest_npis) <> 1 THEN 'ambiguous_latest'
     WHEN contains(latest_npis, npi) THEN 'latest_observed'
     ELSE 'superseded' END AS registration_link_status
```

This excerpt applies only after confirming usable GUID, dated link observations and no undated registration evidence. Otherwise status is `unknown`. Other vendors receive `not_applicable`. Multiple latest NPIs remain ambiguous for every link in that registration.

Each link publishes one row. It reports the most recently observed of its GUIDs (greatest `registration_link_last_observed_day`, ties broken by GUID) in `registration_guid`, with that GUID's status, dates and replacement fields.

## Examples and limits

Illustrative observations: GUID G reports email E with NPI A on January 1, then B on January 2. At January 1, A is latest observed. At January 2, A is superseded and B is latest observed. If A returns alone on January 3, A becomes latest observed and B becomes superseded.

`registration_superseded_since_day` is the first observed registration day after the old NPI last appeared. `registration_superseded_by_npis` holds the unique latest observed NPI, not necessarily the first intervening replacement. Both are empty/NULL unless status is superseded. `registration_supersession_definition_version` identifies the rule.

Another GUID may still report A for the same email. Supersession therefore never applies indiscriminately across all email/NPI links, and an email-level flip-back does not supersede a registration across GUID boundaries. A later classification does not rewrite what was known on earlier days. No links are filtered or redirected; conflict indicators are unaffected.

## Real examples

Executed November 2, 2026, against `iceberg.jteixeira_ipa.pii_clean` snapshot `2837737034249693554`. These selected cases explain outcomes; they do not measure prevalence.

```sql
SELECT source, email, npi, record_count, registration_guid, registration_link_status,
       registration_link_last_observed_day, registration_latest_observed_day,
       registration_latest_npis, registration_superseded_since_day, registration_superseded_by_npis
FROM iceberg.jteixeira_ipa.pii_clean
WHERE ROW(source, link_id) IN (
    ROW('medscape', '000003E89687B0747799F66B933F62332C57BB2FD0FDFE3D96D63F41944A4C61'),
    ROW('medscape', '4821799311E3ACBA17FFAD2AB22009385A063F35CBB4046DBF8BB07A1293F687'),
    ROW('medscape', '7670F3D32CE56873A71091E69675641F23F7F399E63C1E515790A304003A2D0C'),
    ROW('medscape', '0CF18CAFBB0225E8B4AA033E2BE72EA19A212FFF8EFADD542854F7BFB12256E6'),
    ROW('medscape', '07F90157AC8FA07254DD4BF552EB4E4AEF27B83FDB65D97827B7FCDB7E7324A7'))
ORDER BY email, npi, link_id
```

| source | email | npi | record_count | registration_guid | registration_link_status | registration_link_last_observed_day | registration_latest_observed_day | registration_latest_npis | registration_superseded_since_day | registration_superseded_by_npis |
|---|---|---|---|---|---|---|---|---|---|---|
| medscape | drobertsmm@aol.com | 1285060574 | 2 | 52270267 | latest_observed | 2026-11-01 | 2026-11-01 | [1285060574] | NULL | [] |
| medscape | drobertsmm@aol.com | 1346363231 | 1 | 52270267 | superseded | 2025-10-21 | 2026-11-01 | [1285060574] | 2025-12-06 | [1285060574] |
| medscape | roadrunner262001@yahoo.com | 1003803560 | 1 | 28917062 | superseded | 2025-10-29 | 2026-06-16 | [1528583325] | 2025-10-30 | [1528583325] |
| medscape | roadrunner262001@yahoo.com | 1528583325 | 1 | 28917062 | latest_observed | 2026-06-16 | 2026-06-16 | [1528583325] | NULL | [] |
| medscape | usmanayubkhan@gmail.com | 1346658416 | 1 | 31424166 | latest_observed | 2025-04-10 | 2025-04-10 | [1346658416] | NULL | [] |

**What differentiates these cases:** GUID 28917062 last reported `roadrunner262001@yahoo.com` with NPI `1003803560` on 2025-10-29; the registration's latest observed day is 2026-06-16 and its only latest NPI is `1528583325`. NPI `1003803560` is therefore `superseded`, since 2025-10-30 (the first registration day after it last appeared), by `1528583325`, which is `latest_observed`. GUID 52270267 shows the same pattern for `drobertsmm@aol.com`: `1346363231` was last seen under this GUID on 2025-10-21 and is superseded since 2025-12-06 by `1285060574`, which has two versions and is latest observed on 2026-11-01. `usmanayubkhan@gmail.com` with NPI `1346658416` under GUID 31424166 is latest observed although its last day is 2025-04-10: latest is relative to that registration, not to the calendar.

## Statistics and validation

Measured **November 2, 2026** from `iceberg.jteixeira_ipa.pii_clean` snapshot `2837737034249693554`. These are exact published-population counts across retained eligible history, not a sample.

Source data period (first and last observed day): HealthLink 2026-01-07 to 2026-10-03, QuantumMedica 2025-09-14 to 2026-10-15, Medscape 2024-01-10 to 2026-11-01 and Haymarket 2021-07-06 (one snapshot day). Endato, RocketReach and DRDB are undated.

[Population SQL](../../sql/statistics/26_registration_supersession.sql) counts distinct Medscape GUID/email/NPI/status combinations, separately from source/email/NPI links. Each published link reports one GUID, so the 3,661,537 registration links equal the Medscape link count. Missing GUID combinations remain unknown rather than identifiable registrations.

| Source | Status | Registration links, n (%) |
|---|---|---|
| Medscape | latest_observed | 3,552,169 (97.013058%) |
| Medscape | superseded | 109,368 (2.986942%) |

About 3.0% of Medscape registration links are superseded and 97.0% are the latest observed claim of their registration. No link has `ambiguous_latest` or `unknown` status, because every Medscape link carries a GUID and no registration has several latest NPIs on its latest day.

[Synthetic tests](../../tools/test_sequential_history.py) cover replacements, reappearance, missing GUID/date evidence, multiple latest NPIs and registration isolation. [Stored integrity checks](../../tests/sequential_history.sql) validate status, dates and replacement fields.

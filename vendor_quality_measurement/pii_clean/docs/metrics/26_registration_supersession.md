# 26. Medscape registration supersession

Registration supersession distinguishes historical Medscape claims from the latest observed claim for the same registration and email. It does not declare the latest NPI correct. These fields are published in complete canonical snapshot `8811920360682490090`, verified October 31, 2026. Native Medscape core integrity and final preservation checks passed. See [build evidence](../build_recovery.md).

## How it is computed

The [macro](../../macros/sequential_history.sql) runs inside `int_medscape__metrics`, after cumulative NPI opt-outs. It extracts cleaned `registration_guid` from the exact record's stored payload and groups eligible observations by source, GUID and email. Unknown GUIDs are never grouped into a synthetic registration.

The maximum observed day through `sequence_as_of_day` supplies `registration_latest_observed_day`. Distinct NPIs on that day become `registration_latest_npis`. Each NPI also retains `registration_link_last_observed_day`. No future dated observation participates.

```sql
CASE WHEN cardinality(latest_npis) <> 1 THEN 'ambiguous_latest'
     WHEN contains(latest_npis, npi) THEN 'latest_observed'
     ELSE 'superseded' END AS registration_link_status
```

This excerpt applies only after confirming usable GUID, dated link observations and no undated registration evidence. Otherwise status is `unknown`. Other vendors receive `not_applicable`. Multiple latest NPIs remain ambiguous for every link in that registration.

## Examples and limits

Illustrative observations: GUID G reports email E with NPI A on January 1, then B on January 2. At January 1, A is latest observed. At January 2, A is superseded and B is latest observed. If A returns alone on January 3, A becomes latest observed and B becomes superseded.

`registration_superseded_since_day` is the first observed registration day after the old NPI last appeared. `registration_superseded_by_npis` holds the unique latest observed NPI, not necessarily the first intervening replacement. Both are empty/NULL unless status is superseded. `registration_supersession_definition_version` identifies the rule.

Another GUID may still report A for the same email. Supersession therefore never applies indiscriminately across all email/NPI records. A later classification does not rewrite what was known on earlier days. No records are filtered or redirected; existing conflict indicators remain unchanged.

## Real example: an older registration claim is superseded

Queried October 31, 2026, for stored cleaned email `sbrooks.arnp@gmail.com` and registration GUID `16994466`. The [stored-field SQL](../../sql/examples/26_registration_supersession_published.sql) reads `iceberg.jteixeira_ipa.pii_clean` snapshot `8811920360682490090` without recomputing registration status. The stored sequence cutoff is October 30. Cumulative exclusions used opt-out snapshot `4503450222412661359` during core construction.

| source | email | GUID | NPI | Registration link status | Last link day | Latest registration day | Superseded since | Superseded by |
|---|---|---|---|---|---|---|---|---|
| medscape | sbrooks.arnp@gmail.com | 16994466 | 1700132818 | latest_observed | 2026-03-18 | 2026-03-18 | NULL | [] |
| medscape | sbrooks.arnp@gmail.com | 16994466 | 1790783207 | superseded | 2025-10-29 | 2026-03-18 | 2025-10-30 | [1700132818] |

The same registration/email last reports NPI `1790783207` on October 29, 2025. It reports `1700132818` on the next observed day, October 30, and retains that NPI through its latest observed day, March 18, 2026. The older claim therefore becomes superseded at this evaluation cutoff. Both historical claims remain available. This is registration-scoped vendor evidence; it does not establish that the replacement NPI is correct. The case illustrates the rule rather than prevalence.

## Statistics and validation

[Population SQL](../../sql/statistics/26_registration_supersession.sql) counts distinct Medscape GUID/email/NPI/status combinations, separately from metric rows or source/email/NPI links. Missing GUID combinations remain unknown rather than identifiable registrations. Complete canonical snapshot `8811920360682490090`, measured October 31, 2026, contains:

| Registration status | Registration links | Percent |
|---|---:|---:|
| latest_observed | 3,551,648 | 97.0192% |
| superseded | 109,120 | 2.9808% |
| **Total** | **3,660,768** | **100%** |

No unknown or ambiguous-latest links appeared in this measured population. Those outcomes remain supported by the definition and synthetic tests.

[Synthetic tests](../../tools/test_sequential_history.py) cover replacements, reappearance, missing GUID/date evidence, multiple latest NPIs and registration isolation. [Stored integrity checks](../../tests/sequential_history.sql) validate status, dates and replacement fields. Native checks passed on all rebuilt Medscape rows.

Validation checkpoint, October 31, 2026: the complete local suite passed 120 tests. Native core checks validated the rebuilt Medscape population, and final enrichment preserved all 124 core fields. The stored example above passed native execution against the complete final snapshot. The same query also shows `fangchenmd@gmail.com` with two latest-observed NPIs belonging to different GUIDs (`14104992` and `35575811`). Its email-level flip-back does not supersede either registration across GUID boundaries.

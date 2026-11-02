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

No executed examples exist yet for this definition.

## Statistics and validation

No measurements exist yet for this definition.

[Population SQL](../../sql/statistics/26_registration_supersession.sql) counts distinct Medscape GUID/email/NPI/status combinations, separately from source/email/NPI links. Missing GUID combinations remain unknown rather than identifiable registrations.

[Synthetic tests](../../tools/test_sequential_history.py) cover replacements, reappearance, missing GUID/date evidence, multiple latest NPIs and registration isolation. [Stored integrity checks](../../tests/sequential_history.sql) validate status, dates and replacement fields.

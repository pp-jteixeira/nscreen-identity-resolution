# 21. Link stability

Stability describes a reported link's presence and overlap across a vendor's dated email history. It does not establish ownership, switching frequency or independent confirmation.

## How it is computed

The [macro](../../macros/link_stability.sql) counts distinct `observed_days` of each `source/email/npi` link, which already unions the days of all its versions. The email denominator unions days across every NPI for that `source/email`. Distinct `conflict_days` count days when this link accompanied another NPI. Repeated versions and email positions do not increase these counts. The columns are appended to each link in `iceberg.jteixeira_ipa.pii_clean`.

| Stored column | Meaning |
|---|---|
| `email_observed_day_count` | Distinct known days for the vendor/email across all NPIs. |
| `link_observed_day_count` | Distinct known days for this vendor/email/NPI. |
| `link_conflict_day_count` | Distinct known days this link overlapped another NPI. |
| `link_presence_share` | Link days divided by email days. |
| `link_overlap_share` | Conflict days divided by link days. |
| `link_stability_has_undated_observations` | Any link for this vendor/email, including peer NPIs, has undated or invalid-day observations. |

Shares are fractions from 0 to 1; multiply by 100 for percentages. Presence shares across NPIs can sum above 100% because days overlap. Several competing NPIs on one day still contribute only one conflict day. A link with no dated observations has zero link/conflict day counts and NULL shares. Its email-day denominator can still be positive when another NPI supplies dated email history. Mixed histories retain shares over known days and flag incomplete coverage. Missing calendar days are not inferred. All stored parsed dates participate; stability applies no evaluation-day filter.

## Real examples

No executed examples exist yet for this definition.

**What differentiates outcomes:** Full presence over one day supplies little history. Partial presence without overlap differs from appearing on every day alongside a competing NPI. A link can also have both partial presence and overlap. Undated links have zero known-day counts and NULL shares, rather than measured zero stability.

## Statistics by source

No measurements exist yet for this definition.

[Statistics SQL](../../sql/statistics/21_link_stability.sql)

Presence and overlap percentages use dated links. A zero dated denominator is undefined (—), not zero stability. Means weight each dated link equally. One-day histories can show full presence without sufficient sequential history. Distinct links within each source remain separate from globally unique people.

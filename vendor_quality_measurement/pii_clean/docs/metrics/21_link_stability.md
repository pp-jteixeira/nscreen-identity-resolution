# 21. Link stability

Stability describes a reported link's presence and overlap across a vendor's dated email history. It does not establish ownership, switching frequency or independent confirmation.

## How it is computed

The [macro](../../macros/link_stability.sql) unions distinct `observed_days` across records within each `source/email/npi`. The email denominator unions days across every NPI for that `source/email`. Distinct `conflict_days` count days when this link accompanied another NPI. Repeated records and email positions do not increase these counts. Original rows remain intact in `iceberg.jteixeira_ipa.pii_clean`.

| Stored column | Meaning |
|---|---|
| `email_observed_day_count` | Distinct known days for the vendor/email across all NPIs. |
| `link_observed_day_count` | Distinct known days for this vendor/email/NPI. |
| `link_conflict_day_count` | Distinct known days this link overlapped another NPI. |
| `link_presence_share` | Link days divided by email days. |
| `link_overlap_share` | Conflict days divided by link days. |
| `link_stability_has_undated_observations` | Any record for this vendor/email, including peer NPIs, has undated or invalid-day observations. |

Shares are fractions from 0 to 1; multiply by 100 for percentages. Presence shares across NPIs can sum above 100% because days overlap. Several competing NPIs on one day still contribute only one conflict day. A link with no dated observations has zero link/conflict day counts and NULL shares. Its email-day denominator can still be positive when another NPI supplies dated email history. Mixed histories retain shares over known days and flag incomplete coverage. Missing calendar days are not inferred. All stored parsed dates participate; stability applies no evaluation-day filter.

**Illustrative example:** daily NPI sets `{A}`, `{A,B}`, `{A}`, `{B}`, `{A}` give A presence `4/5 = 80%` and overlap `1/4 = 25%`. B has presence `2/5 = 40%` and overlap `1/2 = 50%`.

## Statistics and limits

[Standalone statistics SQL](../../sql/statistics/21_link_stability.sql) counts each source/email/NPI once. Mean percentages weight dated links equally. Full/partial presence and overlap counts describe distributions without assigning stable/unstable thresholds. Unknown shares are excluded from those percentages. Incomplete-date percentages use all links.

Always inspect the denominators: 100% presence over one day supplies little history. Endato, RocketReach and DRDB have NULL shares despite possible undated conflicts. Partial feeds and repeated snapshots limit interpretation. No scoring or record filters apply.

### Published population, October 30, 2026

All 75,564,265 records and 26,730,605 source/email/NPI links are retained. Percentages below use dated links, except unknown shares and incomplete email dates, which use all links. Counts refer to links, not people.

| Vendor | Links | Unknown shares (%) | Full presence / dated links (%) | Any overlap / dated links (%) | Mean presence / overlap (%) | Single email-day links | Incomplete email-date links (%) |
|---|---:|---:|---:|---:|---:|---:|---:|
| drdb | 826,886 | 826,886 (100.00000%) | — | — | — / — | 0 | 826,886 (100.00000%) |
| endato | 5,427,459 | 5,427,459 (100.00000%) | — | — | — / — | 0 | 5,427,459 (100.00000%) |
| haymarket | 4,223,245 | 0 (0.00000%) | 4,223,245 / 4,223,245 (100.00000%) | 0 / 4,223,245 (0.00000%) | 100.00000 / 0.00000 | 4,223,245 | 0 (0.00000%) |
| healthlink | 7,688,451 | 0 (0.00000%) | 7,688,211 / 7,688,451 (99.99688%) | 0 / 7,688,451 (0.00000%) | 99.99844 / 0.00000 | 1,223,251 | 0 (0.00000%) |
| medscape | 3,659,306 | 0 (0.00000%) | 3,440,818 / 3,659,306 (94.02925%) | 32 / 3,659,306 (0.00087%) | 97.01446 / 0.00050 | 30,735 | 0 (0.00000%) |
| quantummedica | 1,705,723 | 0 (0.00000%) | 1,705,722 / 1,705,723 (99.99994%) | 56 / 1,705,723 (0.00328%) | 99.99999 / 0.00327 | 1,087 | 0 (0.00000%) |
| rocketreach | 3,199,535 | 3,199,535 (100.00000%) | — | — | — / — | 0 | 3,199,535 (100.00000%) |

Haymarket’s full presence reflects a single observed day for every link. Dated overlap appears in 32 Medscape links and 56 QuantumMedica links. Undated-vendor conflicts remain visible through the existing conflict flag while their day-based shares remain unknown.

Executed [statistics SQL](../../sql/statistics/21_link_stability.sql) on published snapshot `8096642935433856886`. Results were inspected in memory. [Publication and compatibility checks](../../results/publication_stability_20261030/report.md).

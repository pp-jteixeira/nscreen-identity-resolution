# Has conflict linkage

**Principle:** flag competing reported NPIs at the same observation time, within one vendor/email. Output: nullable boolean `has_conflict_linkage`, one value per link, in `iceberg.jteixeira_ipa.pii__int_<vendor>__metrics` and `iceberg.jteixeira_ipa.pii_clean`.

## How it is computed

For dated vendors, count distinct NPIs within `source`, `email`, actual delivery day, using each link's `observed_days` across all its versions. Collect days with more than one NPI into `email_conflict_days`, then keep only days observed for this link:

```sql
count(DISTINCT npi) AS daily_npi_count
```

```sql
array_sort(array_intersect(observed_days, email_conflict_days)) AS conflict_days
```

Endato, RocketReach and DRDB compare all current links within each vendor, including both DRDB inputs. This assumes comparability, not a common collection date.

```sql
CASE WHEN source IN ('endato', 'rocketreach', 'drdb') THEN email_npi_count > 1
     WHEN cardinality(conflict_days) > 0 THEN true
     WHEN email_npi_count = 1 THEN false
     WHEN undated_observation_count > 0 THEN NULL
     ELSE false
END AS has_conflict_linkage
```

Repeated deliveries of one NPI do not create conflict. Unknown days in dated vendors remain unknown; date ranges are never expanded.

A link can span many days and several versions. `conflict_days` lists exactly which of the link's `observed_days` conflict; any such day makes its flag true. Undated-vendor conflicts have an empty `conflict_days` array. A conflict may reflect a shared mailbox or reporting error; it does not identify the correct NPI. All links remain in the table.

## Real examples

No examples have been executed against this definition yet.

Cases worth contrasting: a dated email reassigned without overlap (reassignment true, conflict false), a dated email whose NPIs overlap on every observed day (conflict true, reassignment false), and an undated Endato conflict with zero known conflict days. Zero known days does not undo an undated conflict, because the undated rule compares available vendor links rather than dated observations.

## Statistics by source

No measurements exist yet for this definition. [Statistics SQL](../../sql/statistics/10_has_conflict_linkage.sql) reports, per source, distinct emails, conflicting and unknown emails, and conflicting links.

Email percentages use distinct source/emails; link percentages use the source's links. Email-level conflict means at least one conflicting link. Unknown chronology remains separate from false.

# Has conflict linkage

**Principle:** flag competing reported NPIs at the same observation time, within one vendor/email. Output: nullable boolean `has_conflict_linkage` in `iceberg.jteixeira_ipa.pii__int_<vendor>__metrics` and `iceberg.jteixeira_ipa.pii_clean`.

## How it is computed

For dated vendors, count distinct NPIs within `source`, `email`, actual delivery day. Collect days with more than one NPI into `email_conflict_days`, then keep only days observed for this record:

```sql
count(DISTINCT npi) AS daily_npi_count
```

```sql
array_sort(array_intersect(observed_days, email_conflict_days)) AS conflict_days
```

Endato, RocketReach and DRDB compare all current records within each vendor, including both DRDB inputs. This assumes comparability, not a common collection date.

```sql
CASE WHEN source IN ('endato', 'rocketreach', 'drdb') THEN email_npi_count > 1
     WHEN cardinality(conflict_days) > 0 THEN true
     WHEN email_npi_count = 1 THEN false
     WHEN undated_observation_count > 0 THEN NULL
     ELSE false
END AS has_conflict_linkage
```

Repeated copies of one NPI do not create conflict. Unknown days in dated vendors remain unknown; date ranges are never expanded.

Otherwise-identical records can span several days. `conflict_days` lists exactly which of that record's `observed_days` conflict; any such day makes its flag true. Undated-vendor conflicts have an empty `conflict_days` array. A conflict may reflect a shared mailbox or reporting error; it does not identify the correct NPI. Source metric rows remain intact.

## Real examples

Executed October 31, 2026, against canonical snapshot `8811920360682490090`. These selected cases explain outcomes; they do not measure prevalence.

[Executed example SQL](../../sql/examples/10_has_conflict_linkage.sql):

```sql
WITH selected AS (
    SELECT *
    FROM iceberg.jteixeira_ipa.pii_clean FOR VERSION AS OF 8811920360682490090
    WHERE (source = 'endato' AND metric_row_id IN (
        '301CF08DDB677315479773A9D4F728F00F664700BC7F030088C7A8BA0AF05ECF'))
       OR (source = 'healthlink' AND metric_row_id IN (
        '4E8278D37C840774C11F0182CFB16FF3C1F32F292E6769A17B6E328688FE1A26'))
       OR (source = 'quantummedica' AND metric_row_id IN (
        'CA266C53D1E739500DDF891E13D3117AF4CB7478E74A5F6F42E31D9510149D1C'))
)
SELECT m.source,
       m.email,
       m.npi,
       m.email_npi_count,
       m.observed_days,
       m.conflict_days,
       m.has_been_reassigned,
       m.has_conflict_linkage,
       cardinality(m.conflict_days) AS conflict_day_count
FROM selected m
ORDER BY m.source, m.metric_row_id
```

| source | email | npi | email_npi_count | observed_days | conflict_days | has_been_reassigned | has_conflict_linkage | conflict_day_count |
|---|---|---|---|---|---|---|---|---|
| endato | devireddysr@yahoo.com | 1447336276 | 2 | [] | [] | NULL | true | 0 |
| healthlink | jadams@srhs.com | 1023557691 | 2 | [2026-10-03] | [] | true | false | 0 |
| quantummedica | aroman@prongersmith.com | 1174520019 | 2 | [2025-09-14, 2025-10-15, 2025-11-15, 2025-12-15, 2026-01-15, 2026-02-15, 2026-03-15, 2026-04-15, 2026-06-15, 2026-09-15, 2026-10-15] | [2025-09-14, 2025-10-15, 2025-11-15, 2025-12-15, 2026-01-15, 2026-02-15, 2026-03-15, 2026-04-15, 2026-06-15, 2026-09-15, 2026-10-15] | false | true | 11 |

**What differentiates these cases:** Reassignment can occur without overlap; persistent overlap can occur without reassignment. The undated Endato conflict has zero known conflict days because its rule compares available vendor records, not dated observations. Zero known days therefore does not undo its true conflict flag.

## Statistics by source

Measured **October 31, 2026** from `iceberg.jteixeira_ipa.pii_clean` snapshot `8811920360682490090`. These are exact published-population counts across retained eligible history, not a sample. Stored evaluation dates remain unchanged.

[Executed statistics SQL](../../sql/statistics/10_has_conflict_linkage.sql)

| Source | Distinct emails | True: emails, n (%) | Unknown: emails, n (%) | True: records, n (%) |
|---|---|---|---|---|
| HealthLink | 7,688,331 | 0 (0.000000%) | 0 (0.000000%) | 0 (0.000000%) |
| QuantumMedica | 1,705,695 | 28 (0.001642%) | 0 (0.000000%) | 56 (0.003283%) |
| Medscape | 3,550,359 | 16 (0.000451%) | 0 (0.000000%) | 46 (0.000098%) |
| Endato | 5,324,318 | 91,841 (1.724935%) | 0 (0.000000%) | 194,982 (3.592510%) |
| RocketReach | 3,163,679 | 29,990 (0.947947%) | 0 (0.000000%) | 96,287 (1.979526%) |
| DRDB | 819,454 | 7,400 (0.903040%) | 0 (0.000000%) | 22,404 (2.008580%) |
| Haymarket | 4,223,245 | 0 (0.000000%) | 0 (0.000000%) | 0 (0.000000%) |

Email percentages use distinct source/emails; record percentages use metric records. Email-level conflict means at least one conflicting record. Unknown chronology remains separate from false.

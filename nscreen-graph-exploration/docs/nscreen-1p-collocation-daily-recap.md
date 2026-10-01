# NScreenFirstPartyCollocationDaily recap

## Task
`NScreenFirstPartyCollocationDaily` (`src/nscreen_graph/tasks/daily.py:88`)

- SQL: `NScreenFirstPartyCollocationDaily.sql`
- Dest table: `iceberg.crossscreen.nscreen_1p_collocation_daily`, partitioned by `day`
- Requires: 24x `NScreenFirstPartyCollocationHourly` (one per hour of `self.day`) → source table `iceberg.crossscreen.nscreen_1p_collocation_hourly`

## SQL logic

```sql
select uid1, uid2, count(*) as weight
from iceberg.crossscreen.nscreen_1p_collocation_hourly
where day >= '{{ start_day }}' and day <= '{{ day }}'
group by uid1, uid2
```

`start_day = day - 30`. Each daily run aggregates a **rolling 30-day lookback window** of hourly src data into a single output `day` partition. One partition = one day's worth of *output*, not 30 separate rows.

## Trino day counts (checked 2026-08-30)

| Table | Distinct days | Range |
|---|---|---|
| `nscreen_1p_collocation_hourly` (source) | 193 | 2026-02-19 → 2026-08-30 |
| `nscreen_1p_collocation_daily` (dest) | 11 | 2026-08-19 → 2026-08-29 |

Source has plenty of history. Dest only has 11 partitions — likely task started running recently / no backfill beyond 11 days, not a bug per se.

## Followers of `nscreen_1p_collocation_daily`

Only one direct consumer found: `NScreenIpCollocationDailyClean` (`daily.py:115`, SQL `NScreenIpCollocationDailyClean.sql:17`).

- Luigi requires: `NScreenFirstPartyCollocationDaily(day=self.day)` — same day only, no loop.
- SQL: `where day = '{{ day }}'` — reads exactly one partition, no lookback.

**Conclusion:** follower needs only a single day of dest data, not more. 11 available days is sufficient for current-day runs — no downstream impact from the shallow dest history, since each partition already encodes 30 days of source aggregation internally.

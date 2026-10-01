# Lookback Window Inventory

This document lists all scripts in this repository that use, pass, or consume lookback-style time windows.

## Scope

Lookback-related patterns covered here:
- `_LOOKBACK_DAYS`
- `date_sub(..., num_days=...)`
- `start_day` SQL variables
- `LookbackWrapperTask`

## Explicit Window Definitions (Task Code)

### 14-day window

1. `src/nscreen_graph/tasks/daily.py`
	- Constant: `_LOOKBACK_DAYS = 14`
	- Used by `NScreenIpColocationDailyAllUa` to set `start_day`.
	- Used by `NScreenIpColocationDailyAllUa.requires` to build day-by-day dependencies from `start_day` through `day` (inclusive).
	- Used by `NScreenGeoDaily` to set `start_day`.

What it represents:
- Short-term recency context for IP colocation and geo feature generation.

### 30-day window

1. `src/nscreen_graph/tasks/daily.py`
	- `NScreenFirstPartyCollocationDaily` sets `start_day` with `num_days=30`.

What it represents:
- Longer-term first-party collocation context for more stable relationship signals.

## SQL Scripts That Consume the Lookback Inputs

These scripts apply the `start_day` filter passed from daily task code. They do not define the window size.

1. `src/nscreen_graph/spark/sparksql/NScreenIpColocationDailyAllUa.sql`
	- Filters `day` between `start_day` and `day`.

2. `src/nscreen_graph/spark/sparksql/NScreenGeoDaily.sql`
	- Filters `day` using `start_day`.

3. `src/nscreen_graph/spark/sparksql/NScreenFirstPartyCollocationDaily.sql`
	- Filters `day` between `start_day` and `day`.

## Wrapper-Based Lookback Behavior

1. `src/nscreen_graph/tasks/hourly.py`
	- `NScreenHourlyGraphRunner` inherits from `LookbackWrapperTask`.

Interpretation:
- This indicates lookback-capable orchestration for hourly runs.
- The exact default window size is not defined in this repository file and comes from the external `dpdtk` implementation/configuration.

## Complete File List

All repository files with lookback-related hits:

1. `src/nscreen_graph/tasks/daily.py`
2. `src/nscreen_graph/tasks/hourly.py`
3. `src/nscreen_graph/spark/sparksql/NScreenIpColocationDailyAllUa.sql`
4. `src/nscreen_graph/spark/sparksql/NScreenGeoDaily.sql`
5. `src/nscreen_graph/spark/sparksql/NScreenFirstPartyCollocationDaily.sql`
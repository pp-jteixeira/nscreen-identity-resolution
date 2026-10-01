# Vendor Activity Coverage Analysis

## Current Decision

The working dataset uses activity from `2026-09-16`. Vendor matchids are filtered using same-day logevent overlap, vendor-specific total-cookie caps, vendor-specific coverage lines, and a high-coverage exception.

Eligible matchids and sampled memberships are persisted separately for Experian, LiveRamp, and Throtle. Each vendor has deterministic `0.5%` and `0.1%` matchid samples. Sampling targets matchids rather than membership rows, so selected matchids retain complete membership stars.

The persisted `0.5%` sample contains `785,704` vendor-matchids and `14,288,711` membership rows. The nested `0.1%` sample contains `157,321` vendor-matchids and `2,863,582` membership rows. Use the smaller sample for quicker vendor-stage iteration.

## Scope

- Activity date: `2026-09-16`
- Vendors: Experian, LiveRamp, Throtle
- Activity window: same day
- Matchid sample rates: `0.5%` and `0.1%` per vendor
- Sample seed: `nscreen-graph-local-v1`
- Trino schema: `iceberg.jteixeira_ipa`
- Run label: `line_filter_v1`

Sampling is rate-driven. No fixed membership-row target applies.

## Core Definitions

`total_cookie_count`
: Distinct eligible vendor cookies per vendor-matchid. Synthetic vendor anchors are excluded from this eligibility metric.

`overlapping_cookie_count`
: Distinct eligible vendor cookies also observed within same-day `visitorlogevent` identifiers.

`activity_coverage_pct`
: `100 * overlapping_cookie_count / total_cookie_count`.

`membership row`
: One persisted vendor, UID, matchid, household, and stability association used by `nscreen-graph`.

Evidence measures same-day observability. It does not establish identity correctness.

## Working Eligibility Rules

Every retained vendor-matchid must satisfy all shared conditions:

- At least one overlapping cookie
- Nonzero matchid
- Nonempty UID
- Vendor-specific synthetic anchor exclusion during eligibility scoring
- Vendor-specific total-cookie cap
- Vendor-specific line filter or high-coverage exception

### Total-Cookie Caps

| Vendor | Exclusive cap |
|---|---:|
| Experian | 250 |
| LiveRamp | 100 |
| Throtle | 75 |

### Line Filters

| Vendor | Cookie intercept | Coverage intercept |
|---|---:|---:|
| Experian | 75 | 60% |
| LiveRamp | 80 | 80% |
| Throtle | 25 | 110% |

For each vendor, a matchid passes below its line when:

```text
activity_coverage_pct <= coverage_intercept
    * (1 - total_cookie_count / cookie_intercept)
```

Points above this line are filtered unless they qualify for the exception:

```text
activity_coverage_pct > 95
AND total_cookie_count < cookie_intercept
```

## Eligibility Computation

Eligibility is computed independently per vendor. Each query reads one vendor source plus same-day `iceberg.fact.visitorlogevent` data.

Synthetic anchor exclusions are:

| Vendor | Excluded UID prefixes |
|---|---|
| Experian | `EP_`, `EL_` |
| LiveRamp | `LR_` |
| Throtle | `TH_` |

Created eligibility tables:

- `iceberg.jteixeira_ipa.nscreen_eligible_matchids_experian_20260916_line_filter_v1`
- `iceberg.jteixeira_ipa.nscreen_eligible_matchids_liveramp_20260916_line_filter_v1`
- `iceberg.jteixeira_ipa.nscreen_eligible_matchids_throtle_20260916_line_filter_v1`

Recorded creation times:

| Vendor | Eligibility runtime |
|---|---:|
| Experian | 85.798 seconds |
| LiveRamp | 244.288 seconds |
| Throtle | 180.340 seconds |
| **Total** | **510.426 seconds** |

## Sampling Method

Sampling occurs independently within each vendor eligibility table. The deterministic hash key combines vendor, matchid, and sample seed. Hash values map into `1,000,000` buckets. The first `5,000` buckets produce the `0.5%` sample. The first `1,000` buckets produce the nested `0.1%` sample.

For the `0.5%` sample, selected matchids are joined back to their complete vendor source memberships. This step retains synthetic anchor rows needed by the graph, while eligibility scoring itself excludes those anchors. The `0.1%` tables are strict subsets of the persisted `0.5%` tables using the same hash predicate and seed, so complete membership stars remain intact.

Separate vendor queries reduce peak workload and allow isolated retries. Independent vendor sampling does not preserve production cross-vendor connectivity rates. Graph merge-rate results from this sample should therefore remain experimental.

## Persisted Membership Tables

- `iceberg.jteixeira_ipa.nscreen_membership_sample_experian_20260916_line_filter_v1_0p5pct`
- `iceberg.jteixeira_ipa.nscreen_membership_sample_liveramp_20260916_line_filter_v1_0p5pct`
- `iceberg.jteixeira_ipa.nscreen_membership_sample_throtle_20260916_line_filter_v1_0p5pct`

Nested `0.1%` tables:

- `iceberg.jteixeira_ipa.nscreen_membership_sample_experian_20260916_line_filter_v1_0p1pct`
- `iceberg.jteixeira_ipa.nscreen_membership_sample_liveramp_20260916_line_filter_v1_0p1pct`
- `iceberg.jteixeira_ipa.nscreen_membership_sample_throtle_20260916_line_filter_v1_0p1pct`

Each table contains:

- `day`
- `vendor`
- `uid`
- `matchid`
- `householdid`
- `stable`

LiveRamp preserves source `stable` values. Experian and Throtle use `true`.

## Persisted Sample Results

| Vendor | Sampled matchids | Membership rows | Rows per matchid | Row share | Sample runtime |
|---|---:|---:|---:|---:|---:|
| Experian | 221,116 | 4,027,677 | 18.22 | 28.19% | 91.470 seconds |
| LiveRamp | 409,049 | 9,339,019 | 22.83 | 65.36% | 96.796 seconds |
| Throtle | 155,539 | 922,015 | 5.93 | 6.45% | 23.069 seconds |
| **Total** | **785,704** | **14,288,711** | **18.19** | **100.00%** | **211.335 seconds** |

Validation completed in `2.422` seconds.

The resulting membership volume is `42.89%` above the earlier `10M` local planning target. Future local runs should record peak memory and wall-clock time before increasing the sampling rate.

### Nested `0.1%` Sample Results

| Vendor | Sampled matchids | Membership rows | Rows per matchid |
|---|---:|---:|---:|
| Experian | 43,997 | 803,992 | 18.27 |
| LiveRamp | 82,181 | 1,875,048 | 22.82 |
| Throtle | 31,143 | 184,542 | 5.93 |
| **Total** | **157,321** | **2,863,582** | **18.20** |

All persisted rows passed the `1,000 / 1,000,000` hash-bucket condition. Each table contains one source day.

This smaller sample changes only vendor inputs. Local replay still uses the full production collocation and geography tables. Vendor-stage work should shrink, but remainder clustering should not be expected to shrink proportionally.

## Population Estimate Warning

Scaling sampled matchid counts by `1 / 0.005` gives approximate eligible populations:

| Vendor | Implied eligible matchids |
|---|---:|
| Experian | 44.22M |
| LiveRamp | 81.81M |
| Throtle | 31.11M |
| **Total** | **157.14M** |

These are sampling estimates, not exact table counts.

Earlier analysis used `mod(matchid, 10) = 0` and estimated `305.94M` retained vendor-matchids. The large discrepancy indicates that decimal matchid modulus sampling was not representative for these identifier distributions. Do not use earlier modulus-scaled population counts for capacity planning. Prefer hash sampling or exact counts from persisted eligibility tables.

## Reproducibility

Current notebook:

- [`vendor-logevent-coverage.ipynb`](../../vendor-logevent-coverage.ipynb)

Current cached aggregate:

- [`matchid_stats_2026-09-16_2026-09-16_sample-0-of-10.csv.gz`](../../outputs/vendor_activity_coverage/matchid_stats_2026-09-16_2026-09-16_sample-0-of-10.csv.gz)

Changing source date, filters, or seed requires a new `SAMPLE_RUN_LABEL`. Different sample rates use distinct rate suffixes. Existing Iceberg tables should remain immutable unless explicitly replaced.

## Future Use

Use the three `0.1%` membership tables for quick local iteration. Retain the `0.5%` tables for wider experiments. Keep vendor provenance through graph construction. Record runtime, peak memory, graph component counts, merge rates, and discarded memberships.

Treat connectivity and cross-vendor merge results as sample behavior, not production-rate estimates. Independent vendor sampling can omit bridging matchids and shared cookies.

## Status

Working filters are selected but remain experimental. Vendor-specific eligibility and both membership samples are materialized. The `0.5%` replay reached remainder clustering and was stopped. The `0.1%` profile is ready for a new replay run.

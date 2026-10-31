# Medscape NPI opt-out exclusion

**Status:** published and validated October 31, 2026. Medscape’s intermediate model excludes every cleaned NPI present in `iceberg.thirdparty.medscape_npi_optout`. The complete canonical publication contains 47,164,366 eligible Medscape records from newer pinned source inputs. See [build evidence](build_recovery.md).

## Eligibility rule

`stg_medscape__optout` preserves all raw deliveries and adds trimmed `npi_clean`. Intermediate `global_versions` applies the exclusion before exact-record aggregation, email eligibility, multiplicity, conflict, name, geography, freshness, stability and vendor-label calculations. Stored core unions eligible vendor outputs before downstream cookie enrichment.

The [record-version macro](../macros/record_versions.sql) joins only the staged opt-out NPI column and keeps unmatched records:

```sql
LEFT JOIN (SELECT npi_clean FROM pii__stg_medscape__optout) excluded
    ON s.npi_clean = excluded.npi_clean
WHERE excluded.npi_clean IS NULL
```

The model’s actual `ref()` resolves to `iceberg.jteixeira_ipa.pii__stg_medscape__optout`. Duplicate opt-outs cannot multiply surviving records. Null/blank opt-out NPIs cannot exclude unrelated nonempty keys. All retained opt-out rows contribute, regardless of delivery/opt-out date validity or chronology, matching Forge’s cumulative NPI exclusion policy. An opt-out can therefore remove older attribution history; this does not reconstruct historical opt-out timing.

Staging remains row-preserving. Other vendors retain their existing eligibility. Surviving records keep their identifiers, payloads and observation history; email-level/conflict/freshness metrics are recomputed over the eligible population.

## Measured impact

[Impact SQL](../sql/medscape_optout_impact.sql) was rendered and executed read-only on October 30, 2026, against the stored canonical Medscape population and currently staged opt-outs:

| Measure | Count |
|---|---:|
| Stored Medscape metric rows before exclusion | 47,072,262 |
| Rows matching opt-out NPIs | 1,859 (0.00394925%) |
| Rows remaining | 47,070,403 |
| Matched distinct NPIs | 169 |
| Matched distinct emails | 270 |
| Matched distinct email–NPI links | 270 |

These are dated measurements of the complete pre-rebuild population at canonical snapshot `8096642935433856886`, not a completed raw-source rebuild or a measurement of business reach. The default impact template now reads the complete current table, whose Medscape records already exclude opted-out NPIs. Reproducing this baseline requires overriding its canonical relation with the pinned pre-rebuild snapshot. Distinct emails may also have eligible records; 270 does not mean all evidence for those emails disappears. The previously measured vendor specialty/profession populations predate this exclusion.

## Validation and publication

At the opt-out validation checkpoint, all 86 local tests passed. The latest complete suite passed 120 tests, including subsequent history and publication controls. The final Medscape model passed native distributed planning with 144 fragments, below Trino’s 150-stage limit. HealthLink also passed replanning with 141 fragments. The remaining fresh vendor-plan checks were stopped while resource-queued; their earlier plan counts remain historical checkpoints. Vendor-label conflict contexts use one narrow per-email observation window to avoid repeated linkage scans, with all-vendor results checked by independent local integrity tests.

Local and native Trino fixtures cover duplicated/null/blank NPIs, missing/invalid/future dates, cumulative removal across observation days, unaffected vendors and unchanged staging row counts. They verify recomputed multiplicity, conflict, freshness and stability context, plus preserved grain for surviving records. An independent [integrity query](../tests/medscape_optout.sql) rejects any opted-out Medscape NPI in stored outputs. The default candidate flow checks before replacement, while direct builds check after all source appends.

Current intermediate views and the complete canonical publication include this exclusion. Native core validation found no excluded NPI in the rebuilt Medscape population using pinned opt-out snapshot `4503450222412661359`. Final enrichment preserved all core values. The complete email lookup reads stored rows and applies no separate opt-out join. Native impact results stay in stdout; only selected aggregate evidence is retained here.
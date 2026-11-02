# Medscape NPI opt-out exclusion

**Status:** Medscape’s intermediate model excludes every cleaned NPI present in `iceberg.thirdparty.medscape_npi_optout`.

## Eligibility rule

`stg_medscape__optout` preserves all raw deliveries and adds trimmed `npi_clean`. Intermediate `global_versions` applies the exclusion before version grouping, email eligibility, link collapse, multiplicity, conflict, name, geography, freshness, stability and vendor-label calculations. Stored core unions eligible vendor outputs before downstream cookie enrichment.

The [record-version macro](../macros/record_versions.sql) joins only the staged opt-out NPI column and keeps unmatched records:

```sql
LEFT JOIN (SELECT npi_clean FROM pii__stg_medscape__optout) excluded
    ON s.npi_clean = excluded.npi_clean
WHERE excluded.npi_clean IS NULL
```

The model’s actual `ref()` resolves to `iceberg.jteixeira_ipa.pii__stg_medscape__optout`. Duplicate opt-outs cannot multiply surviving versions. Null/blank opt-out NPIs cannot exclude unrelated nonempty keys. All retained opt-out rows contribute, regardless of delivery/opt-out date validity or chronology, matching Forge’s cumulative NPI exclusion policy. An opt-out can therefore remove older attribution history; this does not reconstruct historical opt-out timing.

Staging remains row-preserving. Other vendors keep their own eligibility rules. Surviving versions keep their identifiers, payloads and observation history; links and email-level/conflict/freshness metrics are computed over the eligible population only.

## Measured impact

[Impact SQL](../sql/medscape_optout_impact.sql) measures how many stored Medscape links match currently staged opt-out NPIs. Because the stored table already excludes them, the default template should find none; measuring the population before exclusion requires overriding its canonical relation with a table built without the exclusion. No impact measurement exists for this definition.

## Validation

Local and native Trino fixtures cover duplicated/null/blank NPIs, missing/invalid/future dates, cumulative removal across observation days, unaffected vendors and unchanged staging row counts. They verify recomputed multiplicity, conflict, freshness and stability context, plus preserved grain for surviving links. An independent [integrity query](../tests/medscape_optout.sql) rejects any opted-out Medscape NPI in stored outputs. The default candidate flow checks before replacement, while direct builds check after all source appends. [Email-batch builds](build_recovery.md) pin the opt-out snapshot together with the Medscape global and metadata inputs.

The complete email lookup reads stored rows and applies no separate opt-out join. Native impact results stay in stdout; only selected aggregate evidence belongs here.

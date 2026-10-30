# NPI validity and entity type — validated candidate

Metric 22 is implemented and its candidate is ready for publication. **The canonical table and vendor views have not changed.** `iceberg.jteixeira_ipa.pii_clean` retains 114 columns at snapshot `8096642935433856886`. The candidate has **126 columns and 75,564,265 records**. Publication will append twelve fields, retain every record and existing value, and expand the complete email lookup from 120 to 132 outputs.

## Inputs and preservation

- Canonical input: `iceberg.jteixeira_ipa.pii_clean FOR VERSION AS OF 8096642935433856886`.
- Registry input: `iceberg.npi.nppes_npidata_latest FOR VERSION AS OF 4824930614863268861`.
- Materialized NPI lookup: `iceberg.jteixeira_ipa.pii_clean_npi_identity_39b808aed2af`, snapshot `650166003218247767`.
- Validated candidate: `iceberg.jteixeira_ipa.pii_clean_candidate_npi_identity_39b808aed2af`, snapshot `2593466519988720108`.

The lookup evaluates each distinct stored NPI and aggregates raw NPPES entity codes before joining to records. It uses explicit equality keys so Trino can hash identifier matches while distinguishing null from empty input. The NPI lookup materialized in 21 seconds. Seven vendor batches attach its fields to the same pinned canonical snapshot. Candidate writes use query-scoped limits of eight writer tasks and one writer per task.

Existing 108-field checksums and keyed six-field stability checksums were reused only after verifying the canonical snapshot matches the completed stability publication. Candidate checksums match those verified values for every vendor, including `computed_at` and previous reference/evaluation dates. Per-vendor record counts match and record keys remain unique. A separate keyed checksum covers the twelve new fields for subsequent publication verification. Source records and prior reference enrichment were not recomputed.

## Validation

- 73 local tests passed, including missing and malformed identifiers, trailing newlines, prefixed Luhn checks, duplicate/missing/conflicting entity codes, preservation and independent corruption detection.
- Native Trino fixtures passed for the metric, independent invariant and statistics.
- All seven vendor plans passed with 106–134 fragments, below the 150-stage limit. A full raw-source rebuild was not executed.
- All fourteen native candidate integrity checks passed.
- All 30 statistics statements and 18 profile templates passed native semantic validation against the new schema.
- Candidate statistics ran without an output limit. Their three distributions each account for all 75,564,265 records across seven vendors.
- Native lookup fixtures preserved all 126 fields and six helpers. A complete lookup against the candidate returned 1 record with 132 outputs in 9.82 seconds. Individual identifiers and lookup values were not retained.

See [definitions and vendor statistics](../../docs/metrics/22_npi_identity.md), [standalone statistics SQL](../../sql/statistics/22_npi_identity.sql) and [lookup reference](../../docs/email_lookup.md). Query results and operational checkpoints were inspected in memory/stdout, with selected findings retained here.

## Publication and compatibility

Publication requires replacing `iceberg.jteixeira_ipa.pii_clean` with the validated candidate and updating the seven `pii__int_<vendor>__metrics` views. Before replacement, verify that the canonical and candidate snapshots still match the identifiers above. Recheck published schema, counts, keys and all field checksums afterward.

Existing named-column queries retain their values. Fixed-width `SELECT *` consumers must accept twelve appended fields. The prepared complete lookup and metric 22 statistics require the new schema, or an explicit candidate-table substitution until publication. Structural validity does not prove issuance, entity type does not establish email ownership, and lifecycle status remains a separate metric. No scoring, identifier repairs or row filters are introduced.

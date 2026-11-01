# Build recovery and verified publication

**Published and verified, October 31, 2026:** final snapshot `4233051104478921549` contains 75,656,369 records across seven sources and 158 fields. Source-scoped cookie enrichment preserved all 128 fields from core snapshot `3003274000539755025`, including stored name explanations. Both cookie inputs cover October 28–30 with all three days present. See [stored name evidence](name_match_evidence.md) for recovery and validation details.

## Stored names and source-scoped cookies — October 31, 2026

Core snapshot `3003274000539755025` contains 75,656,369 records and 128 fields. It preserves every original core field, key and source count, including `computed_at`. Full reconstruction found zero differences in the existing name indicators, usability flags or source-name arrays. Stored-name integrity passed over the complete population. Query `20261031_184611_47122_6efcm` published core in 1,005.43 seconds. Name comparisons use NPI-reference snapshot `2149991209070307144` and evaluation timestamp `2026-10-31 18:46:11.738 UTC`.

The source-scoped cookie publisher reads that verified core. It pins LiveIntent snapshot `844438291382994861`, geography `3696066139659628990` and ZIP3 mapping `7123669604605367079`. Evaluation day is October 31, with October 28–30 covered in both cookie inputs: three available days and no missing-day flags. Each source is filtered before cookie calculation. Thirty cookie fields are recomputed; all 128 core fields must remain identical.

All seven source writes completed without retry. Each source passed 128-field preservation, complete counts, unique-key checks and cookie integrity before the next source started:

| Source | Records | Committed snapshot | Write query | Minutes |
|---|---:|---|---|---:|
| HealthLink | 11,156,016 | `720901398691810994` | `20261031_205724_51378_6efcm` | 8.03 |
| QuantumMedica | 1,705,723 | `1661377579457959310` | `20261031_210619_51593_6efcm` | 2.64 |
| Medscape | 47,164,366 | `1649545757546135012` | `20261031_210933_51656_6efcm` | 30.39 |
| Endato | 5,427,459 | `6020568208386004321` | `20261031_214323_52932_6efcm` | 3.06 |
| RocketReach | 4,864,145 | `9046938604591700148` | `20261031_214704_53017_6efcm` | 4.12 |
| DRDB | 1,115,415 | `4339068729856760244` | `20261031_215149_53106_6efcm` | 1.92 |
| Haymarket | 4,223,245 | `4233051104478921549` | `20261031_215421_53180_6efcm` | 3.49 |

Final snapshot `4233051104478921549` contains all 75,656,369 records and 158 fields. Full-population preservation passed in 349.01 seconds as query `20261031_215810_53267_6efcm`; cookie integrity passed in 14.55 seconds. The cookie view was refreshed, the incomplete marker was cleared, and the publisher exited successfully. All 128 core fields remain identical to core snapshot `3003274000539755025`. The thirty cookie fields were recomputed from the pinned three-day inputs.

Medscape's write produced 16,582,369,877 bytes. Its individual preservation and cookie checks took 170.66 and 10.82 seconds. Timings describe this execution and are not runtime guarantees. Ordinary refresh or interrupted-source recovery uses `tools/pipeline.py cookies`; incomplete checkpoints retain original snapshot pins, window and coverage.

The current local suite passed all 141 tests in 293.70 seconds. Native Trino verified equivalence of combined and separate cookie calculations on 36 synthetic records, with zero differences. All seven source plans passed at 20 fragments each. Dependency validation confirms 26 project relations, 20 external inputs and 83 direct edges.

## Original core/cookie publication

**Verified October 31, 2026:** `iceberg.jteixeira_ipa.pii_clean` contained **75,656,369 records across all seven sources**, with 154 fields, at snapshot `8811920360682490090`. Core snapshot `2198246156417274278` contains the same records and 124 fields. Final enrichment preserved every core field, including `computed_at`, with identical per-source checksums and no duplicate keys. Cookie integrity checks passed.

The cookie window is October 28–30, three completed calendar days before evaluation. At that evaluation, mapping and geography inputs contained October 28–29 and lacked October 30. Those stored rows retain the missing date and `missing_source_days` status. The window was not extended to compensate for missing data.

Large Medscape writes repeatedly failed with HDFS replica-allocation errors. The recovery path bounds both writer concurrency and transaction size while preserving each email's full observation history. It writes directly into the stored core, `iceberg.jteixeira_ipa.pii__int_pii__metrics`.

## Email batches

`tools/build_medscape_batches.py` partitions normalized email addresses using the first hexadecimal character of SHA-256, producing sixteen disjoint batches. Filtering occurs before exact-record grouping. All NPIs, registration GUIDs, record variants and observation dates for an email remain together. Sequential swaps, flip-backs, opt-out effects and registration supersession therefore retain their full context.

Source-relative freshness needs one extra safeguard: every batch uses the latest eligible observation day from the entire Medscape source. A batch containing older emails cannot redefine the source's latest day. All evaluation dates are fixed for the run.

The runner pins Medscape global, metadata and opt-out Iceberg snapshots. It computes expected record counts, distinct keys and key/history checksums from eligible raw records. An existing batch is retained only when it matches that complete expected population. Each INSERT is atomic. Following a write error, committed rows are inspected before retrying, preventing duplicate insertion after an uncertain client result. Mismatched or incomplete existing batches stop the runner. A table-comment marker blocks ordinary core resume and final publication while email batches are incomplete. It is cleared only after complete expected coverage is verified.

Shared external reference tables are read through the normal metric definitions. They are not all snapshot-pinned by this recovery tool. If they change between batches, reference evidence may differ by build time. Stored evaluation dates and provenance remain available.

## Commands

The core table must match the current 128-field schema. Historical 124-field cores require the [name-evidence upgrade](name_match_evidence.md) or a complete source refresh before resuming; do not fill new evidence fields with placeholders. Stored core has completed that upgrade. The execution evidence below describes the completed 124-field recovery. From `vendor_quality_measurement/pii_clean`:

```bash
../../.venv/bin/python tools/build_medscape_batches.py --day 2026-10-30 --materialize-records
```

Repeat the command to resume after inspecting a failure. `--batches 0123` limits execution to selected hash buckets. The runner always checks expected source history before retaining committed buckets. It prints checkpoints and validation results without saving local result files.

After all sixteen Medscape buckets and the six other sources are complete, validate the stored core and publish final cookie enrichment:

```bash
../../.venv/bin/python tools/pipeline.py core --direct --resume
../../.venv/bin/python tools/pipeline.py final
```

The first command retains complete source batches and runs core integrity checks. Run the email-batch tool before this command whenever Medscape is partial. Ordinary source-level resume cannot prove that partial Medscape batches are complete.

Writer settings are eight writer tasks, one writer per task, local writer scaling disabled, and a 64 MB target data-file size. The file-size setting is a target rather than a strict upper bound. Upstream computation remains distributed. These settings reduce write pressure but cannot repair unhealthy HDFS storage.

## Core and final separation

Completed core rows can be recovered from an explicitly pinned, already validated publication by projecting every non-cookie field required by the current contract. The historical 124-field recovery below cannot supply the four additional name-explanation fields. Recovery must compare counts, unique keys and all-field checksums against that snapshot. Existing cookie values are not copied into core.

Final cookie enrichment uses the default three completed days and produces actual 158-field rows under the current contract; the dated publication below has 154 fields. A failed cookie build leaves core available for retry. See [cookie workflow](cookie_stage.md) and the execution evidence below.

## Reusable exact-record input

The raw Medscape global feed contains 1,046,958,615 observations. Native query diagnostics showed eleven scans of that feed in each full metric batch, with 673.67 GB of physical input per batch. A stored exact-record input groups those observations once, applies cumulative NPI opt-outs and retains original record fields, payloads and exact observation-day arrays. It is an execution input, not a second copy of final enriched metrics.

Use `--materialize-records` to create this execution input during a new run, or pass an existing owned-schema table with `--versioned-input`. Before using it, the batch runner compares every expected key/history checksum to freshly grouped pinned raw inputs. The normal metric model remains available without this optional input. Local equivalence checks compare every core field except query-time `computed_at` between raw and stored-version execution.

## Original core recovery evidence

The six completed source batches were recovered from canonical snapshot `2626250323108905113`. All **28,492,003 records**, unique keys and **124-field checksums** match, including `computed_at`. Writes used eight writer tasks, one writer per task and 64 MB target files.

Medscape inputs are pinned to global snapshot `7639075655973237474`, metadata snapshot `7203470042741170390` and opt-out snapshot `4503450222412661359`. Eligible exact-record grouping found **47,164,366 records**, with no duplicate metric keys, and latest observation day October 29, 2026. This is newer than the historical candidate population. The verified combined core population is **75,656,369 records**. Medscape metrics use October 30 evaluation dates throughout this run.

The first six email buckets committed and matched their expected raw-history checksums:

| Bucket | Records | INSERT query | Seconds |
|---|---:|---|---:|
| 0 | 2,939,188 | `20261030_225146_63059_6efcm` | 104.10 |
| 1 | 2,945,520 | `20261030_225344_63105_6efcm` | 99.19 |
| 2 | 2,960,615 | `20261030_225549_63146_6efcm` | 120.57 |
| 3 | 2,954,150 | `20261030_225804_63201_6efcm` | 238.14 |
| 4 | 2,939,865 | `20261030_230227_63294_6efcm` | 193.57 |
| 5 | 2,946,126 | `20261030_230600_63342_6efcm` | 174.73 |

All sixteen Medscape buckets committed and matched their expected raw-history checksums, for 47,164,366 records. Together with the six recovered sources, stored core snapshot `2198246156417274278` contains 75,656,369 records. Six-source preservation checks and all sixteen native core integrity checks on Medscape passed. The completion marker was cleared only after these checks. Cookie publication is a separate downstream operation over this pinned core snapshot.

The complete local suite passed 120 tests, including stored-version execution. The affected publication suite passed another 18 checks after snapshot/concurrency and incomplete-batch safeguards. The storage audit found zero prohibited artifacts and Source SQL formatting checks found zero violations. Git hooks use `.githooks`.

Reusable input `iceberg.jteixeira_ipa.pii_medscape_versions_4721bed4abb8` committed successfully in 285.28 seconds with a five-fragment plan. The first six Medscape buckets were verified before switching execution to this input. Bucket 5 completed as query `20261030_230600_63342_6efcm`, with 2,946,126 records in 174.73 seconds. The redundant raw-scan query for bucket 6, `20261030_230920_63368_6efcm`, was cancelled before resuming from stored versions. Committed buckets remain subject to checksum validation on resume.

The original snapshot `8811920360682490090` confirms the October 28–30 window, two available days in each input and October 30 missing from both at its evaluation. Date presence measures available partitions, not complete ingestion or independent observations.

The first stored-input batch, bucket 6, committed and verified 2,933,801 records. Query `20261030_231336_63436_6efcm` took 77.30 seconds, read **30.25 GB** and wrote **601.25 MB**. Native query inputs contained **zero scans of `medscape_pii_global`**. Compared with the 673.67 GB raw-batch input, this reduces physical input by approximately **95.5%**. The distributed plan has 74 fragments instead of 96.

All sixteen Medscape buckets were verified complete after query `20261030_232725_64207_6efcm`. The final bucket INSERT was `20261030_232621_64192_6efcm`, completing in 58.91 seconds. The continuation independently rechecked the complete raw-history population and passed all sixteen Medscape core integrity checks before final cookie enrichment.

Preservation checks must use ordinary read-session aggregation planning. A diagnostic comparison showed that forcing `distinct_aggregations_strategy=single_step` on a wide per-source checksum removed distributed partial aggregation and concentrated the check by source. Query `20261030_232835_64236_6efcm` was cancelled as a read-only bottleneck, and verification was restarted with the normal distributed read plan. Writer bounds remain query-scoped to writes. The regular `pipeline.py` validation helper already uses ordinary read sessions.

Complete Medscape core measurements found 3,550,359 dated emails, including 3,500,157 with sufficient history, 109,280 with at least one swap (3.0780%) and 13 with at least one flip-back (0.0003662%). Registration-grain measurements found 109,120 superseded links and 3,551,648 latest-observed links. These counts use different units: source/email for sequence metrics, and GUID/email/NPI/status for registration metrics. The existing `fangchenmd@gmail.com` flip-back and `sbrooks.arnp@gmail.com` supersession examples were reproduced from stored core without rebuilding vendor history.

## Final publication checks

These checks describe the original cookie refresh before the name-evidence upgrade.

Query `20261030_234252_64647_6efcm` published the actual 154-field cookie-enriched table on its first attempt. Its 25-fragment plan finished in 16.92 minutes, reading 391.48 GB and writing 19.41 GB (decimal units), with no HDFS failure. The full 124-field preservation query passed in 104.83 seconds; the cookie invariant query returned no failures in 20.99 seconds. The core snapshot remained unchanged. The publication worker exited successfully.

Direct queries of final snapshot `8811920360682490090` verified these populations:

| Source | Metric records | Distinct emails | Distinct email/NPI links |
|---|---:|---:|---:|
| drdb | 1,115,415 | 819,454 | 826,886 |
| endato | 5,427,459 | 5,324,318 | 5,427,459 |
| haymarket | 4,223,245 | 4,223,245 | 4,223,245 |
| healthlink | 11,156,016 | 7,688,331 | 7,688,451 |
| medscape | 47,164,366 | 3,550,359 | 3,659,659 |
| quantummedica | 1,705,723 | 1,705,695 | 1,705,723 |
| rocketreach | 4,864,145 | 3,163,679 | 3,199,535 |

Email counts overlap between sources and must not be summed as globally distinct emails. Registration-grain counts additionally include GUID and are a different unit from the email/NPI links above.

The [stored sequence summaries](../sql/examples/25_sequential_history_medscape_published.sql), [daily transitions](../sql/examples/25_sequential_history_medscape_daily_published.sql) and [registration outcomes](../sql/examples/26_registration_supersession_published.sql) passed native execution against this final snapshot. Full 160-column lookup execution returned 21 records for `sbrooks.arnp@gmail.com` (17 Medscape, three HealthLink, one DRDB) in 5.57 seconds and eight records for `fangchenmd@gmail.com` (five Medscape, two HealthLink, one Haymarket) in 5.03 seconds. These selected lookup timings do not establish performance for every email. Final-table population profiles reproduced the sequence and registration counts above.

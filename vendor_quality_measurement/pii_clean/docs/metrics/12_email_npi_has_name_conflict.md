# Email–NPI name conflict

**Principle:** flag incompatible usable names reported for the same vendor/email/NPI across retained history. The result applies to every metric row for that link, including earlier or nameless records.

**Where:** `iceberg.jteixeira_ipa.pii__int_<vendor>__metrics` and `iceberg.jteixeira_ipa.pii_clean`. Inputs: `source`, `email`, `npi`, `source_name_values`. Output: nullable boolean `email_npi_has_name_conflict`.

## How it is computed

Collect distinct usable names within `source`, `email`, `npi` into `pair_names`. Compare every pair. In this excerpt, `has_disagreeing_pair` means at least one pair fails the fuzzy first/last-name rules below; it is false when there is only one name or all pairs agree.

```sql
CASE WHEN cardinality(pair_names) = 0 THEN NULL
     ELSE has_disagreeing_pair
END AS email_npi_has_name_conflict
```

Both first and last names must agree under [metric 07's fuzzy rules](07_vendor_name_matches_registry_name.md): nicknames, shared tokens, permitted first-name prefixes and small spelling differences. First-name-only agreement is insufficient. Missing/partial names do not create disagreement; registry names never fill missing vendor names.

Every pair is checked: the compound surname in the third example cannot hide disagreement between SMITH and JONES. Different names attached only to different NPIs do not create this flag. The separate `has_conflict_linkage` metric checks competing NPIs at the observation time or within current undated vendor data.

HealthLink uses its retained HCP names without date alignment. This metric includes historical name changes; a true result does not establish an incorrect identity. Vendor partitions and existing metric rows remain separate.

## Real examples: contrasting outcomes

Selected real records, queried October 30, 2026, from `iceberg.jteixeira_ipa.pii_clean` at snapshot `8096642935433856886`. These examples explain outcomes; they are not prevalence estimates. `email_key` is a shortened SHA-256 label. `link_names` collects distinct normalized vendor pairs for this source/email/NPI, without filling from registry names.

[Runnable example SQL](../../sql/examples/12_email_npi_has_name_conflict.sql):

```sql
WITH selected AS (
    SELECT *
    FROM iceberg.jteixeira_ipa.pii_clean FOR VERSION AS OF 8096642935433856886
    WHERE (source = 'drdb' AND metric_row_id IN (
        '76F42EB2F2C6093316B5CDEF2587E5A52525DDC28EA8CF1B437507091D8AF857',
        '79F6E827954FADE1457B94E8CB35408A2927D2280745D63CDC9CD2A33FD0696E'))
       OR (source = 'quantummedica' AND metric_row_id IN (
        '213F802895D91A49015A7538C13C00FF8712BFA5CFE8584EE9CD7E96622024D2'))
), context_names AS (
    SELECT t.source, t.email, t.npi,
           array_sort(array_distinct(flatten(array_agg(transform(t.source_name_values, n -> concat(n.first_name, ' ', n.last_name)))))) AS names
    FROM iceberg.jteixeira_ipa.pii_clean FOR VERSION AS OF 8096642935433856886 t
    JOIN (SELECT DISTINCT source, email, npi FROM selected) k
      ON t.source = k.source AND t.email = k.email AND t.npi = k.npi
    GROUP BY t.source, t.email, t.npi
)
SELECT m.source,
       substr(to_hex(sha256(to_utf8(m.email))), 1, 12) AS email_key,
       m.email_npi_count,
       c.names AS link_names,
       m.email_npi_has_name_conflict
FROM selected m
LEFT JOIN context_names c ON m.source = c.source AND m.email = c.email AND m.npi = c.npi
ORDER BY m.source, m.metric_row_id
```

**Result:** 3 rows.

| source | email_key | email_npi_count | link_names | email_npi_has_name_conflict |
|---|---|---|---|---|
| drdb | 6B7B55A02822 | 1 | [KEITH LONG, KEITHLINTON LONG] | false |
| drdb | B626A92C528B | 1 | [RICHARD JR, RICHARD SALZER] | true |
| quantummedica | 857355DB1D7B | 1 | [] | NULL |

**What differentiates these cases:** Multiple spellings can remain compatible under fuzzy matching. An incompatible pair on the same vendor/email/NPI gives true. No usable names leaves NULL, rather than false. The result belongs to the link history, not only the selected record. In the RICHARD JR/SALZER example, JR is treated as a last name; this flag compares parsed name pairs rather than proving that two people share the email.

Stored indicators are unchanged by display helpers. Reproduction requires the pinned snapshot to remain available.

## Statistics by vendor

[Statistics SQL](../../sql/statistics/12_email_npi_has_name_conflict.sql) was executed against the current published `iceberg.jteixeira_ipa.pii_clean` table.

Measured **October 29, 2026**, across all retained source history. Extraction completed at `2026-10-29T17:20:39.136145+01:00`. Published snapshot `6346435822181920647` remained unchanged throughout the six-query refresh. Counts are exact. Link percentages use distinct vendor/email/NPI links. Row percentages use that vendor’s metric rows. Reporting link counts does not deduplicate metric output.

| Vendor | Distinct email–NPI links | Conflicting links, n (%) | Unknown links, n (%) | Conflicting metric rows, n (%) |
|---|---:|---:|---:|---:|
| HealthLink | 7,688,451 | 51 (0.00066%) | 515 (0.00670%) | 73 (0.00065%) |
| QuantumMedica | 1,705,723 | 0 (0.00000%) | 1,705,722 (99.99994%) | 0 (0.00000%) |
| Medscape | 3,659,306 | 2,883 (0.07879%) | 44,709 (1.22179%) | 76,913 (0.16339%) |
| Endato | 5,427,459 | 0 (0.00000%) | 222 (0.00409%) | 0 (0.00000%) |
| RocketReach | 3,199,535 | 0 (0.00000%) | 1,958 (0.06120%) | 0 (0.00000%) |
| DRDB | 826,886 | 10,781 (1.30381%) | 62 (0.00750%) | 23,227 (2.08236%) |
| Haymarket | 4,223,245 | 0 (0.00000%) | 191,914 (4.54423%) | 0 (0.00000%) |

QuantumMedica has usable vendor names for only one link; almost all its outcomes are unknown. Zero conflicts in Endato or RocketReach does not imply that each email belongs to one NPI: this metric compares names within the same email–NPI link.

Current measured counts, executed SQL and snapshot checks (historical output, not retained: `../../results/published_metric_refresh_20261029.json`) · Native validation and field-preservation checks (historical output, not retained: `../../results/name_consistency_native_validation.json`)

[Profile SQL](../../sql/name_consistency_profile.sql) · [Independent pairwise check](../../tests/name_consistency.sql) · [Rules](../../macros/name_consistency.sql) · [Name count](11_email_name_count.md)

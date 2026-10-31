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

## Real examples

Executed October 31, 2026, against canonical snapshot `8811920360682490090`. These selected cases explain outcomes; they do not measure prevalence.

[Executed example SQL](../../sql/examples/12_email_npi_has_name_conflict.sql):

```sql
WITH selected AS (
    SELECT *
    FROM iceberg.jteixeira_ipa.pii_clean FOR VERSION AS OF 8811920360682490090
    WHERE (source = 'drdb' AND metric_row_id IN (
        '76F42EB2F2C6093316B5CDEF2587E5A52525DDC28EA8CF1B437507091D8AF857',
        '79F6E827954FADE1457B94E8CB35408A2927D2280745D63CDC9CD2A33FD0696E'))
       OR (source = 'quantummedica' AND metric_row_id IN (
        '213F802895D91A49015A7538C13C00FF8712BFA5CFE8584EE9CD7E96622024D2'))
), context_names AS (
    SELECT t.source, t.email, t.npi,
           array_sort(array_distinct(flatten(array_agg(transform(t.source_name_values, n -> concat(n.first_name, ' ', n.last_name)))))) AS names
    FROM iceberg.jteixeira_ipa.pii_clean FOR VERSION AS OF 8811920360682490090 t
    JOIN (SELECT DISTINCT source, email, npi FROM selected) k
      ON t.source = k.source AND t.email = k.email AND t.npi = k.npi
    GROUP BY t.source, t.email, t.npi
)
SELECT m.source,
       m.email,
       m.npi,
       m.email_npi_count,
       c.names AS link_names,
       m.email_npi_has_name_conflict
FROM selected m
LEFT JOIN context_names c ON m.source = c.source AND m.email = c.email AND m.npi = c.npi
ORDER BY m.source, m.metric_row_id
```

| source | email | npi | email_npi_count | link_names | email_npi_has_name_conflict |
|---|---|---|---|---|---|
| drdb | klong.md@verizon.net | 1467487439 | 1 | [KEITH LONG, KEITHLINTON LONG] | false |
| drdb | rsalzerjr@gmail.com | 1508810300 | 1 | [RICHARD JR, RICHARD SALZER] | true |
| quantummedica | jamesnikolakakis@clinical-assoc.com | 1801968805 | 1 | [] | NULL |

**What differentiates these cases:** Multiple spellings can remain compatible under fuzzy matching. An incompatible pair on the same vendor/email/NPI gives true. No usable names leaves NULL, rather than false. The result belongs to the link history, not only the selected record. In the RICHARD JR/SALZER example, JR is treated as a last name; this flag compares parsed name pairs rather than proving that two people share the email.

## Statistics by source

Measured **October 31, 2026** from `iceberg.jteixeira_ipa.pii_clean` snapshot `8811920360682490090`. These are exact published-population counts across retained eligible history, not a sample. Stored evaluation dates remain unchanged.

[Executed statistics SQL](../../sql/statistics/12_email_npi_has_name_conflict.sql)

| Source | Distinct email/NPI links | Conflicting links, n (%) | Unknown links, n (%) | Conflicting records, n (%) |
|---|---|---|---|---|
| HealthLink | 7,688,451 | 51 (0.000663%) | 515 (0.006698%) | 73 (0.000654%) |
| QuantumMedica | 1,705,723 | 0 (0.000000%) | 1,705,722 (99.999941%) | 0 (0.000000%) |
| Medscape | 3,659,659 | 2,883 (0.078778%) | 44,701 (1.221453%) | 77,041 (0.163346%) |
| Endato | 5,427,459 | 0 (0.000000%) | 222 (0.004090%) | 0 (0.000000%) |
| RocketReach | 3,199,535 | 0 (0.000000%) | 1,958 (0.061196%) | 0 (0.000000%) |
| DRDB | 826,886 | 10,781 (1.303807%) | 62 (0.007498%) | 23,227 (2.082364%) |
| Haymarket | 4,223,245 | 0 (0.000000%) | 191,914 (4.544231%) | 0 (0.000000%) |

Link percentages use distinct source/email/NPI links. Record percentages use metric records. A missing usable name pair leaves unknown; conflicting spellings do not prove different people.

# Email matches source name

**Question:** does the email's mailbox text resemble a name supplied by this vendor? A match is name evidence, not proof of ownership.

**Where:** `email_matches_source_name` in `iceberg.jteixeira_ipa.pii__int_<vendor>__metrics`, keyed by `source`, `metric_row_id`. Vendors: `healthlink`, `quantummedica`, `medscape`, `endato`, `rocketreach`, `drdb`, `haymarket`. Inputs and name parsing are listed in the [source map](../00_source_map.md#name-comparison-inputs).

## How it is computed

Normalize each paired first/last name: uppercase, supported accents removed, spaces/hyphens/apostrophes retained; empty, `NULL`, `NaN` and `\N` become missing. Expand first names through the [nickname list](../../seeds/nicknames.csv). Reduce the email mailbox to lowercase letters:

```sql
regexp_replace(lower(regexp_extract(email, '^([^@]*)@', 1)), '[^a-z]', '') AS local_letters
```

For each usable name, compute `source_match` using these rules:

- Both first and last names occur anywhere; each needs two letters.
- Or the local part starts with the first initial and ends with the last name, or the reverse. It must be longer than the last name.
- Or a local part of six or more letters differs by at most one insertion, deletion or substitution from first+last, last+first, initial+last or last+initial.

A usable name needs at least one first-name letter and two last-name letters. `source_name_usable` records availability. Within `source`, `metric_row_id`, any matching comparison gives true; usable comparisons with no match give false; all-null comparisons stay unknown.

```sql
bool_or(source_match) AS email_matches_source_name
```

Names stay paired within their source record. Changed source records stay separate. HealthLink alone attaches distinct HCP-reference names by NPI across retained history, without date alignment. Repeated observations add no weight.

Format validation is separate. RocketReach and DRDB full-name parsing can mistake titles or suffixes for name parts.

## Real examples

Executed October 31, 2026, against canonical snapshot `8811920360682490090`. These selected cases explain outcomes; they do not measure prevalence.

[Executed example SQL](../../sql/examples/05_email_matches_source_name.sql):

```sql
WITH selected AS (
    SELECT *
    FROM iceberg.jteixeira_ipa.pii_clean FOR VERSION AS OF 8811920360682490090
    WHERE (source = 'endato' AND metric_row_id IN (
        '7043AC9E562F5F136D74A9F97D058212CFA121114A1774A885886A4191415F38',
        'FD13E1A91B10E0169EB0E2880202F0C7024D164C9230CC158C3ABC85C2A6101D'))
       OR (source = 'quantummedica' AND metric_row_id IN (
        'D678C06341C0CDE9EE0FE677515A39A66D167424179488066216A273376FC028'))
)
SELECT m.source,
       m.email,
       transform(m.source_name_values, n -> concat(n.first_name, ' ', n.last_name)) AS vendor_names,
       m.source_name_usable,
       m.email_matches_source_name
FROM selected m
ORDER BY m.source, m.metric_row_id
```

| source | email | vendor_names | source_name_usable | email_matches_source_name |
|---|---|---|---|---|
| endato | gtarbour@bellsouth.net | [GERALD ARBOUR] | true | true |
| endato | mrsmiller1987@yahoo.com | [FRANCIS COTTONE] | true | false |
| quantummedica | ehoffman@sunrisehospital.com | [] | false | NULL |

**What differentiates these cases:** `gtarbour` starts with G and ends with ARBOUR, so the initial/surname rule accepts it for GERALD ARBOUR despite the intervening text. A usable nonmatching name gives false. An empty vendor-name array leaves the outcome NULL. Registry evidence never fills the missing vendor name, and mailbox resemblance does not prove ownership.

## Statistics by source

Measured **October 31, 2026** from `iceberg.jteixeira_ipa.pii_clean` snapshot `8811920360682490090`. These are exact published-population counts across retained eligible history, not a sample. Stored evaluation dates remain unchanged.

[Executed statistics SQL](../../sql/statistics/05_email_matches_source_name.sql)

| Source | Metric records | Match, n (%) | No match, n (%) | Unknown, n (%) |
|---|---|---|---|---|
| HealthLink | 11,156,016 | 7,587,293 (68.010776%) | 3,568,038 (31.983084%) | 685 (0.006140%) |
| QuantumMedica | 1,705,723 | 0 (0.000000%) | 1 (0.000059%) | 1,705,722 (99.999941%) |
| Medscape | 47,164,366 | 24,993,116 (52.991523%) | 22,012,109 (46.671059%) | 159,141 (0.337418%) |
| Endato | 5,427,459 | 1,999,756 (36.845161%) | 3,427,481 (63.150749%) | 222 (0.004090%) |
| RocketReach | 4,864,145 | 2,977,399 (61.211148%) | 1,884,149 (38.735461%) | 2,597 (0.053391%) |
| DRDB | 1,115,415 | 788,347 (70.677461%) | 321,591 (28.831511%) | 5,477 (0.491028%) |
| Haymarket | 4,223,245 | 2,528,601 (59.873415%) | 1,502,730 (35.582354%) | 191,914 (4.544231%) |

Percentages use all metric records within each source. Categories partition records. Distinct-email outcomes cannot be inferred by adding record counts. Unknown is NULL, not disagreement. Names and outcomes can differ between records sharing an email/NPI.

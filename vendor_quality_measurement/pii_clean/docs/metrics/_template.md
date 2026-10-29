# [Plain-language concept or metric name]

**Status:** proposed / implemented / measured / reviewed.

**Principle:** explain the question in one or two sentences.

**Where to find it:** give the full output table name (`catalog.schema.table`) and exact column names. Default key: `source`, `metric_row_id` (exact source record and email position). Email–NPI deduplication is deferred. Name the input tables and columns, or link a precise entry in the [source map](../00_source_map.md). Include join keys when needed. Distinguish stored columns from statistics calculated for this page.

## How it is computed

In a few sentences, explain input cleaning, join/grouping keys, history scope and the calculation. Include a short expression when practical:

```sql
some_transformation AS column_name
```

Explain helper values and zero/false/null behavior. Label simplified expressions; link the exact implementation instead of reproducing long SQL. Avoid repeating the same rule in prose, a table and code.

**Examples:** show one normal case and one tricky case. Label invented examples “illustrative”; use reserved example domains. Keep real examples free of unnecessary personal details.

## Statistics by source

Measured on: [date]. Source data period: [range, or source-specific ranges].

| Source | Eligible metric rows | Measurable rows, n (%) | Result or distribution |
|---|---:|---:|---|
| [Every source] | [count] | [count and % of eligible metric rows] | [value] |

Use “not measured,” “not applicable” or “unknown” explicitly. Never replace unavailable statistics with zero. Name thresholds and label approximate statistics.

**Interpretation:** explain what the result tells us, what it cannot establish, and which source differences matter. No weight is implied by coverage alone.

Keep each page around 150–300 words. Prefer everyday language and short sentences. Explain technical terms once. Put detailed SQL and machine-readable results in linked files. The parent README lists every page.

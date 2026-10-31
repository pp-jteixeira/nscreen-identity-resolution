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

## Real examples: contrasting outcomes

Before statistics, show a few real cases that distinguish outcomes or expose limitations. Name the query date, full source relation, row grain and retained snapshot/evaluation date. Select exact record keys when link histories can differ. Include `source` in both SQL and displayed results. Show stored cleaned identifiers unchanged: full `email` for email-only checks, `npi` for NPI-only checks, and both for email–NPI attribution or link-history metrics. Add only attributes that explain the outcome, such as compared names, peer NPIs, states, facilities, taxonomy codes or exact observation/conflict dates. Do not replace relevant identifiers with hashes, masked shapes, mailbox-only text or domain-only text. Keep exact record keys in the SQL rather than widening the result table with technical identifiers. Label display helpers.

For an unpublished metric, query its validated candidate and explicitly state that the examples are not yet from the canonical publication. Illustrative examples may supplement real cases but do not replace this section.

Include the complete executed SELECT in a SQL fence, followed immediately by its small Markdown result table and a brief explanation of the differences. Save a matching runnable SQL copy under `sql/examples/`; do not save CSV, JSON, Parquet or other result dumps. Cover true/false/unknown or category differences when real cases exist. Never invent an unavailable outcome. Distinguish missing evidence from not applicable and note any current, unpinned reference joins.

## Statistics by source

Measured on: [date]. Source data period: [range, or source-specific ranges].

**Statistics SQL:** link a versioned standalone query under `sql/statistics/` that generates the displayed counts and denominators. Distinguish original executed SQL from an equivalent query. State which statement or output section supplies each table, any aggregation/formatting after extraction, and historical relation/date requirements. Calculation macros and integrity tests do not substitute for this statistics query. Keep selected results inline in Markdown. Do not save standalone result extracts or execution logs locally or in Git.

| Source | Eligible metric rows | Measurable rows, n (%) | Result or distribution |
|---|---:|---:|---|
| [Every source] | [count] | [count and % of eligible metric rows] | [value] |

Use “not measured,” “not applicable” or “unknown” explicitly. Never replace unavailable statistics with zero. Name thresholds and label approximate statistics.

**Interpretation:** explain what the result tells us, what it cannot establish, and which source differences matter. No weight is implied by coverage alone.

Keep explanatory prose around 150–300 words where practical, excluding SQL and result tables. Prefer everyday language and short sentences. Explain technical terms once. Link detailed implementation SQL; keep the selected example results inline without machine-readable result exports. The parent README lists every page.

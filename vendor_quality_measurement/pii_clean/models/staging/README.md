# Staging: preserve input rows

Each model reads one input table. Vendor models read all retained history; `stg_npi__reference` reads the current available registry rows. It preserves every original column through `s.*` and adds cleaned helpers for fields currently needed.

Staging performs trimming, lowercasing email values, and safe type conversions. Original values remain available. Blank scalar helpers become null; textual placeholders such as `NULL` are not silently removed. Dates that cannot be parsed become null with `invalid_vendor_day = true`.

There are no filters, joins, unnesting, deduplication, grouping or latest-partition selections. Email-list splitting and combining email slots belong in intermediate. Every input row, including missing keys and malformed values, must survive staging.

For example, [stg_healthlink__email.sql](stg_healthlink__email.sql) reads `iceberg.thirdparty.healthlink_email` and defines view `iceberg.jteixeira_ipa.pii__stg_healthlink__email`. It retains `npi` and `hld_email` while adding `npi_clean` and `email_clean`.

The live staging test compares input and staged row counts. Local fixtures also check preservation of blank keys and original values. Local DuckDB execution uses translated SQL and does not substitute for Trino validation.

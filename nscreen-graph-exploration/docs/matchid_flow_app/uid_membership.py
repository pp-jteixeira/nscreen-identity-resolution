"""Exact UID membership atoms for source stacking and destination overlap."""


def membership_sql(day, source_tables, staged_table, metrics_table):
    inputs = [
        f"SELECT uid, {bit} AS vendor_mask, CAST(NULL AS VARCHAR) AS reason "
        f"FROM {table} WHERE day = '{day}' AND uid IS NOT NULL"
        for bit, (_, table) in zip((1, 2, 4), source_tables.values(), strict=True)
    ]
    inputs.append(f"""SELECT uid, 0, reason FROM {staged_table}
WHERE day = '{day}' AND stage = 'initial' AND uid IS NOT NULL
  AND matchid <> 0
  AND NOT (regexp_like(uid, '^LR_.*$') AND reason = 'IC')
  AND NOT regexp_like(uid, '^[01\\-_!*]*$')""")
    union = "\nUNION ALL\n".join(inputs)
    return f"""INSERT INTO {metrics_table}
WITH membership AS (
    SELECT uid, bitwise_or_agg(vendor_mask) AS mask,
        coalesce(array_agg(DISTINCT reason) FILTER (WHERE reason IS NOT NULL),
                 CAST(ARRAY[] AS ARRAY(VARCHAR))) AS reasons
    FROM ({union}) inputs
    GROUP BY uid
), classified AS (
    SELECT mask,
        CASE WHEN cardinality(reasons) = 0 THEN 'unrepresented'
             WHEN cardinality(reasons) = 1 THEN element_at(reasons, 1)
             ELSE 'multiple_reasons' END AS reason
    FROM membership
)
SELECT '{day}', 'uid_membership', reason, CAST(mask AS VARCHAR),
    count(*), count(*), 'exact', current_timestamp
FROM classified GROUP BY reason, mask"""

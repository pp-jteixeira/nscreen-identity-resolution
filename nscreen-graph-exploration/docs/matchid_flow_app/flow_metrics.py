"""Offline measurements for identity representation and publication.

Representation is based on shared UIDs, not inferred vendor-reason totals.
It does not establish why a UID was removed or prove a causal vendor merge.
"""

GRAPH_TABLES = {
    "graph_clean": "iceberg.crossscreen.nscreen_ipcollocation_daily_clean",
    "graph_remainder": "iceberg.crossscreen.nscreen_ipcollocation_daily_remainder_ex",
}
REPRESENTATION_STATES = ("same_id", "reassigned_only", "unrepresented")


def representation_sql(day, vendor, source_table, staged_table, metrics_table):
    """Classify each source matchid once, using its UIDs in initial output.

    UNION plus UID grouping avoids a many-to-many raw-table join. Reassigned
    means at least one shared UID, but none retains the source matchid.
    """
    return f"""
INSERT INTO {metrics_table}
WITH uid_membership AS (
    SELECT uid,
        array_agg(DISTINCT source_id) FILTER (WHERE source_id IS NOT NULL) AS source_ids,
        array_agg(DISTINCT initial_id) FILTER (WHERE initial_id IS NOT NULL) AS initial_ids
    FROM (
        SELECT uid, CAST(matchid AS VARCHAR) AS source_id,
            CAST(NULL AS VARCHAR) AS initial_id
        FROM {source_table}
        WHERE day = '{day}' AND matchid IS NOT NULL
        UNION ALL
        SELECT uid, CAST(NULL AS VARCHAR), CAST(matchid AS VARCHAR)
        FROM {staged_table}
        WHERE day = '{day}' AND stage = 'initial'
    ) inputs
    GROUP BY uid
), source_membership AS (
    SELECT source_id,
        bool_or(uid IS NOT NULL AND cardinality(initial_ids) > 0) AS represented,
        bool_or(uid IS NOT NULL AND contains(initial_ids, source_id)) AS same_id,
        count(*) AS uid_rows
    FROM uid_membership
    CROSS JOIN UNNEST(source_ids) AS ids(source_id)
    GROUP BY source_id
), classified AS (
    SELECT source_id, uid_rows,
        CASE WHEN same_id THEN 'same_id'
             WHEN represented THEN 'reassigned_only'
             ELSE 'unrepresented' END AS outcome
    FROM source_membership
)
SELECT '{day}', 'vendor_representation', '{vendor}', outcome,
    count(*), sum(uid_rows), 'exact', current_timestamp
FROM classified GROUP BY outcome
""".strip()


def graph_sql(day, group, table, metrics_table):
    """Count distinct endpoint UIDs and relationship rows in one partition."""
    return f"""
INSERT INTO {metrics_table}
WITH counts AS (
    SELECT count(DISTINCT uid) AS uids, count(*) / 2 AS relationships
    FROM {table}
    CROSS JOIN UNNEST(ARRAY[uid1, uid2]) AS endpoints(uid)
    WHERE day = '{day}'
)
SELECT '{day}', 'graph_size', '{group}', measure,
    CAST(NULL AS BIGINT), value, 'exact', current_timestamp
FROM counts
CROSS JOIN UNNEST(ARRAY['uids', 'relationships'], ARRAY[uids, relationships])
    AS measures(measure, value)
""".strip()


def publication_sql(day, staged_table, final_table, metrics_table):
    """Measure each stage's assignment publication by UID and canonical ID.

    Stages overlap in matchid space. Outcomes are distinct within a stage
    and outcome, and must not be summed into a unique final matchid total.
    """
    return f"""
INSERT INTO {metrics_table}
WITH membership AS (
    SELECT uid, matchid,
        array_agg(DISTINCT stage) FILTER (WHERE stage IS NOT NULL) AS stages,
        bool_or(published) AS published
    FROM (
        SELECT uid,
            IF(stable, 'S_' || CAST(matchid AS VARCHAR), CAST(matchid AS VARCHAR)) AS matchid,
            stage, false AS published
        FROM {staged_table}
        WHERE day = '{day}' AND stage IN ('initial', 'stage1', 'stage2', 'louvain')
        UNION ALL
        SELECT uid, CAST(matchid AS VARCHAR), CAST(NULL AS VARCHAR), true
        FROM {final_table} WHERE day = '{day}'
    ) inputs
    GROUP BY uid, matchid
)
SELECT '{day}', 'stage_publication', stage,
    IF(published, 'published', 'not_published'),
    count(DISTINCT matchid), count(*), 'exact', current_timestamp
FROM membership CROSS JOIN UNNEST(stages) AS assignments(stage)
GROUP BY stage, published
""".strip()

"""Narrow, audited Spark-to-Trino adapters; Forge SQL remains authoritative."""

import hashlib
import re
from pathlib import Path

import jinja2
import sqlglot
from sqlglot import exp

INPUTS = (
    "liveramp_source",
    "throtle_source",
    "experian_source",
    "nscreen_ipcollocation_daily_clean",
    "nscreen_geo_daily_ua",
)
STAGED = "nscreen_liveramp_throtle_ex_reason_staged"
REMAINDER = "nscreen_ipcollocation_daily_remainder_ex"
RESULT = "nscreen_lr_throtle_ex_reason_result"
FILES = {
    "lrth": "NScreenLiverampThrotleOnlyStage.sql",
    "initial": "NScreenLiverampThrotleExInitialStage.sql",
    "connected_ns": "NScreenLiverampThrotleExConnectedNsStage.sql",
    "stage1": "NScreenLiverampThrotleExNStage.sql",
    "stage2": "NScreenLiverampThrotleExNStage.sql",
    "remainder": "NScreenIpCollocationDailyExRemainder.sql",
    "louvain": "NScreenExRemainderLouvainStage.sql",
    "result": "NScreenLrThrotleExReasonResult.sql",
}
STAGE_COLUMNS = "uid, matchid, householdid, stable, reason"


def literal(value):
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, str):
        return "'" + value.replace("'", "''") + "'"
    raise TypeError(f"Unsupported SQL literal: {type(value)}")


def identifier(value):
    if not re.fullmatch(r"[a-z][a-z0-9_]*", value):
        raise ValueError(f"Unsafe identifier: {value!r}")
    return value


def qualified_table(value):
    parts = value.split(".")
    if len(parts) != 3:
        raise ValueError(f"Expected catalog.schema.table, got: {value!r}")
    return ".".join(identifier(part) for part in parts)


def versioned_ref(table, snapshot):
    return f"{qualified_table(table)} FOR VERSION AS OF {int(snapshot)}"


def source_hashes(source_root):
    return {
        f: hashlib.sha256((source_root / f).read_bytes()).hexdigest()
        for f in sorted(set(FILES.values()))
    }


def production_ref(table, snapshot):
    return versioned_ref(f"iceberg.crossscreen.{identifier(table)}", snapshot)


def parse_source(root, stage, day):
    template = (Path(root) / FILES[stage]).read_text()
    params = {"day": day, "current_stage": stage}
    rendered = (
        jinja2.Environment(undefined=jinja2.StrictUndefined)
        .from_string(template)
        .render(var=lambda name: params[name])
    )
    return sqlglot.parse_one(rendered, read="spark")


def compile_stage(root, stage, day, refs, mapping_table=None, cluster_table=None):
    """Return (materialized mapping SQL or None, final stage SQL).

    Adapt only known incompatible CTE shapes. Fail on unsupported functions or
    unknown production tables, rather than silently reading unpinned inputs.
    """
    tree = parse_source(root, stage, day)
    ctes = list(tree.ctes)
    by_name = {c.alias: c for c in ctes}

    def require_shape(name, expected):
        reference = sqlglot.parse_one(expected, read="spark")
        candidate = by_name[name].this.copy()
        for node in candidate.walk():
            node.comments = None
        if candidate != reference:
            raise ValueError(
                f"Source {name} changed; review adapter instead of discarding source changes"
            )

    if stage == "connected_ns":
        require_shape(
            "distinct_ns_uids",
            "SELECT DISTINCT explode(array(uid1,uid2)) AS uid "
            "FROM iceberg.crossscreen.nscreen_ipcollocation_daily_clean "
            f"WHERE day={literal(day)}",
        )
        by_name["distinct_ns_uids"].set(
            "this",
            sqlglot.parse_one(
                f"SELECT DISTINCT u.uid FROM iceberg.crossscreen.nscreen_ipcollocation_daily_clean "
                f"CROSS JOIN UNNEST(ARRAY[uid1,uid2]) AS u(uid) WHERE day={literal(day)}",
                read="trino",
            ),
        )
    if stage in ("stage1", "stage2"):
        require_shape(
            "ns_dbl",
            "SELECT inline(array("
            "named_struct('uid1',uid1,'uid2',uid2,'weight',weight),"
            "named_struct('uid1',uid2,'uid2',uid1,'weight',weight))) "
            "FROM iceberg.crossscreen.nscreen_ipcollocation_daily_clean "
            f"WHERE day={literal(day)}",
        )
        by_name["ns_dbl"].set(
            "this",
            sqlglot.parse_one(
                "SELECT u.uid1,u.uid2,u.weight "
                "FROM iceberg.crossscreen.nscreen_ipcollocation_daily_clean "
                "CROSS JOIN UNNEST(ARRAY[ROW(uid1,uid2,weight),ROW(uid2,uid1,weight)]) "
                f"AS u(uid1,uid2,weight) WHERE day={literal(day)}",
                read="trino",
            ),
        )
        # Spark SUM(REAL) produces DOUBLE. Trino SUM(REAL) retains REAL.
        for node in tree.find_all(exp.Sum):
            if node.this.sql() != "weight":
                raise ValueError("Unexpected aggregate; review Spark numeric semantics")
            node.set(
                "this", exp.Cast(this=node.this.copy(), to=exp.DataType.build("DOUBLE"))
            )
    if stage == "louvain":
        if not cluster_table:
            raise ValueError("Clustering output required")
        require_shape(
            "remainder",
            "SELECT uid1,uid2,weight,samedevice,differentusers,geo "
            "FROM iceberg.crossscreen.nscreen_ipcollocation_daily_remainder_ex "
            f"WHERE day={literal(day)}",
        )
        require_shape(
            "raw",
            "SELECT hudf_calc_screen7_ids_udaf(murmur3(uid1),murmur3(uid2),"
            "weight,samedevice,differentusers) AS result_per_geo FROM remainder GROUP BY geo",
        )
        require_shape(
            "inlined",
            "SELECT uidhash,deviceid,matchid,householdid FROM raw "
            "LATERAL VIEW inline(result_per_geo) x AS uidhash,deviceid,matchid,householdid",
        )
        require_shape("all_uids_list", "SELECT array(uid1,uid2) AS uids FROM remainder")
        require_shape(
            "uid_to_hash",
            "SELECT uid,murmur3(uid) AS uidhash FROM all_uids_list "
            "LATERAL VIEW explode(uids) t AS uid GROUP BY uid",
        )
        # Preserve the original global hash join, including collisions across geos.
        # Packed transfer still carries each original uid and its exact Java hash.
        by_name["inlined"].set(
            "this",
            sqlglot.parse_one(
                "SELECT uidhash,deviceid,matchid,householdid FROM "
                f"(SELECT DISTINCT geo,uidhash,deviceid,matchid,householdid FROM {cluster_table})",
                read="trino",
            ),
        )
        by_name["uid_to_hash"].set(
            "this",
            sqlglot.parse_one(
                f"SELECT DISTINCT uid,uidhash FROM {cluster_table}", read="trino"
            ),
        )
        tree.set(
            "with", exp.With(expressions=[by_name["inlined"], by_name["uid_to_hash"]])
        )

    mapping = None
    if stage in ("lrth", "initial"):
        if not mapping_table:
            raise ValueError("Mapping materialization required")
        mapping_cte = by_name["mapping"]
        if "persist_cte" not in mapping_cte.this.sql(dialect="spark").lower():
            raise ValueError("Production mapping materialization changed")
        index = ctes.index(mapping_cte)
        mapping = mapping_cte.this.copy()
        mapping.set("with", exp.With(expressions=[c.copy() for c in ctes[:index]]))
        mapping_cte.set(
            "this", sqlglot.parse_one(f"SELECT * FROM {mapping_table}", read="trino")
        )

    def render(expression):
        for hint in list(expression.find_all(exp.Hint)):
            hint.parent.set("hint", None)
        # Spark takes Boolean MAX; use equivalent boolean aggregate in Trino.
        for node in list(expression.find_all(exp.Max)):
            if isinstance(node.this, exp.Column) and node.this.name == "stable":
                node.replace(
                    exp.Anonymous(this="bool_or", expressions=[node.this.copy()])
                )
        for table in list(expression.find_all(exp.Table)):
            if table.catalog == "iceberg" and table.db == "crossscreen":
                if table.name not in refs:
                    raise ValueError(f"Unmapped production read: {table.name}")
                replacement_query = sqlglot.parse_one(
                    f"SELECT * FROM {refs[table.name]}", read="trino"
                )
                replacement = replacement_query.args["from"].this.copy()
                if table.args.get("alias"):
                    replacement.set("alias", table.args["alias"].copy())
                table.replace(replacement)
        for node in expression.find_all(exp.Anonymous):
            if node.name.lower() in (
                "inline",
                "named_struct",
                "murmur3",
            ) or node.name.lower().startswith("hudf_"):
                raise ValueError(f"Unadapted production function: {node.name}")
        return expression.sql(
            dialect="trino", pretty=True, unsupported_level=sqlglot.ErrorLevel.RAISE
        )

    mapping_sql = render(mapping) if mapping is not None else None
    sql = render(tree)
    cols = (
        STAGE_COLUMNS
        if stage not in ("remainder", "result")
        else (
            "uid1,uid2,weight,samedevice,differentusers,geo"
            if stage == "remainder"
            else "uid,matchid,householdid,reason"
        )
    )
    # common.run overwrites partition columns after evaluating SELECT.
    partition = f", {literal(day)} AS day"
    if stage not in ("remainder", "result"):
        partition += f", {literal(stage)} AS stage"
    return mapping_sql, f"SELECT {cols}{partition}\nFROM (\n{sql}\n) AS source_result"


def multiset_diff(left, right, columns):
    cols = ", ".join(columns)
    return f"""SELECT {cols}, sum(_side) AS delta
FROM (
  SELECT {cols}, CAST(1 AS BIGINT) AS _side FROM ({left}) l
  UNION ALL
  SELECT {cols}, CAST(-1 AS BIGINT) AS _side FROM ({right}) r
) both_sides
GROUP BY {cols}
HAVING sum(_side) <> 0"""


def canonical_result(query):
    """Exact membership-based row representation, preserving row multiplicity.

    Empty/null household labels remain distinct. No hash is used as an equality
    proof; complete sorted member arrays define each nonempty group.
    """
    return f"""WITH data AS ({query}),
matches AS (
 SELECT matchid, array_sort(array_agg(DISTINCT uid)) AS match_members
 FROM data WHERE matchid IS NOT NULL GROUP BY matchid
), households AS (
 SELECT householdid, array_sort(array_agg(DISTINCT uid)) AS household_members
 FROM data WHERE householdid IS NOT NULL AND householdid <> '' GROUP BY householdid
)
SELECT d.uid, m.match_members, h.household_members,
 CASE WHEN d.matchid IS NULL THEN 'null' ELSE 'group' END AS match_kind,
 CASE WHEN d.householdid IS NULL THEN 'null' WHEN d.householdid='' THEN 'empty'
 ELSE 'group' END AS household_kind, d.reason
FROM data d
LEFT JOIN matches m ON d.matchid=m.matchid
LEFT JOIN households h ON d.householdid=h.householdid"""

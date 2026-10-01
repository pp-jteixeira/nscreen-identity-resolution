"""Run the repository SQL against the fixed collocation fixture with local Spark.

Use the Forge Python environment (pyspark), with JAVA_HOME pointing to a JDK.
The fixture already uses normalized IPv4; its UA lookup is empty. Only these
UDF boundary results are stubbed. SQL joins, filters, sums, counts and ranks run
from the repository files, not from the Python walkthrough implementation.
"""

from collocation_example import DAY, OBSERVATIONS, PIXELS, SQL_ROOT, build_collocation_steps
from example import REPO_ROOT
from pyspark.sql import SparkSession

TABLES = {
    "iceberg.fact.visitorlogevent": "visitor_events",
    "iceberg.fact.recordingpixellogevent": "pixel_events",
    "iceberg.crossscreen.nscreen_raw_hourly": "raw_hourly",
    "iceberg.crossscreen.nscreen_ua_hourly": "ua_hourly",
    "iceberg.crossscreen.nscreen_ipcolocation_hourly_ua": "ip_hourly",
    "iceberg.crossscreen.nscreen_ipcolocation_daily_ua": "ip_daily",
    "iceberg.crossscreen.nscreen_ipcolocation_daily_all_ua": "ip_all",
    "iceberg.crossscreen.nscreen_1p_collocation_hourly": "fp_hourly",
    "iceberg.crossscreen.nscreen_1p_collocation_daily": "fp_daily",
}
PAIR_SCHEMA = "uid1 string, uid2 string, weight double, samedevice boolean, differentusers boolean"


def verify():
    spark = (
        SparkSession.builder.master("local[2]")
        .appName("collocation-example-check")
        .config("spark.ui.enabled", "false")
        .config("spark.sql.shuffle.partitions", "2")
        .getOrCreate()
    )
    spark.sparkContext.setLogLevel("ERROR")
    spark.udf.register("hudf_normalize_ip_address", lambda ip: ip, "string")
    spark.udf.register("hudf_is_same_device", lambda *_args: False, "boolean")
    spark.udf.register("hudf_different_users", lambda *_args: False, "boolean")

    def table(name, rows, schema):
        spark.createDataFrame(rows, schema).createOrReplaceTempView(name)

    def sql(file, **params):
        query = (REPO_ROOT / SQL_ROOT / file).read_text()
        for key, value in params.items():
            query = query.replace("{{ var('" + key + "') }}", value)
        for source, view in TABLES.items():
            query = query.replace(source, view)
        return [row.asDict() for row in spark.sql(query).collect()]

    def same(actual, expected, keys):
        assert sorted(tuple(row[k] for k in keys) for row in actual) == sorted(
            tuple(row[k] for k in keys) for row in expected
        ), keys

    events = [
        dict(row, visitorguid=row["uid"], deviceid=None, eids="", country="USA", postalcode="10001", naics=None)
        for row in OBSERVATIONS
    ]
    table(
        "visitor_events",
        events,
        "day string, hour string, useragent string, country string, postalcode string, ip string, visitorguid string, deviceid string, eids string, naics int",
    )
    table(
        "pixel_events",
        PIXELS,
        "day string, hour string, guid string, visitorstatus int, visitorguid string, deviceifa string, eids string",
    )
    table(
        "ua_hourly",
        [],
        "day string, hour string, useragent string, deviceclass string, devicename string, os string, osversion string, browser string, browserversion string",
    )
    raw, ip_hourly, fp_hourly = [], [], []
    periods = sorted({(row["day"], row["hour"]) for row in OBSERVATIONS + PIXELS})
    for day, hour in periods:
        current = [dict(row, day=day, hour=hour) for row in sql("NScreenRawHourly.sql", day=day, hour=hour)]
        raw.extend(current)
        table(
            "raw_hourly",
            current,
            "day string, hour string, ip string, uid string, useragent string, weight double, country string, postalcode string",
        )
        ip_hourly.extend(
            dict(row, day=day, hour=hour) for row in sql("NScreenIpColocationHourlyUa.sql", day=day, hour=hour)
        )
        fp_hourly.extend(
            dict(row, day=day, hour=hour) for row in sql("NScreenFirstPartyCollocationHourly.sql", day=day, hour=hour)
        )
    table("ip_hourly", ip_hourly, "day string, hour string, " + PAIR_SCHEMA)
    ip_daily = [
        dict(row, day=day)
        for day in sorted({d for d, _ in periods})
        for row in sql("NScreenIpColocationDailyUa.sql", day=day)
    ]
    table("ip_daily", ip_daily, "day string, " + PAIR_SCHEMA)
    ip_all = sql("NScreenIpColocationDailyAllUa.sql", day=DAY, start_day="2026-08-28")
    table("ip_all", [dict(row, day=DAY) for row in ip_all], "day string, " + PAIR_SCHEMA)
    table("fp_hourly", fp_hourly, "day string, hour string, uid1 string, uid2 string")
    fp_daily = sql("NScreenFirstPartyCollocationDaily.sql", day=DAY, start_day="2026-08-12")
    table("fp_daily", [dict(row, day=DAY) for row in fp_daily], "day string, uid1 string, uid2 string, weight long")
    clean = sql("NScreenIpCollocationDailyClean.sql", day=DAY)
    steps = build_collocation_steps()
    same(raw, steps[1]["rows"], ["day", "hour", "ip", "uid", "weight"])
    keys = ["uid1", "uid2", "weight", "samedevice", "differentusers"]
    same(ip_hourly, steps[3]["rows"], ["day", "hour", *keys])
    same(ip_daily, steps[3]["daily"], ["day", *keys])
    same(ip_all, [r for r in steps[4]["rows"] if r["kept"]], keys)
    same(fp_hourly, steps[6]["rows"], ["day", "hour", "uid1", "uid2"])
    same(fp_daily, steps[7]["rows"], ["uid1", "uid2", "weight"])
    same(clean, [r for r in steps[8]["rows"] if r["kept"]], keys)
    print(  # noqa: T201 - standalone verification result
        "PASS: seven repository SQL stages agree with the example; seven final pairs. UDF boundaries: normalized IPv4 and missing UA fixtures."
    )
    spark.stop()


if __name__ == "__main__":
    verify()

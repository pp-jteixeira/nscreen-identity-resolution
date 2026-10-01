"""Executable example of the IP and first-party SQL relationship stages.

Input observations start after IP normalization and UID extraction. Missing UA
metadata makes both Java UA predicates false in this example. No clustering is run.
"""

from collections import Counter, defaultdict
from itertools import combinations

from example import node_link

SQL_ROOT = "nscreen-graph/src/nscreen_graph/spark/sparksql/"
DAY = "2026-09-11"
UIDS = {name: f"FP_{name}000000001" for name in "ABCDEF"}
UIDS["I"] = "12345678-1234-1234-1234-123456789abc"
UIDS.update({name: f"FP_{name}000000001" for name in ["Solo", *[f"Z{i}" for i in range(9)]]})
IP_ADDRESSES = {f"ip{i}": f"192.0.2.{i}" for i in range(1, 6)}
ALIASES = {uid: name for name, uid in UIDS.items()}
OBSERVATIONS = [
    {"day": day, "hour": "00", "uid": UIDS[uid], "ip": IP_ADDRESSES[ip], "useragent": None}
    for day, ip, members in [
        ("2026-09-09", "ip1", "AB"),
        ("2026-09-09", "ip2", "ABCD"),
        ("2026-09-10", "ip2", "ABCD"),
        (DAY, "ip2", "ABCD"),
        (DAY, "ip3", "EF"),
        (DAY, "ip4", ["Solo"]),
        (DAY, "ip5", [f"Z{i}" for i in range(9)]),
    ]
    for uid in members
]
OBSERVATIONS.append(dict(OBSERVATIONS[2]))  # Repeated A/ip2 observation in the same hour.
PIXELS = [
    {
        "day": day,
        "hour": hour,
        "guid": guid,
        "visitorstatus": 3,
        "visitorguid": UIDS[visitor],
        "deviceifa": ifa,
        "eids": eids,
    }
    for day, hour, guid, visitor, ifa, eids in [
        ("2026-09-09", "00", "event1", "A", "", UIDS["B"] + "|" + UIDS["B"] + "|ZZ_ignored"),
        ("2026-09-09", "00", "event2", "A", "", UIDS["B"]),
        ("2026-09-10", "00", "event3", "A", "", UIDS["B"]),
        (DAY, "00", "event4", "A", "00000000-0000-0000-0000-000000000000", UIDS["B"] + "|" + UIDS["C"]),
        (DAY, "01", "event5", "E", UIDS["I"], ""),
    ]
]


def pair_row(pair, weight, **extra):
    return {"uid1": pair[0], "uid2": pair[1], "weight": weight, **extra}


def build_collocation_steps():
    groups = defaultdict(set)
    for row in OBSERVATIONS:
        groups[row["day"], row["hour"], row["ip"]].add(row["uid"])
    stats = [
        {"day": day, "hour": hour, "ip": ip, "uid_count": len(members), "kept": 2 <= len(members) <= 8}
        for (day, hour, ip), members in sorted(groups.items())
    ]
    weighted = [
        {"day": day, "hour": hour, "ip": ip, "uid": uid, "weight": 1 / len(members), "useragent": None}
        for (day, hour, ip), members in sorted(groups.items())
        if 2 <= len(members) <= 8
        for uid in sorted(members)
    ]
    contributions = [
        pair_row(pair, 1 / len(members), day=day, hour=hour, ip=ip)
        for (day, hour, ip), members in sorted(groups.items())
        if 2 <= len(members) <= 8
        for pair in combinations(sorted(members), 2)
    ]
    hourly_weights = defaultdict(float)
    for row in contributions:
        hourly_weights[row["day"], row["hour"], row["uid1"], row["uid2"]] += row["weight"]
    hourly = [
        pair_row((a, b), weight, day=day, hour=hour, samedevice=False, differentusers=False)
        for (day, hour, a, b), weight in sorted(hourly_weights.items())
    ]
    daily_weights = defaultdict(float)
    for row in hourly:
        daily_weights[row["day"], row["uid1"], row["uid2"]] += row["weight"]
    daily = [
        pair_row((a, b), weight, day=day, samedevice=False, differentusers=False)
        for (day, a, b), weight in sorted(daily_weights.items())
    ]
    histories = defaultdict(list)
    for row in daily:
        histories[row["uid1"], row["uid2"]].append(row)
    lookback = [
        pair_row(
            pair,
            sum(r["weight"] for r in rows),
            days=len(rows),
            kept=len(rows) >= 3,
            samedevice=False,
            differentusers=False,
        )
        for pair, rows in sorted(histories.items())
    ]
    ip_edges = [dict(row) for row in lookback if row["kept"]]

    extracted = []
    for event in PIXELS:
        candidates = []
        if event["visitorstatus"] == 3 and event["visitorguid"]:
            candidates.append((event["visitorguid"], "visitor"))
        if len(event["deviceifa"]) == 36 and event["deviceifa"] != "00000000-0000-0000-0000-000000000000":
            candidates.append((event["deviceifa"], "IFA"))
        candidates.extend(
            (eid, "EID") for eid in event["eids"].split("|") if eid and eid.split("_")[0] in {"FP", "MA", "I5"}
        )
        extracted.extend(
            {"day": event["day"], "hour": event["hour"], "guid": event["guid"], "uid": uid, "source": source}
            for uid, source in candidates
        )
    by_guid = defaultdict(set)
    for row in extracted:
        by_guid[row["day"], row["hour"], row["guid"]].add(row["uid"])
    fp_hourly_keys = sorted(
        {(day, hour, a, b) for (day, hour, _), members in by_guid.items() for a, b in combinations(sorted(members), 2)}
    )
    fp_hourly = [{"day": day, "hour": hour, "uid1": a, "uid2": b} for day, hour, a, b in fp_hourly_keys]
    fp_counts = Counter((a, b) for _, _, a, b in fp_hourly_keys)
    fp_daily = [
        pair_row(pair, count, samedevice=True, differentusers=False) for pair, count in sorted(fp_counts.items())
    ]
    union = [dict(row, source="IP") for row in ip_edges] + [dict(row, source="First party") for row in fp_daily]
    by_pair = defaultdict(list)
    for row in union:
        by_pair[row["uid1"], row["uid2"]].append(row)
    merged = [
        pair_row(
            pair,
            max(r["weight"] for r in rows),
            samedevice=any(r["samedevice"] for r in rows),
            differentusers=any(r["differentusers"] for r in rows),
            sources=", ".join(r["source"] for r in rows),
        )
        for pair, rows in sorted(by_pair.items())
    ]
    for field, other, rank in (("uid1", "uid2", "uid1rank"), ("uid2", "uid1", "uid2rank")):
        partitions = defaultdict(list)
        for row in merged:
            partitions[row[field]].append(row)
        for rows in partitions.values():
            for position, row in enumerate(sorted(rows, key=lambda r: (r["weight"], r[other]), reverse=True), 1):
                row[rank] = position
    for row in merged:
        row["kept"] = row["uid1rank"] <= 10 and row["uid2rank"] <= 10

    definitions = [
        (
            "Input UID/IP observations",
            "Normalized IPs and extracted eligible UIDs are the starting input. A/B share ip1; A/B/C/D share ip2. One repeated A/ip2 observation demonstrates deduplication. UA metadata is absent, so both Java UA flags are false.",
            OBSERVATIONS,
            "NScreenRawHourly.sql",
            38,
            79,
        ),
        (
            "Deduplicate, count, and weight IPs",
            "Deduplicate each UID/IP within each hour. Keep IPs with 2-8 distinct UIDs. ip4 has one UID and ip5 has nine, so both are dropped. Each remaining UID/IP row gets 1/N: ip1=0.5 and ip2=0.25.",
            weighted,
            "NScreenRawHourly.sql",
            38,
            79,
        ),
        (
            "Generate UID pairs per IP",
            "Join UIDs sharing an IP within the hour; retain uid1 < uid2. Two UIDs yield one pair; four yield all six pairs, including B-D. Each contribution uses the smaller UID's stored weight, which is 1/N here.",
            contributions,
            "NScreenIpColocationHourlyUa.sql",
            1,
            20,
        ),
        (
            "Aggregate hourly and daily IP pairs",
            "Sum contributions across IPs. On September 9, A-B gets 0.5 + 0.25 = 0.75. Daily aggregation sums hourly weights, MAXs sameDevice, and MINs differentUsers. Missing UA metadata makes both flags false in this fixture.",
            hourly,
            "NScreenIpColocationDailyUa.sql",
            1,
            9,
        ),
        (
            "IP lookback and three-day gate",
            "Sum daily weights over day-14 through day, inclusive (15 dates). Require at least three daily rows. A-B totals 1.25; the other five A/B/C/D pairs total 0.75 each. E-F appears on one day and is rejected. Unlisted dates have no observations.",
            lookback,
            "NScreenIpColocationDailyAllUa.sql",
            1,
            10,
        ),
        (
            "Extract first-party identifiers",
            "For each recording event, include visitorguid only when visitorstatus=3; include a 36-character nonzero IFA; include only FP/MA/I5-prefixed EIDs. Repeated B remains in the extraction rows. ZZ_ignored and the zero IFA are excluded. guid links identifiers from the same event.",
            extracted,
            "NScreenFirstPartyCollocationHourly.sql",
            1,
            31,
        ),
        (
            "Build first-party hourly pairs",
            "Pair identifiers sharing guid within an hour; keep uid1 < uid2 and GROUP BY pair. Repeated EIDs and multiple events producing A-B in the same hour still produce one hourly pair. Event4 yields A-B, A-C, and B-C. Event5 links E with IFA I.",
            fp_hourly,
            "NScreenFirstPartyCollocationHourly.sql",
            33,
            38,
        ),
        (
            "Count first-party lookback occurrences",
            "COUNT hourly pair rows over day-30 through day, inclusive (31 dates). A-B has weight 3; A-C, B-C, and E-I have weight 1. These are hourly occurrences, not event counts or 1/N weights. The clean union assigns sameDevice=true and differentUsers=false.",
            fp_daily,
            "NScreenFirstPartyCollocationDaily.sql",
            1,
            7,
        ),
        (
            "Union, merge, and rank relationships",
            "UNION ALL IP and first-party rows, then MAX weight and each flag by ordered pair. A-B becomes MAX(1.25, 3)=3; A-C and B-C become 1. Rank separately by uid1 and uid2, weight descending then opposite UID descending. Keep both ranks ≤10. All seven pairs survive here; E-I needs no three-day IP history.",
            merged,
            "NScreenIpCollocationDailyClean.sql",
            1,
            53,
        ),
    ]
    steps = [
        {"number": i, "title": title, "note": note, "rows": rows, "sources": [(SQL_ROOT + file, start, end)]}
        for i, (title, note, rows, file, start, end) in enumerate(definitions)
    ]
    steps[1]["ip_stats"] = stats
    steps[3]["daily"] = daily
    steps[3]["sources"] += [
        (SQL_ROOT + "NScreenIpColocationHourlyUa.sql", 23, 50),
        ("src/jvm/com/pulsepoint/hive/udf/UDFIsSameDevice.java", 17, 29),
        ("src/jvm/com/pulsepoint/hive/udf/UDFDifferentUsers.java", 24, 36),
    ]
    steps[4]["sources"].append(("nscreen-graph/src/nscreen_graph/tasks/daily.py", 17, 17))
    steps[7]["sources"] += [
        ("nscreen-graph/src/nscreen_graph/tasks/daily.py", 100, 109),
        (SQL_ROOT + "NScreenIpCollocationDailyClean.sql", 10, 18),
    ]
    steps[8]["union"] = union
    return steps


def collocation_graph(steps, number, full=False):
    nodes, edges = {}, []

    def uid_node(uid):
        name = ALIASES[uid]
        nodes[name] = {"kind": "uid", "details": f"{name}\nUID: {uid}"}
        return name

    def pair_edges(rows, layer, skip_rejected=False):
        for row in rows:
            if skip_rejected and not row.get("kept", True):
                continue
            edges.append(
                {
                    "source": uid_node(row["uid1"]),
                    "target": uid_node(row["uid2"]),
                    "weight": row.get("weight", 1),
                    "same_device": row.get("samedevice", False),
                    "different_users": row.get("differentusers", False),
                    "source_rows": (layer,),
                    "label": f"{row.get('weight', 1):.6g}",
                    "layer": layer,
                    "details": "\n".join(f"{k}: {v}" for k, v in row.items()),
                }
            )

    def observations(rows):
        for row in rows:
            ip = next(name for name, address in IP_ADDRESSES.items() if address == row["ip"])
            nodes[ip] = {"kind": "ip", "details": f"{ip}\n{row['ip']}"}
            edges.append(
                {
                    "source": uid_node(row["uid"]),
                    "target": ip,
                    "kind": "observation",
                    "label": str(row.get("weight", "observed")),
                    "details": str(row),
                }
            )

    def events():
        for row in steps[5]["rows"]:
            event = row["guid"]
            nodes[event] = {"kind": "event", "details": f"{event}\n{row['day']} {row['hour']}"}
            edges.append(
                {
                    "source": uid_node(row["uid"]),
                    "target": event,
                    "kind": "observation",
                    "label": row["source"],
                    "details": str(row),
                }
            )

    if full:
        observations(steps[1]["rows"])
        events()
        pair_edges(steps[8]["rows"], "clean", skip_rejected=True)
    elif number in (0, 1):
        observations(steps[number]["rows"])
    elif number == 2:
        observations([row for row in steps[1]["rows"] if row["day"] == "2026-09-09"])
        pair_edges([row for row in steps[2]["rows"] if row["day"] == "2026-09-09"], "IP contribution")
    elif number == 5:
        events()
    else:
        pair_edges(steps[number]["rows"], steps[number]["title"], skip_rejected=number in (4, 8))
    return node_link(nodes, edges, directed=False)

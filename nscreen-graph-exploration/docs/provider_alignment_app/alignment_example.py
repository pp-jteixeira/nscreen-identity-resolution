"""Computed walkthrough of the expanded notebook inputs with production semantics.

No production data access. Match IDs are numeric fixtures with display aliases.
The two-node Louvain result is a fixed reference, not a Python clustering engine.
"""

import re
from collections import Counter, defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
SQL_ROOT = "nscreen-graph/src/nscreen_graph/spark/sparksql/"
DAY = "2026-09-11"
JOB1 = "NScreenLiverampThrotleOnlyStage.sql"
JOB2 = "NScreenLiverampThrotleExInitialStage.sql"
CONNECTED = "NScreenLiverampThrotleExConnectedNsStage.sql"
PROPAGATE = "NScreenLiverampThrotleExNStage.sql"
REMAINDER = "NScreenIpCollocationDailyExRemainder.sql"
LOUVAIN = "NScreenExRemainderLouvainStage.sql"
RESULT = "NScreenLrThrotleExReasonResult.sql"
ALIASES = {
    **{100 + i: f"T{i}" for i in (1, 2, 3, 4, 5, 6, 9)},
    **{200 + i: f"L{i}" for i in range(1, 7)},
    301: "E1",
    302: "E2",
    303: "E3",
    901: "C1",
}


def provider_rows(groups, reason):
    return [
        {"uid": f"v{uid}", "matchid": match, "householdid": 0, "stable": True, "reason": reason}
        for match, uids in groups.items()
        for uid in uids
    ]


THROTLE = provider_rows(
    {101: [1, 2, 3], 102: [4], 109: [5], 103: [6], 104: [6], 105: [6], 106: [22, 23, 24, 25, 26, 27]}, "TH"
)
LIVERAMP = provider_rows({201: [1, 2, 9], 202: [4, 10, 13], 203: [13, 14], 204: [22], 205: [23], 206: [30, 31]}, "LR")
EXPERIAN = provider_rows({301: [3, 15], 302: [16], 303: [30, 32]}, "EX")
EDGES = [
    {"uid1": a, "uid2": b, "weight": float(w), "samedevice": False, "differentusers": False}
    for a, b, w in [
        ("v1", "v17", 5),
        ("v17", "v18", 3),
        ("v6", "v20", 2),
        ("v19", "v21", 4),
        ("v33", "v34", 3),
        ("v9", "v24", 4),
        ("v9", "v25", 4),
        ("v9", "v26", 4),
    ]
]
ALL_UIDS = sorted(
    {r["uid"] for r in THROTLE + LIVERAMP + EXPERIAN} | {e[k] for e in EDGES for k in ("uid1", "uid2")},
    key=lambda u: int(u[1:]),
)
GEO = [
    {"uid": uid, "geo": {"v33": "G3", "v34": "G4"}.get(uid, "G1")}
    for uid in sorted({e[k] for e in EDGES for k in ("uid1", "uid2")})
]


def align(left, right):
    """Expose joined, grouped, ranked, limited, and mapping without UID dedup."""
    joined = [
        {
            "uid": a["uid"],
            "left": a["matchid"],
            "right": b["matchid"],
            "householdid": b["householdid"],
            "stable": b["stable"],
            "reason": b["reason"],
        }
        for a in left
        for b in right
        if a["uid"] == b["uid"]
    ]
    buckets = defaultdict(list)
    for row in joined:
        buckets[row["left"], row["right"]].append(row)
    grouped = [
        {
            "left": a,
            "right": b,
            "cnt": len(rows),
            "uids": [r["uid"] for r in rows],
            "householdid": max(r["householdid"] for r in rows),
            "stable": max(r["stable"] for r in rows),
            "reason": max(r["reason"] for r in rows),
        }
        for (a, b), rows in buckets.items()
    ]
    ranked = [
        dict(
            row,
            rnk_1=1 + sum(other["left"] == row["left"] and other["cnt"] > row["cnt"] for other in grouped),
            rnk_2=1 + sum(other["right"] == row["right"] and other["cnt"] > row["cnt"] for other in grouped),
        )
        for row in grouped
    ]
    mutual = [r for r in ranked if r["rnk_1"] == r["rnk_2"] == 1]
    c1, c2 = Counter(r["left"] for r in mutual), Counter(r["right"] for r in mutual)
    limited = [
        dict(r, count1=c1[r["left"]], count2=c2[r["right"]], accepted=c1[r["left"]] == c2[r["right"]] == 1)
        for r in mutual
    ]
    mapping = [r for r in limited if r["accepted"]]
    return {"joined": joined, "grouped": grouped, "ranked": ranked, "limited": limited, "mapping": mapping}


def output_alignment(left, right, mapping, first_job):
    by_left = {r["left"]: r for r in mapping}
    by_right = {r["right"]: r for r in mapping}
    right_uids = {r["uid"] for r in right}
    right_out = [
        dict(r, reason=("LRTH" if first_job else r["reason"] + "EX") if r["matchid"] in by_right else r["reason"])
        for r in right
    ]
    only = [r for r in left if r["uid"] not in right_uids]
    left_out = []
    for row in only:
        m = by_left.get(row["matchid"])
        left_out.append(
            dict(
                row,
                matchid=m["right"] if m else row["matchid"],
                householdid=m["householdid"] if m else row["householdid"],
                stable=m["stable"] if m else True,
                reason=("LRTH" if first_job else m["reason"] + "EX") if m else row["reason"],
            )
        )
    return right_out, only, left_out


def propagate(seeds, edges=EDGES, cap=10):
    doubled = [
        dict(uid1=e[a], uid2=e[b], weight=e["weight"]) for e in edges for a, b in (("uid1", "uid2"), ("uid2", "uid1"))
    ]
    contributions = [
        dict(
            uid=e["uid1"],
            via=e["uid2"],
            matchid=s["matchid"],
            householdid=s["householdid"],
            stable=s["stable"],
            weight=e["weight"],
        )
        for e in doubled
        for s in seeds
        if e["uid2"] == s["uid"]
    ]
    weights = defaultdict(float)
    for r in contributions:
        weights[r["uid"], r["matchid"], r["householdid"], r["stable"]] += r["weight"]
    known = {r["uid"] for r in seeds}
    grouped = [
        dict(
            uid=u,
            matchid=m,
            householdid=h,
            stable=s,
            raw_weight=w,
            weight=w * (2 if s else 1),
            already_assigned=u in known,
        )
        for (u, m, h, s), w in weights.items()
    ]
    ranked = []
    per_uid = defaultdict(list)
    for r in grouped:
        if not r["already_assigned"]:
            per_uid[r["uid"]].append(r)
    for rows in per_uid.values():
        ranked.extend(
            dict(r, uid_rank=i)
            for i, r in enumerate(sorted(rows, key=lambda r: (r["weight"], r["matchid"]), reverse=True), 1)
        )
    winners = [r for r in ranked if r["uid_rank"] == 1]
    capped = []
    for match in sorted({r["matchid"] for r in winners}):
        rows = sorted(
            [r for r in winners if r["matchid"] == match], key=lambda r: (r["weight"], r["uid"]), reverse=True
        )
        capped.extend(dict(r, match_rank=i, kept=i <= cap) for i, r in enumerate(rows, 1))
    output = [
        {k: r[k] for k in ("uid", "matchid", "householdid", "stable")} | {"reason": "IC"} for r in capped if r["kept"]
    ]
    return dict(
        doubled=doubled, contributions=contributions, grouped=grouped, ranked=ranked, capped=capped, output=output
    )


def final_result(staged):
    rows = []
    for row in staged:
        if row["stage"] not in {"initial", "stage1", "stage2", "louvain"} or row["matchid"] == 0:
            continue
        if (row["uid"].startswith("LR_") and row["reason"] == "IC") or re.fullmatch(r"[01\-_!*]*", row["uid"]):
            continue
        prefix = "S_" if row["stable"] else ""
        rows.append(
            dict(
                uid=row["uid"],
                matchid=prefix + str(row["matchid"]),
                householdid=prefix + str(row["householdid"]) if row["householdid"] else "",
                reason=row["reason"],
            )
        )
    return rows


def build_example():
    job1 = align(THROTLE, LIVERAMP)
    lr_out, th_only, th_out = output_alignment(THROTLE, LIVERAMP, job1["mapping"], True)
    raw1 = [dict(r, stage="initial") for r in lr_out] + [dict(r, stage="lrth") for r in th_out]
    lrth = [dict(r, stage="lrth") for r in raw1]
    job2 = align(EXPERIAN, lrth)
    lrth_out, ex_only, ex_out = output_alignment(EXPERIAN, lrth, job2["mapping"], False)
    initial = [dict(r, stage="initial") for r in lrth_out + ex_out]
    connected = [
        dict(r, stage="connected_ns", reason="NA")
        for r in initial
        if any(r["uid"] in (e["uid1"], e["uid2"]) for e in EDGES)
    ]
    p1 = propagate(connected)
    stage1 = [dict(r, stage="stage1") for r in p1["output"]]
    p2 = propagate(connected + stage1)
    stage2 = [dict(r, stage="stage2") for r in p2["output"]]
    assigned = {r["uid"] for r in initial + stage1 + stage2}
    geo = {r["uid"]: r["geo"] for r in GEO}
    remainder_checks = [
        dict(
            e,
            uid1_assigned=e["uid1"] in assigned,
            uid2_assigned=e["uid2"] in assigned,
            same_geo=geo.get(e["uid1"]) is not None and geo.get(e["uid1"]) == geo.get(e["uid2"]),
            geo1=geo.get(e["uid1"]),
            geo2=geo.get(e["uid2"]),
        )
        for e in EDGES
    ]
    remainder = [
        dict(e, geo=geo[e["uid1"]])
        for e, check in zip(EDGES, remainder_checks, strict=True)
        if not check["uid1_assigned"] and not check["uid2_assigned"] and check["same_geo"]
    ]
    # Only this documented two-UID component; no arbitrary-input Louvain emulation.
    assert {(r["uid1"], r["uid2"]) for r in remainder} == {("v19", "v21")}
    louvain = [
        dict(uid=u, matchid=901, householdid=0, stable=False, reason="LU", stage="louvain") for u in ("v19", "v21")
    ]
    staged = lrth + initial + connected + stage1 + stage2 + louvain
    diagnostic = [
        dict(
            uid=u,
            rows=sum(r["uid"] == u for r in staged),
            **{f"distinct_{k}": len({r[k] for r in staged if r["uid"] == u}) for k in ("stage", "matchid", "reason")},
        )
        for u in ALL_UIDS
        if any(r["uid"] == u for r in staged)
    ]
    return dict(
        job1=job1,
        lr_out=lr_out,
        th_only=th_only,
        th_out=th_out,
        raw1=raw1,
        lrth=lrth,
        job2=job2,
        lrth_out=lrth_out,
        ex_only=ex_only,
        ex_out=ex_out,
        initial=initial,
        connected=connected,
        p1=p1,
        stage1=stage1,
        p2=p2,
        stage2=stage2,
        remainder_checks=remainder_checks,
        remainder=remainder,
        louvain=louvain,
        staged=staged,
        diagnostic=diagnostic,
        result=final_result(staged),
    )


def source(file, start, end):
    return (SQL_ROOT + file, start, end)


def build_steps(data):
    steps = []

    def add(title, note, tables, sources, *, assignments=(), pairs=(), evidence=()):
        steps.append(
            dict(
                number=len(steps),
                title=title,
                note=note,
                tables=tables,
                sources=sources,
                assignments=list(assignments),
                pairs=list(pairs),
                evidence=list(evidence),
            )
        )

    add(
        "Full input dataset",
        "Vendor claims are UID → matchid memberships, not UID-UID evidence. v6 has three Throtle claims; v13 has two LiveRamp claims. The eight weighted edges come from activity logs independently. New cases: L6/E3 demonstrates LREX; v33/v34 demonstrates rejection across different geos; v9-v24/v25/v26 demonstrates that graph-connection is not the same as matchid inheritance.",
        {
            "Throtle": THROTLE,
            "LiveRamp": LIVERAMP,
            "Experian": EXPERIAN,
            "IP-collocation edges": EDGES,
            "Geo fixture": GEO,
        },
        [("nscreen-graph/provider-alignment-toy.ipynb", 407, 450)],
        assignments=THROTLE + LIVERAMP + EXPERIAN,
        evidence=EDGES,
    )
    for key, title, note, lines in [
        (
            "joined",
            "Job 1: join shared UIDs",
            "Only equal UIDs join. The five evidence rows produce four candidate group pairs. This is COUNT(*), not COUNT(DISTINCT uid).",
            (25, 48),
        ),
        (
            "ranked",
            "Job 1: count and rank pairs",
            "Count joined rows per group pair, then rank counts independently on each side. Both T6 partners tie at rank 1. Rank does not pick one arbitrarily.",
            (37, 69),
        ),
        (
            "limited",
            "Job 1: reject mutual-best ties",
            "Count only pairs ranked first on both sides. T6 has count1=2, so both L4 and L5 pairings are rejected. Both counters must equal 1.",
            (71, 95),
        ),
        (
            "mapping",
            "Job 1: accepted translations",
            "Accept T1 → L1 and T2 → L2. Translation applies to whole groups, including members such as v3 and v9 that were not shared evidence.",
            (85, 115),
        ),
    ]:
        add(
            title,
            note,
            {key: data["job1"][key], **({"Shared counts": data["job1"]["grouped"]} if key == "ranked" else {})},
            [source(JOB1, *lines)],
            pairs=data["job1"][key],
        )
    add(
        "Job 1: write all rows to lrth",
        "Keep every LiveRamp claim. Exclude Throtle rows by UID existence in LiveRamp, then translate surviving Throtle groups. The writer overwrites SQL stage literals: all 21 rows land in lrth, not just the nine Throtle leftovers.",
        {
            "LiveRamp output": data["lr_out"],
            "Throtle-only input": data["th_only"],
            "Throtle output": data["th_out"],
            "SQL output before writer": data["raw1"],
            "Written lrth": data["lrth"],
        },
        [
            source(JOB1, 97, 180),
            ("nscreen-graph/src/nscreen_graph/spark/common.py", 42, 51),
            ("nscreen-graph/src/nscreen_graph/tasks/daily.py", 295, 300),
        ],
        assignments=data["lrth"],
    )
    add(
        "Job 2: join Experian",
        "Experian is compared with ALL lrth rows, including LiveRamp-rooted ones. v3 gives E1 → L1; v30 gives E3 → L6. v15 and v32 provide no overlap themselves but inherit their groups' accepted mappings.",
        {"Joined UIDs": data["job2"]["joined"], "Shared counts": data["job2"]["grouped"]},
        [source(JOB2, 1, 52)],
        pairs=data["job2"]["joined"],
    )
    add(
        "Job 2: rank and accept",
        "Apply the same mutual-best and uniqueness tests. E1 → L1 and E3 → L6 pass. count1 is now the Experian side; count2 is the lrth side.",
        {
            "Ranks": data["job2"]["ranked"],
            "Uniqueness": data["job2"]["limited"],
            "Accepted mapping": data["job2"]["mapping"],
        },
        [source(JOB2, 54, 104)],
        pairs=data["job2"]["limited"],
    )
    add(
        "Job 2: write initial assignments",
        "Every L1 row gains EX: v1, v2, v9, v3 and inherited v15 all become LRTHEX. v16 stays E2/EX. v30, v31 and inherited v32 become L6/LREX. All 24 rows enter initial; v6 and v13 remain ambiguous.",
        {
            "Existing rows rewritten": data["lrth_out"],
            "Experian-only input": data["ex_only"],
            "Experian output": data["ex_out"],
            "Written initial": data["initial"],
        },
        [source(JOB2, 106, 190), ("nscreen-graph/src/nscreen_graph/tasks/daily.py", 324, 329)],
        assignments=data["initial"],
    )
    add(
        "Select graph-connected seeds",
        "Distinct edge endpoints select initial rows by UID. Copy v1 once, v6 three times, and v9/v24/v25/v26 once each -- the last four already had a matchid from provider alignment, so this only makes them graph-connected, not newly assigned. Reasons become NA only in this intermediate copy; initial is unchanged.",
        {"Connected seeds": data["connected"]},
        [source(CONNECTED, 1, 26)],
        assignments=data["connected"],
        evidence=EDGES,
    )
    for index in (1, 2):
        p = data[f"p{index}"]
        seeds = data["connected"] + (data["stage1"] if index == 2 else [])
        add(
            f"Stage {index}: score propagation candidates",
            "Make both directions of each edge. Join neighbors to seeds, sum per UID/match/household/stable, then double stable scores. Drop already-assigned UIDs. "
            + (
                "Scores: v17→L1=10; v20→T3/T4/T5=4 each. v9/v24/v25/v26 also score against each other here, but all four are already-assigned seeds themselves, so none of them is a candidate."
                if index == 1
                else "Stage1 winners now seed this round. v18→L1 scores 6. v1, v6, v9 and v24/v25/v26 are re-reached but excluded."
            ),
            {
                "Seeds": seeds,
                "Directed edges": p["doubled"],
                "Contributions before stable boost": p["contributions"],
                "Grouped scores and exclusions": p["grouped"],
                "UID ranking": p["ranked"],
            },
            [source(PROPAGATE, 1, 86)],
            assignments=seeds,
            pairs=p["grouped"],
            evidence=EDGES,
        )
        add(
            f"Stage {index}: choose winners and cap",
            "Choose one match per UID by score descending, then numeric matchid descending. Cap each match at ten new UIDs AFTER choosing UID winners; discarded alternatives are not reconsidered. No cap binds in this fixture. "
            + (
                "v20 chooses T5 (105), not T3 (103) or T4 (104)."
                if index == 1
                else "Only v18 is newly assigned. This is the last propagation round."
            ),
            {"UID ranks": p["ranked"], "Match cap": p["capped"], f"Written stage{index}": data[f"stage{index}"]},
            [source(PROPAGATE, 67, 119)],
            assignments=data[f"stage{index}"],
            evidence=EDGES,
        )
    add(
        "Select unresolved same-geo edges",
        "Keep an edge only if NEITHER endpoint is in initial/stage1/stage2 and both have the same geo. Only v19-v21 survives. v33-v34 has two unassigned endpoints, but G3 differs from G4, so that edge is rejected and both UIDs remain unassigned.",
        {"Edge eligibility": data["remainder_checks"], "Remainder": data["remainder"]},
        [source(REMAINDER, 1, 61)],
        evidence=[
            dict(e, rejected=not e["same_geo"])
            for e in data["remainder_checks"]
            if not e["uid1_assigned"] and not e["uid2_assigned"]
        ],
    )
    add(
        "Louvain on the remainder",
        "The SQL hashes UIDs, runs the Screen7 UDAF per geo, then joins back to both UID strings. v19 and v21 share one nonzero match, shown as C1 (901); stable=false and reason=LU. Household output is 0 for this single-match household. This is a fixed reference, not clustering run by Streamlit.",
        {"UDAF input edges": data["remainder"], "Written louvain": data["louvain"]},
        [
            source(LOUVAIN, 1, 68),
            ("src/jvm/com/pulsepoint/hive/udf/calcscreen7ids/UDAFCalcScreen7IdsEvaluator.java", 97, 107),
            ("src/jvm/com/pulsepoint/hive/udf/calcscreen7ids/calc/Screen7IdCalculatorDHMH.java", 43, 84),
            ("src/jvm/com/pulsepoint/hive/udf/calcscreen7ids/calc/Screen7IdCalculatorDHMH.java", 109, 130),
        ],
        assignments=data["louvain"],
        evidence=data["remainder"],
    )
    add(
        "Full staged table",
        "58 rows: lrth 21, initial 24, connected_ns 8, stage1 2, stage2 1, louvain 2. These counts match the expanded notebook's production-style write semantics. Parallel graph links retain their stage and reason.",
        {
            "Stage counts": [dict(stage=k, rows=v) for k, v in Counter(r["stage"] for r in data["staged"]).items()],
            "All staged rows": data["staged"],
        },
        [("nscreen-graph/src/nscreen_graph/spark/common.py", 42, 51)],
        assignments=data["staged"],
        evidence=EDGES,
    )
    add(
        "Diagnose multiple assignments",
        "Count distinct stages, matches and reasons per UID. v6 has 3 matches across 3 stages; v13 has 2 matches across 2 stages. v9/v24/v25/v26 each reach 3 distinct stages (lrth, initial, connected_ns) but only 1 distinct matchid -- being graph-connected adds stages and an NA reason, never a second matchid. Multiple stages or reasons alone are not ambiguity. v33/v34 have no staged rows, so the staged-table diagnostic query does not return them. No graph claims are deduplicated by UID.",
        {"Per-UID diagnostics": data["diagnostic"]},
        [("nscreen-graph/provider-alignment-phase.md", 407, 438)],
        assignments=data["staged"],
    )
    final_rows = [r for r in data["staged"] if r["stage"] in {"initial", "stage1", "stage2", "louvain"}]
    add(
        "Final exported result",
        "Keep initial/stage1/stage2/louvain only; filter matchid=0, LR_-prefixed propagated UIDs, and placeholder UIDs. Stable IDs get S_; household 0 becomes empty text. No per-UID deduplication: 29 rows for 26 UIDs. v33 and v34 remain visible as input history but have no exported assignment. Graph aliases label the same identities; exact exported values are in the table.",
        {"Final result": data["result"]},
        [source(RESULT, 1, 19)],
        assignments=final_rows,
        evidence=EDGES,
    )
    return steps


def graph_for(step, data, full=False):
    nodes, links = {}, []

    def node(identifier, kind, details=""):
        nodes.setdefault(identifier, dict(id=identifier, kind=kind, details=details or identifier))

    def uid(identifier):
        node(identifier, "uid")

    def match(identifier):
        label = ALIASES[identifier]
        node(
            label,
            {"T": "throtle", "L": "liveramp", "E": "experian", "C": "community"}[label[0]],
            f"{label}\nNumeric fixture matchid: {identifier}",
        )
        return label

    def link(a, b, kind, label, row, directed=True, origin=None):
        relationship = {
            "source": a,
            "target": b,
            "kind": kind,
            "label": label,
            "directed": directed,
            "details": "\n".join(f"{k}: {v}" for k, v in row.items()),
        }
        if origin:
            relationship["origin"] = origin
            relationship["details"] += (
                f"\nrelationship_source: {origin.replace('_', ' ')}"
            )
        links.append(relationship)

    assignments = step["assignments"]
    pairs = step["pairs"]
    evidence = step["evidence"]
    if full:
        assignments = [dict(r, stage="source") for r in THROTLE + LIVERAMP + EXPERIAN] + data["staged"]
        pairs = data["job1"]["limited"] + data["job2"]["limited"]
        evidence = EDGES
    for r in assignments:
        uid(r["uid"])
        link(r["uid"], match(r["matchid"]), "membership", r.get("stage", "source") + " / " + r["reason"], r)
    for r in pairs:
        if "left" in r:
            a, b = match(r["left"]), match(r["right"])
            kind = "accepted" if r.get("accepted") else "rejected" if r.get("accepted") is False else "candidate"
            label = str(r.get("cnt", "")) + (
                " accepted" if kind == "accepted" else " rejected" if kind == "rejected" else " candidate"
            )
            if "uid" in r:
                uid(r["uid"])
                link(r["uid"], a, "evidence", "shared UID", r, False, "shared_uid")
                link(r["uid"], b, "evidence", "shared UID", r, False, "shared_uid")
            link(a, b, kind, label, r)
        else:
            uid(r["uid"])
            link(
                r["uid"],
                match(r["matchid"]),
                "rejected" if r.get("already_assigned") else "candidate",
                f"score {r['weight']:g}",
                r,
            )
    for e in evidence:
        uid(e["uid1"])
        uid(e["uid2"])
        link(
            e["uid1"],
            e["uid2"],
            "rejected" if e.get("rejected") else "evidence",
            f"weight {e['weight']:g}" + (" / geo mismatch" if e.get("rejected") else ""),
            e,
            False,
            "ip_collocation",
        )
    if step["number"] == 0 or full:
        for u in ALL_UIDS:
            uid(u)
    return {"directed": True, "multigraph": True, "nodes": list(nodes.values()), "links": links}

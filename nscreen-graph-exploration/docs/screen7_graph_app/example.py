"""Graph snapshots for the fixed, Java-verified eleven-row documentation example.

Community assignments are reference fixtures, not a Python implementation of
Louvain or label propagation. Collapses, memberships, and output sentinels are
derived below. Do not substitute arbitrary input without revalidating fixtures.
"""

from collections import Counter, defaultdict
from copy import deepcopy
from dataclasses import asdict, dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
CALCULATOR = "src/jvm/com/pulsepoint/hive/udf/calcscreen7ids/calc/Screen7IdCalculatorDHMH.java"
EVALUATOR = "src/jvm/com/pulsepoint/hive/udf/calcscreen7ids/UDAFCalcScreen7IdsEvaluator.java"
LOUVAIN = "src/jvm/com/pulsepoint/hive/udf/louvain/"


@dataclass(frozen=True)
class Edge:
    source: str
    target: str
    weight: float
    same_device: bool = False
    different_users: bool = False
    source_rows: tuple[str, ...] = ()


EXAMPLE_EDGES = (
    Edge("u1", "u2", 10.0, True, False, ("A",)),
    Edge("u1", "u3", 4.0, False, False, ("B",)),
    Edge("u2", "u3", 3.0, False, False, ("C",)),
    Edge("u4", "u5", 10.0, True, False, ("D",)),
    Edge("u4", "u6", 6.0, False, False, ("E",)),
    Edge("u3", "u4", 1.0, False, False, ("F",)),
    Edge("u7", "u8", 10.0, True, False, ("G",)),
    Edge("u7", "u9", 2.0, False, True, ("H",)),
    Edge("u10", "u11", 10.0, True, False, ("I",)),
    Edge("u10", "u12", 3.0, False, True, ("J",)),
    Edge("u1", "u7", 0.25, False, False, ("K",)),
)

# These readable labels describe the memberships verified against Java.
UID_TO_DEVICE = {
    "u1": "D1",
    "u2": "D1",
    "u3": "D2",
    "u4": "D3",
    "u5": "D3",
    "u6": "D4",
    "u7": "D5",
    "u8": "D5",
    "u9": "D6",
    "u10": "D7",
    "u11": "D7",
    "u12": "D8",
}
PRELIMINARY = {"D1": "H1", "D2": "H1", "D3": "H2", "D4": "H2", "D5": "H3", "D6": "H3", "D7": "H4", "D8": "H4"}
DEVICE_TO_MATCH = {"D1": "M1", "D2": "M1", "D3": "M2", "D4": "M2", "D5": "M3", "D6": "M4", "D7": "M5", "D8": "M6"}
FINAL_HOUSEHOLDS = {"M1": "H1", "M2": "H1", "M3": "H3", "M4": "H3", "M5": "H4", "M6": "H4"}

TITLES = (
    "Input relationships",
    "Build device groups",
    "Collapse the UID graph",
    "Build preliminary households",
    "Build match groups",
    "Collapse the device graph",
    "Build final households",
    "Return UID assignments",
)
NOTES = (
    "Eleven edges, twelve UIDs, one geo. Weak bridges connect three strong pairs; another pair is disconnected.",
    (
        "Only A, D, G, and I are eligible same-device edges. Four other UIDs receive singleton device IDs. "
        "Their ordinary/conflict edges return in Step 2; they are not used in this device pass."
    ),
    (
        "Replace every original endpoint with its device ID. B + C becomes weight 7. "
        "A, D, G, and I become self-edges of weight 0.00001; their weight 10 is discarded."
    ),
    (
        "Four preliminary households form: H1={D1,D2}, H2={D3,D4}, H3={D5,D6}, H4={D7,D8}. "
        "Internal weights 7, 6, 2, and 3 outweigh the bridges of 1 and 0.25. differentUsers is ignored here."
    ),
    (
        "Four independent Louvain calls produce six matches. H1 collapses to M1 and H2 to M2. "
        "Conflicts keep H3 split into M3/M4 and H4 into M5/M6. Bridges F and K are outside these scopes."
    ),
    (
        "Use the complete device graph, including F and K. Internal weights 7 and 6 become tiny self-edges. "
        "The M1--M2 bridge retains weight 1; M1--M3 retains 0.25. Conflicts are dropped."
    ),
    (
        "M2 moves from H2 to H1. Its weight-1 connection to M1 now outweighs staying alone. "
        "H2 becomes empty; H3 and H4 stay intact. Three final households remain, each with two matches."
    ),
    (
        "The UDAF returns twelve structs, not edges. This view overlays its assignments on the original "
        "relationships. u4/u5/u6 changed household together. u9 and u12 return matchid=0. "
        "Downstream SQL removes those two rows; the UDAF itself does not."
    ),
)
SOURCES = (
    ((EVALUATOR, 67, 74),),
    ((CALCULATOR, 47, 51), (CALCULATOR, 157, 166), (LOUVAIN + "GlobalLabelPropAlgo.java", 17, 27)),
    ((CALCULATOR, 52, 52), (CALCULATOR, 183, 210)),
    ((CALCULATOR, 54, 58), (LOUVAIN + "LabelPropAlgo.java", 41, 75)),
    ((CALCULATOR, 60, 75), (CALCULATOR, 133, 145), (LOUVAIN + "Graph.java", 94, 102)),
    ((CALCULATOR, 77, 78), (CALCULATOR, 183, 210)),
    ((CALCULATOR, 80, 82), (LOUVAIN + "LabelPropAlgo.java", 32, 38)),
    ((CALCULATOR, 87, 98), (CALCULATOR, 109, 130), (EVALUATOR, 98, 107)),
)


def collapse_graph(edges: tuple[Edge, ...], mapping: dict[str, str], *, keep_conflicts: bool) -> tuple[Edge, ...]:
    """Apply collapseGraph's rules, retaining source-row provenance for display."""
    pairs: dict[tuple[str, str], list[Edge]] = defaultdict(list)
    for edge in edges:
        pair = tuple(sorted((mapping[edge.source], mapping[edge.target])))
        pairs[pair].append(edge)
    collapsed = []
    for (source, target), contributors in sorted(pairs.items()):
        internal = source == target
        collapsed.append(
            Edge(
                source,
                target,
                0.00001 if internal else sum(edge.weight for edge in contributors),
                False,
                not internal and keep_conflicts and any(edge.different_users for edge in contributors),
                tuple(sorted(row for edge in contributors for row in edge.source_rows)),
            )
        )
    return tuple(collapsed)


def uid_assignments(step: int) -> list[dict]:
    devices_per_match = Counter(DEVICE_TO_MATCH.values())
    uids_per_device = Counter(UID_TO_DEVICE.values())
    matches_per_household = Counter(FINAL_HOUSEHOLDS.values())
    rows = []
    for uid, device in UID_TO_DEVICE.items():
        row = {"uid": uid, "numeric_uid": int(uid[1:])}
        if step >= 1:
            row["deviceid"] = device
        if step >= 3:
            row["preliminary_householdid"] = PRELIMINARY[device]
        if step >= 4:
            row["internal_matchid"] = DEVICE_TO_MATCH[device]
        if step >= 6:
            row["internal_householdid"] = FINAL_HOUSEHOLDS[DEVICE_TO_MATCH[device]]
            row["household_changed"] = row["preliminary_householdid"] != row["internal_householdid"]
        if step == 7:
            match = DEVICE_TO_MATCH[device]
            household = FINAL_HOUSEHOLDS[match]
            row["matchid"] = 0 if devices_per_match[match] == 1 and uids_per_device[device] == 1 else match
            row["householdid"] = 0 if matches_per_household[household] == 1 else household
            row["kept_by_downstream_sql"] = row["matchid"] != 0
        rows.append(row)
    return rows


def node_link(nodes: dict[str, dict], edges: list[dict], *, directed: bool) -> dict:
    """NetworkX-compatible node-link data; no NetworkX dependency is needed."""
    return {
        "directed": directed,
        "multigraph": True,
        "graph": {},
        "nodes": [{"id": name, **attributes} for name, attributes in nodes.items()],
        "links": [{"key": index, **edge} for index, edge in enumerate(edges)],
    }


def evidence_graph(step: int, edges: tuple[Edge, ...], rows: list[dict]) -> dict:
    field = "uid" if step <= 1 or step == 7 else "deviceid" if step <= 4 else "internal_matchid"
    members: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        members[row[field]].append(row)
    nodes = {}
    for name, members_for_node in members.items():
        attributes = {"kind": field, "uid_members": [row["uid"] for row in members_for_node]}
        for column in members_for_node[0]:
            values = {row[column] for row in members_for_node}
            if len(values) == 1:
                attributes[column] = next(iter(values))
        nodes[name] = attributes
    return node_link(nodes, [asdict(edge) for edge in edges], directed=False)


def identity_graph(step: int, rows: list[dict]) -> dict:
    nodes = {row["uid"]: {"kind": "uid", **row} for row in rows}
    relations = set()
    for row in rows:
        uid = row["uid"]
        if step >= 1:
            device = row["deviceid"]
            nodes.setdefault(device, {"kind": "device"})
            relations.add((uid, device))
        if step >= 4:
            match = row["internal_matchid"]
            match_attributes = {"kind": "match", "preliminary_householdid": row["preliminary_householdid"]}
            if step >= 6:
                match_attributes.update(
                    internal_householdid=row["internal_householdid"], household_changed=row["household_changed"]
                )
            nodes.setdefault(match, match_attributes)
            relations.add((device, match))
        if step >= 3:
            household = row["internal_householdid"] if step >= 6 else row["preliminary_householdid"]
            nodes.setdefault(household, {"kind": "household", "phase": "final" if step >= 6 else "preliminary"})
            relations.add((match if step >= 4 else device, household))
    edges = [{"source": source, "target": target, "kind": "membership"} for source, target in sorted(relations)]
    return node_link(nodes, edges, directed=True)


def build_steps() -> list[dict]:
    """Return independent graph snapshots for input and all seven steps."""
    devices = collapse_graph(EXAMPLE_EDGES, UID_TO_DEVICE, keep_conflicts=True)
    matches = collapse_graph(devices, DEVICE_TO_MATCH, keep_conflicts=False)
    scoped_devices = tuple(edge for edge in devices if PRELIMINARY[edge.source] == PRELIMINARY[edge.target])
    edge_sets = (
        EXAMPLE_EDGES,
        tuple(edge for edge in EXAMPLE_EDGES if edge.same_device),
        devices,
        devices,
        scoped_devices,
        matches,
        matches,
        EXAMPLE_EDGES,
    )
    steps = []
    for number, edges in enumerate(edge_sets):
        rows = uid_assignments(number)
        steps.append(
            {
                "number": number,
                "title": TITLES[number],
                "note": NOTES[number],
                "assignment_mode": "fixed_java_verified_example",
                "evidence": evidence_graph(number, edges, rows),
                "identities": identity_graph(number, rows),
                "uid_assignments": rows,
                "excluded_relationships": (
                    [asdict(edge) for edge in devices if edge not in scoped_devices] if number == 4 else []
                ),
                "sources": SOURCES[number],
            }
        )
    steps[7]["full"] = full_graph(steps)
    return steps


def full_graph(steps: list[dict]) -> dict:
    """Combine final memberships with all three evidence resolutions, without reclustering."""
    final = steps[7]
    graph = deepcopy(final["identities"])
    graph["graph"] = {"mixed_edges": True, "hierarchical": False, "households": "final"}
    fields = {"uid": "uid", "device": "deviceid", "match": "internal_matchid", "household": "internal_householdid"}
    for node in graph["nodes"]:
        members = [row for row in final["uid_assignments"] if row[fields[node["kind"]]] == node["id"]]
        node["uid_members"] = [row["uid"] for row in members]
        for column in members[0]:
            values = {row[column] for row in members}
            if len(values) == 1:
                node[column] = next(iter(values))
    for edge in graph["links"]:
        edge.update(directed=True, layer="membership")
    for number, layer in ((0, "UID evidence"), (2, "Device evidence"), (5, "Match evidence")):
        for edge in steps[number]["evidence"]["links"]:
            graph["links"].append(
                {
                    **deepcopy(edge),
                    "key": len(graph["links"]),
                    "kind": "evidence",
                    "directed": False,
                    "layer": layer,
                }
            )
    return graph


def node_label(node: dict, *, step: int) -> str:
    """Use the same assignment annotations in both graph renderers."""
    label = node["id"]
    if node.get("uid_members") and node["uid_members"] != [node["id"]]:
        label += "\n" + ", ".join(node["uid_members"])
    for key, prefix in (
        ("deviceid", "device"),
        ("internal_matchid", "match"),
        ("preliminary_householdid", "pre-HH"),
    ):
        if key in node and node[key] != node["id"]:
            label += f"\n{prefix}: {node[key]}"
    if step >= 6 and "internal_householdid" in node:
        label += f"\nfinal HH: {node['internal_householdid']}"
    if node.get("household_changed"):
        label += "\nCHANGED HOUSEHOLD"
    if step == 7 and "matchid" in node:
        label += f"\nreturned match: {node['matchid']}"
    if node.get("kind") == "household":
        label += f"\n{node['phase']} household"
    return label


def node_color(node: dict) -> str:
    household = node.get("internal_householdid", node.get("preliminary_householdid", node["id"]))
    return {"H1": "#2563eb", "H2": "#c65a10", "H3": "#9333ea", "H4": "#0d9488"}.get(household, "#64748b")


def to_dot(graph: dict, *, step: int) -> str:
    """Render evidence (undirected) or membership (directed) without losing loops."""
    import graphviz  # noqa: PLC0415 - data-only SQL verification does not require the renderer

    dot = graphviz.Digraph(graph_attr={"rankdir": "LR", "nodesep": "0.45", "ranksep": "0.7"})
    dot.attr("node", shape="box", style="rounded", fontsize="13", fontname="Arial", margin="0.16")
    dot.attr("edge", fontsize="11", fontname="Arial")
    for node in graph["nodes"]:
        dot.node(
            node["id"],
            label=node_label(node, step=step),
            color=node_color(node) if node.get("current", True) else "#9ca3af",
            fontcolor="#172033" if node.get("current", True) else "#6b7280",
            penwidth="3" if node.get("household_changed") else "2",
        )
    for edge in graph["links"]:
        current = edge.get("current", True)
        if edge.get("directed", graph["directed"]):
            dot.edge(edge["source"], edge["target"], color="#0284c7" if current else "#a8afb9")
            continue
        same = edge["same_device"]
        conflict = edge["different_users"]
        label = format(edge["weight"], ".6g") + "\nrows " + ",".join(edge["source_rows"])
        if same:
            label += "\nsameDevice"
        if conflict:
            label += "\ndifferentUsers"
        dot.edge(
            edge["source"],
            edge["target"],
            label=label if current else "",
            dir="none",
            color=("#c0392b" if conflict else "#15803d" if same else "#64748b") if current else "#a8afb9",
            style="dashed" if conflict else "solid",
            penwidth="2" if same or conflict else "1",
        )
    return dot.source

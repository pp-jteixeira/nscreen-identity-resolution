"""Incremental presentation of Screen7 snapshots, without changing calculations."""

import hashlib
import json
from collections import Counter
from pathlib import Path

from example import node_label


def current_graph(step):
    number = step["number"]
    nodes = {n["id"]: dict(n) for n in step["evidence"]["nodes"]}
    links = [dict(e, directed=False) for e in step["evidence"]["links"]]
    identities = {n["id"]: n for n in step["identities"]["nodes"]}
    # Show mapping outputs when they are created, then again at final assignment.
    targets = {1: {"device"}, 4: {"match"}, 6: {"household"}, 7: {"device", "match", "household"}}.get(number, set())
    for edge in step["identities"]["links"]:
        target = identities[edge["target"]]
        if target["kind"] not in targets or target.get("phase") == "preliminary":
            continue
        for endpoint in (edge["source"], edge["target"]):
            nodes.setdefault(endpoint, dict(identities[endpoint]))
        links.append(dict(edge, directed=True))
    return {"nodes": list(nodes.values()), "links": links}


def incremental_graph(steps, number):
    nodes, edges = {}, {}
    for index, step in enumerate(steps[: number + 1]):
        graph = current_graph(step)
        for node in graph["nodes"]:
            seen = nodes.get(node["id"], {}).get("steps", [])
            nodes[node["id"]] = dict(node, steps=[*seen, index], details=node_label(node, step=index))
        occurrences = Counter()
        for original_edge in graph["links"]:
            # Snapshot-local edge indices are not relationship identities.
            edge = {k: v for k, v in original_edge.items() if k != "key"}
            signature = json.dumps(edge, sort_keys=True)
            occurrences[signature] += 1
            key = hashlib.sha256(f"{signature}:{occurrences[signature]}".encode()).hexdigest()
            entry = edges.setdefault(key, dict(edge, key=key, steps=[]))
            entry["steps"].append(index)
    for entry in [*nodes.values(), *edges.values()]:
        entry["current"] = number in entry["steps"]
        entry["history_note"] = (
            ("Current step" if entry["current"] else "Earlier context, not a current-step output")
            + "\nShown in steps: "
            + ", ".join(map(str, entry["steps"]))
        )
    positions = json.loads(Path(__file__).with_name("fixed_layout.json").read_text())["positions"]
    if set(positions) != {n["id"] for n in steps[-1]["full"]["nodes"]}:
        raise ValueError("Regenerate fixed_layout.json for the changed Screen7 dataset")
    bounds = {axis: 2 * (max(abs(p[axis]) for p in positions.values()) + 180) for axis in ("x", "y")}
    return {
        "directed": True,
        "multigraph": True,
        "graph": {"hierarchical": False, "incremental": True, "layout_bounds": bounds},
        "nodes": [dict(n, **positions[n["id"]]) for n in nodes.values()],
        "links": list(edges.values()),
    }

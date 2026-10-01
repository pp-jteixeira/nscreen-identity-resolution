"""Presentation-only history: no changes to pipeline calculations."""

import hashlib
import json
from collections import Counter


def incremental_graph(snapshots, number):
    """Union all snapshots; distinguish current, historical and future entries.

    Identical repeated edges share a history entry. Distinct stage/reason/rank
    records remain parallel edges, including duplicate occurrences within a step.
    """
    nodes, edges = {}, {}
    for index, snapshot in enumerate(snapshots):
        for node in snapshot["nodes"]:
            entry = nodes.setdefault(node["id"], dict(node, steps=[]))
            entry["steps"].append(index)
        occurrences = Counter()
        for edge in snapshot["links"]:
            signature = json.dumps(edge, sort_keys=True)
            occurrences[signature] += 1
            identifier = hashlib.sha256(f"{signature}:{occurrences[signature]}".encode()).hexdigest()
            entry = edges.setdefault(identifier, dict(edge, id=identifier, steps=[]))
            entry["steps"].append(index)
    for entry in [*nodes.values(), *edges.values()]:
        entry["current"] = number in entry["steps"]
        entry["first_step"] = entry["steps"][0]
        entry["last_step"] = entry["steps"][-1]
        entry["future"] = entry["first_step"] > number
        status = (
            "Current step"
            if entry["current"]
            else "Future step preview (not yet produced)"
            if entry["future"]
            else "Earlier step context (not a current assignment)"
        )
        entry["details"] += f"\n\n{status}\nShown in steps: {', '.join(map(str, entry['steps']))}"
    return {
        "directed": True,
        "multigraph": True,
        "incremental": True,
        "nodes": list(nodes.values()),
        "links": list(edges.values()),
    }

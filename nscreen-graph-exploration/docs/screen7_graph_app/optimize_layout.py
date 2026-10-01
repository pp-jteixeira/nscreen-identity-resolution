"""Optimize the final Screen7 graph offline; emit captured coordinates as JSON.

From this directory, run ../../../.venv/bin/python optimize_layout.py.
Requires networkx and numpy from the shared repository environment.
This is a NetworkX force simulation, not vis-network browser physics.
No identity calculations or graph relationships are modified.
"""

import argparse
import json
import math

import networkx as nx
from example import build_steps


def crossing_count(graph, positions):
    edges = [(a, b) for a, b in graph.edges if a != b]

    def side(a, b, c):
        return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])

    count = 0
    for i, (a, b) in enumerate(edges):
        for c, d in edges[i + 1 :]:
            if len({a, b, c, d}) != 4:
                continue
            pa, pb, pc, pd = (positions[n] for n in (a, b, c, d))
            count += side(pa, pb, pc) * side(pa, pb, pd) < 0 and side(pc, pd, pa) * side(pc, pd, pb) < 0
    return count


def optimize(trials=24, iterations=12000):
    final = build_steps()[7]["full"]
    graph = nx.Graph()
    graph.add_nodes_from(sorted(n["id"] for n in final["nodes"]))
    graph.add_edges_from(sorted((e["source"], e["target"]) for e in final["links"]))
    positions, reports = {}, []
    cursor = 0
    for component in sorted(nx.connected_components(graph), key=lambda c: (-len(c), sorted(c))):
        subgraph = graph.subgraph(sorted(component)).copy()
        best = None
        for seed in range(trials):
            candidate = nx.spring_layout(
                subgraph, seed=seed, iterations=iterations, threshold=0, weight=None, method="force"
            )
            distance = min(
                math.dist(candidate[a], candidate[b]) for i, a in enumerate(subgraph) for b in list(subgraph)[i + 1 :]
            )
            candidate = {n: (float(p[0]) * 170 / distance, float(p[1]) * 170 / distance) for n, p in candidate.items()}
            xs, ys = [p[0] for p in candidate.values()], [p[1] for p in candidate.values()]
            width, height = max(xs) - min(xs), max(ys) - min(ys)
            score = (crossing_count(subgraph, candidate), width * height, max(width, height))
            if best is None or score < best[0]:
                best = (score, seed, candidate)
        score, seed, candidate = best
        xs, ys = [p[0] for p in candidate.values()], [p[1] for p in candidate.values()]
        # Rotate the whole component, preserving the optimized geometry.
        if max(xs) - min(xs) < max(ys) - min(ys):
            candidate = {n: (-p[1], p[0]) for n, p in candidate.items()}
        xs, ys = [p[0] for p in candidate.values()], [p[1] for p in candidate.values()]
        for n, p in candidate.items():
            positions[n] = (p[0] - min(xs) + cursor, p[1] - (max(ys) + min(ys)) / 2)
        cursor += max(xs) - min(xs) + 260
        reports.append(dict(nodes=len(component), selected_seed=seed, straight_edge_crossings=score[0]))
    center = (max(p[0] for p in positions.values()) + min(p[0] for p in positions.values())) / 2
    positions = {n: {"x": round(p[0] - center, 4), "y": round(p[1], 4)} for n, p in positions.items()}
    return dict(
        algorithm="NetworkX spring_layout (Fruchterman-Reingold), independently per connected component",
        networkx_version=nx.__version__,
        trials_per_component=trials,
        iterations_per_trial=iterations,
        total_iterations=len(reports) * trials * iterations,
        graph_nodes=len(final["nodes"]),
        graph_relationships=len(final["links"]),
        minimum_spacing=170,
        components=reports,
        straight_edge_crossings=sum(r["straight_edge_crossings"] for r in reports),
        note="Crossing score excludes self-loops and shared endpoints; browser curves and labels can still overlap. Unit layout weights are visual only.",
        positions=positions,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trials", type=int, default=24)
    parser.add_argument("--iterations", type=int, default=12000)
    args = parser.parse_args()
    print(json.dumps(optimize(args.trials, args.iterations), indent=2))  # noqa: T201 - captured JSON output

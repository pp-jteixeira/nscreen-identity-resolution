import copy
import json
import math
from pathlib import Path

from alignment_example import build_example, build_steps, graph_for
from alignment_graph import to_html, to_network, with_stable_positions
from alignment_history import incremental_graph


def test_incremental_future_preview_and_current_focus():
    data = build_example()
    snapshots = [graph_for(step, data) for step in build_steps(data)]
    original = copy.deepcopy(snapshots)
    previous_nodes, previous_edges = set(), set()
    for number, snapshot in enumerate(snapshots):
        graph = incremental_graph(snapshots, number)
        nodes = {n["id"] for n in graph["nodes"]}
        edges = {e["id"] for e in graph["links"]}
        assert previous_nodes <= nodes
        assert previous_edges <= edges
        assert {n["id"] for n in graph["nodes"] if n["current"]} == {n["id"] for n in snapshot["nodes"]}
        assert sum(e["current"] for e in graph["links"]) == len(snapshot["links"])
        assert all(e["future"] == (e["first_step"] > number) for e in graph["links"])
        assert len(nodes) == 45
        assert len(edges) == 146
        if number < 15:
            assert next(n for n in graph["nodes"] if n["id"] == "C1")["future"]
        previous_nodes, previous_edges = nodes, edges
    assert snapshots == original
    assert sum(e["current"] for e in incremental_graph(snapshots, 0)["links"]) == len(snapshots[0]["links"])
    assert not any(e["future"] for e in incremental_graph(snapshots, len(snapshots) - 1)["links"])


def test_duplicate_occurrences_and_stage_changes_remain_distinct():
    node = dict(id="u", kind="uid", details="u")
    edge = dict(source="u", target="u", details="source row", label="source", directed=True, kind="membership")
    snapshots = [dict(nodes=[node], links=[edge, edge]), dict(nodes=[node], links=[dict(edge, details="initial row")])]
    graph = incremental_graph(snapshots, 1)
    assert len(graph["links"]) == 3
    assert sum(e["current"] for e in graph["links"]) == 1
    assert "source row" in graph["links"][0]["details"]
    assert "Shown in steps: 0" in graph["links"][0]["details"]


def test_muted_rendering_and_stable_positions():
    data = build_example()
    steps = build_steps(data)
    snapshots = [graph_for(step, data) for step in steps]
    universe = graph_for(steps[-1], data, full=True)
    early = with_stable_positions(incremental_graph(snapshots, 1), universe)
    late = with_stable_positions(incremental_graph(snapshots, 5), universe)
    coordinates = lambda g: {n["id"]: (n["x"], n["y"]) for n in g["nodes"]}
    assert coordinates(early) == coordinates(late)
    network = to_network(early)
    assert network.options["physics"]["enabled"] is False
    rendered = {e["id"]: e for e in network.edges}
    initial = with_stable_positions(incremental_graph(snapshots, 0), universe)
    initial_rendered = {e["id"]: e for e in to_network(initial).edges}
    current_ip_edges = [
        e
        for e in initial["links"]
        if e.get("current") and e.get("origin") == "ip_collocation"
    ]
    assert current_ip_edges
    for edge in current_ip_edges:
        assert initial_rendered[edge["id"]]["color"]["color"] == "#0f766e"
        assert initial_rendered[edge["id"]]["dashes"] == [12, 6]
        assert initial_rendered[edge["id"]]["width"] == 3.5
    remainder = with_stable_positions(incremental_graph(snapshots, 14), universe)
    remainder_rendered = {e["id"]: e for e in to_network(remainder).edges}
    rejected_ip_edges = [
        e
        for e in remainder["links"]
        if e.get("current")
        and e.get("origin") == "ip_collocation"
        and e["kind"] == "rejected"
    ]
    assert rejected_ip_edges
    for edge in rejected_ip_edges:
        assert remainder_rendered[edge["id"]]["color"]["color"] == "#dc2626"
        assert remainder_rendered[edge["id"]]["dashes"] == [12, 6]
    for edge in early["links"]:
        if edge["future"]:
            assert rendered[edge["id"]]["color"]["color"] == "#e2e5e9"
            assert rendered[edge["id"]]["width"] == 1
            assert rendered[edge["id"]]["label"] == ""
            assert "Future step preview" in rendered[edge["id"]]["title"]
        elif not edge["current"]:
            assert rendered[edge["id"]]["color"]["color"] == "#a8afb9"
            assert rendered[edge["id"]]["width"] >= 1.5
            assert rendered[edge["id"]]["label"] == ""
            assert "Earlier step context" in rendered[edge["id"]]["title"]
            if edge.get("origin") == "ip_collocation":
                assert rendered[edge["id"]]["dashes"] == [12, 6]
    assert any(n["color"]["background"] == "#f1f3f5" for n in network.nodes)
    final = with_stable_positions(incremental_graph(snapshots, len(steps) - 1), universe)
    final["focus_final"] = True
    final_network = to_network(final)
    final_nodes = {n["id"]: n for n in final_network.nodes}
    final_edges = {e["id"]: e for e in final_network.edges}
    historical_nodes = [n for n in final["nodes"] if not n["current"]]
    historical_edges = [e for e in final["links"] if not e["current"]]
    final_ip_edges = [
        e for e in final["links"] if e["current"] and e.get("origin") == "ip_collocation"
    ]
    assert historical_nodes
    assert historical_edges
    assert final_ip_edges
    for node in historical_nodes:
        rendered_node = final_nodes[node["id"]]
        assert rendered_node["color"] == {"background": "#fafafa", "border": "#e5e7eb"}
        assert rendered_node["font"]["color"] == "#d1d5db"
        assert rendered_node["borderWidth"] == 1
    for edge in historical_edges:
        assert final_edges[edge["id"]]["color"]["color"] == "#e5e7eb"
        assert final_edges[edge["id"]]["width"] == 0.8
    for edge in final_ip_edges:
        rendered_edge = final_edges[edge["id"]]
        assert rendered_edge["color"]["color"] == "#cbd5e1"
        assert rendered_edge["font"]["color"] == "#cbd5e1"
        assert rendered_edge["dashes"] == [12, 6]
        assert rendered_edge["width"] == 1.2
    html = to_html(early)
    assert "border: 1px solid #d1d5db !important" in html
    assert "box-sizing: border-box" in html
    assert "padding: 0 !important" in html
    assert "network.moveTo" in html
    assert "network.once('stabilizationIterationsDone'" not in html


def test_layout_has_room_for_nodes_and_relationships():
    data = build_example()
    steps = build_steps(data)
    universe = graph_for(steps[-1], data, full=True)
    graph = with_stable_positions(universe, universe)
    nodes = graph["nodes"]
    for i, a in enumerate(nodes):
        for b in nodes[i + 1 :]:
            assert math.hypot(a["x"] - b["x"], a["y"] - b["y"]) >= 140


def test_captured_layout_covers_full_incremental_history():
    capture = json.loads(Path(__file__).with_name("fixed_layout.json").read_text())
    data = build_example()
    steps = build_steps(data)
    snapshots = [graph_for(step, data) for step in steps]
    final = incremental_graph(snapshots, len(steps) - 1)
    assert capture["graph_nodes"] == len(final["nodes"])
    assert capture["graph_relationships"] == len(final["links"])
    assert capture["iterations_per_trial"] == 12000
    assert capture["trials_per_component"] == 24
    bounds = None
    for number in range(len(steps)):
        graph = with_stable_positions(incremental_graph(snapshots, number), final)
        if bounds is None:
            bounds = graph["layout_bounds"]
        assert graph["layout_bounds"] == bounds
        for node in graph["nodes"]:
            assert {axis: node[axis] for axis in ("x", "y")} == capture["positions"][node["id"]]
            assert all(math.isfinite(node[axis]) for axis in ("x", "y"))
        assert not to_network(graph).options["physics"]["enabled"]

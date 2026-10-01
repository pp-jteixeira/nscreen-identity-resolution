import copy
import json
import math
from pathlib import Path

from example import build_steps, to_dot
from interactive_graph import to_html, to_network
from screen7_history import current_graph, incremental_graph
from streamlit.testing.v1 import AppTest


def test_captured_force_positions_and_viewport():
    capture = json.loads(Path(__file__).with_name("fixed_layout.json").read_text())
    assert capture["total_iterations"] == 576000
    assert capture["graph_nodes"] == 29
    assert capture["graph_relationships"] == 55
    bounds = None
    for number in range(8):
        graph = incremental_graph(build_steps(), number)
        if bounds is None:
            bounds = graph["graph"]["layout_bounds"]
        assert graph["graph"]["layout_bounds"] == bounds
        for node in graph["nodes"]:
            for axis in ("x", "y"):
                assert node[axis] == capture["positions"][node["id"]][axis]
                assert math.isfinite(node[axis])
                assert abs(node[axis]) < bounds[axis] / 2
        network = to_network(graph, step=number)
        assert all(n["physics"] is False for n in network.nodes)
        assert json.dumps(bounds) in to_html(network)


def test_incremental_history_no_future_or_preliminary_nodes():
    steps = build_steps()
    original = copy.deepcopy(steps)
    previous_edges, previous_nodes, coordinates = set(), set(), {}
    for number in range(8):
        graph = incremental_graph(steps, number)
        nodes = {n["id"] for n in graph["nodes"]}
        edges = {e["key"] for e in graph["links"]}
        assert previous_nodes <= nodes
        assert previous_edges <= edges
        assert "H2" not in nodes
        assert all(n.get("phase") != "preliminary" for n in graph["nodes"])
        assert all(max(e["steps"]) <= number for e in graph["links"])
        if number < 1:
            assert not any(n.startswith("D") for n in nodes)
        if number < 4:
            assert not any(n.startswith("M") for n in nodes)
        if number < 6:
            assert not any(n.startswith("H") for n in nodes)
        assert sum(e["current"] for e in graph["links"]) == len(current_graph(steps[number])["links"])
        for n in graph["nodes"]:
            point = (n["x"], n["y"])
            assert coordinates.setdefault(n["id"], point) == point
        previous_nodes, previous_edges = nodes, edges
    assert steps == original
    final = incremental_graph(steps, 7)
    assert len(final["nodes"]) == 29
    assert len(final["links"]) == 55
    assert len(incremental_graph(steps, 0)["links"]) == 11
    assert next(n for n in final["nodes"] if n["id"] == "u9")["matchid"] == 0
    points = list(coordinates.values())
    for i, a in enumerate(points):
        for b in points[i + 1 :]:
            assert math.dist(a, b) >= 140


def test_history_renderers_keep_gray_edges_and_provenance():
    graph = incremental_graph(build_steps(), 4)
    network = to_network(graph, step=4)
    assert len(network.edges) == len(graph["links"])
    assert network.options["physics"]["enabled"] is False
    edges = {e["id"]: e for e in network.edges}
    for row in graph["links"]:
        rendered = edges[row["key"]]
        assert "Shown in steps" in rendered["title"]
        if not row["current"]:
            assert rendered["color"]["color"] == "#a8afb9"
            assert rendered["width"] >= 1.5
            assert rendered["label"] == ""
    assert "network.moveTo" in to_html(network)
    assert "#a8afb9" in to_dot(graph, step=4)
    # F/K device bridges remain visible but inactive during scoped matching.
    bridges = [e for e in graph["links"] if e["source"].startswith("D") and e.get("source_rows") in [("F",), ("K",)]]
    assert len(bridges) == 2
    assert not any(e["current"] for e in bridges)


def test_incremental_ui_forward_backward_pyvis_only():
    app = AppTest.from_file(str(Path(__file__).parent / "streamlit_app.py"), default_timeout=20).run()
    assert not app.exception
    assert not app.segmented_control
    assert app.toggle(key="physics").disabled
    for number in (1, 4, 6, 7, 0):
        app.radio(key="step").set_value(number).run()
        assert not app.exception
    assert not app.selectbox
    assert not app.get("graphviz_chart")

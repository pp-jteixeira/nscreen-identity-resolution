import re
from collections import Counter
from copy import deepcopy
from pathlib import Path

import pytest
from example import EXAMPLE_EDGES, UID_TO_DEVICE, build_steps, collapse_graph, to_dot
from interactive_graph import GRAPH_HEIGHT_PX, NODE_STYLES, to_html, to_network
from streamlit.testing.v1 import AppTest

HERE = Path(__file__).parent


def test_input_matches_documentation():
    guide = (HERE.parent / "udaf-calc-screen7-ids-evaluator.md").read_text()
    rows = re.findall(
        r"^\| ([A-K]) \| (u\d+) \| (u\d+) \| ([\d.]+) \| (true|false) \| (true|false) \|$", guide, re.MULTILINE
    )
    documented = [
        (row, source, target, float(weight), same == "true", conflict == "true")
        for row, source, target, weight, same, conflict in rows
    ]
    assert documented == [
        (edge.source_rows[0], edge.source, edge.target, edge.weight, edge.same_device, edge.different_users)
        for edge in EXAMPLE_EDGES
    ]


def test_collapses_preserve_provenance_and_internal_edges():
    graph = collapse_graph(EXAMPLE_EDGES, UID_TO_DEVICE, keep_conflicts=True)
    by_pair = {(edge.source, edge.target): edge for edge in graph}
    assert len(graph) == 10
    assert by_pair["D1", "D1"].weight == 0.00001
    assert not by_pair["D1", "D1"].same_device
    assert by_pair["D1", "D2"].weight == 7.0
    assert by_pair["D1", "D2"].source_rows == ("B", "C")
    assert by_pair["D5", "D6"].different_users
    match_graph = build_steps()[5]["evidence"]
    assert len(match_graph["links"]) == 8
    assert not any(edge["different_users"] for edge in match_graph["links"])
    assert sorted(row for edge in match_graph["links"] for row in edge["source_rows"]) == list("ABCDEFGHIJK")


def test_all_steps_keep_every_uid_without_future_assignments():
    steps = build_steps()
    assert [len(step["evidence"]["links"]) for step in steps] == [11, 4, 10, 10, 8, 8, 8, 11]
    assert [len(step["evidence"]["nodes"]) for step in steps] == [12, 12, 8, 8, 8, 6, 6, 12]
    assert "preliminary_householdid" not in steps[2]["uid_assignments"][0]
    assert "internal_matchid" not in steps[3]["uid_assignments"][0]
    assert "matchid" not in steps[6]["uid_assignments"][0]
    for step in steps:
        assert {row["uid"] for row in step["uid_assignments"]} == set(UID_TO_DEVICE)
        for kind in ("evidence", "identities"):
            ids = {node["id"] for node in step[kind]["nodes"]}
            assert 0 not in ids
            assert "0" not in ids
            assert all(edge["source"] in ids and edge["target"] in ids for edge in step[kind]["links"])


def test_household_move_and_zero_sentinels():
    steps = build_steps()
    preliminary = {row["uid"]: row["preliminary_householdid"] for row in steps[3]["uid_assignments"]}
    assert len(set(preliminary.values())) == 4
    assert preliminary["u4"] == preliminary["u5"] == preliminary["u6"] == "H2"
    output = {row["uid"]: row for row in steps[7]["uid_assignments"]}
    assert {row["householdid"] for row in output.values()} == {"H1", "H3", "H4"}
    assert {uid for uid, row in output.items() if row["household_changed"]} == {"u4", "u5", "u6"}
    assert output["u4"]["householdid"] == output["u5"]["householdid"] == output["u6"]["householdid"] == "H1"
    assert output["u4"]["matchid"] == output["u5"]["matchid"] == output["u6"]["matchid"] == "M2"
    assert output["u9"]["matchid"] == output["u12"]["matchid"] == 0
    assert output["u9"]["internal_matchid"] != output["u12"]["internal_matchid"]
    assert output["u9"]["householdid"] != output["u12"]["householdid"]


def test_cross_household_bridges_reappear_after_match_grouping():
    steps = build_steps()
    scoped_rows = {row for edge in steps[4]["evidence"]["links"] for row in edge["source_rows"]}
    assert scoped_rows == set("ABCDEGHIJ")
    excluded = {row for edge in steps[4]["excluded_relationships"] for row in edge["source_rows"]}
    assert excluded == {"F", "K"}
    match_edges = {(edge["source"], edge["target"]): edge for edge in steps[5]["evidence"]["links"]}
    assert match_edges["M1", "M2"]["weight"] == 1.0
    assert match_edges["M1", "M3"]["weight"] == 0.25


def test_documented_output_matches_app():
    guide = (HERE.parent / "udaf-calc-screen7-ids-evaluator.md").read_text()
    output_section = guide.split("The evaluator returns this array of structs", 1)[1].split("## Why", 1)[0]
    documented = re.findall(r"^\| (u\d+) \| (D\d+) \| (M\d+|0) \| (H\d+) \|$", output_section, re.MULTILINE)
    rows = build_steps()[7]["uid_assignments"]
    assert documented == [(row["uid"], row["deviceid"], str(row["matchid"]), row["householdid"]) for row in rows]


def test_streamlit_navigation_and_views():
    app = AppTest.from_file(str(HERE / "streamlit_app.py"), default_timeout=15).run()
    assert not app.exception
    assert len(app.get("popover")) == 1
    assert not any(child.type in ("caption", "info", "markdown") for child in app.main.children.values())
    for number in range(8):
        app.radio(key="step").set_value(number).run()
        assert not app.exception
        assert not app.segmented_control
        assert not any(
            "Relationships" in caption.value or "Identity mappings" in caption.value for caption in app.caption
        )
        assert app.sidebar.subheader[0].value.startswith(f"{number}.")
        assert app.sidebar.markdown[0].value == build_steps()[number]["note"]
        assert not any(header.value.startswith(f"{number}.") for header in app.main.subheader)
        assignments = next(frame.value for frame in app.dataframe if "numeric_uid" in frame.value.columns)
        assert len(assignments) == 12
        assert "new vis.Network" in app.get("iframe")[0].proto.srcdoc
    assert not app.exception
    assert "returned match: 0" in app.get("iframe")[0].proto.srcdoc
    assert "CHANGED HOUSEHOLD" in app.get("iframe")[0].proto.srcdoc
    assert not app.selectbox
    assert not app.get("graphviz_chart")
    transitions = next(frame.value for frame in app.dataframe if "changed" in frame.value.columns)
    assert transitions.loc[transitions["changed"], "match"].tolist() == ["M2"]


@pytest.mark.parametrize("number", range(8))
@pytest.mark.parametrize("view", ["evidence", "identities"])
def test_interactive_graph_preserves_snapshots(number, view):
    graph = build_steps()[number][view]
    original = deepcopy(graph)
    network = to_network(graph, step=number)
    assert graph == original
    assert {node["id"] for node in network.nodes} == {node["id"] for node in graph["nodes"]}
    assert [(edge["from"], edge["to"]) for edge in network.edges] == [
        (edge["source"], edge["target"]) for edge in graph["links"]
    ]
    for rendered, source in zip(network.edges, graph["links"], strict=True):
        assert rendered["arrows"]["to"]["enabled"] == graph["directed"]
        if not graph["directed"]:
            assert rendered["dashes"] == source["different_users"]
            assert f"{source['weight']:.6g}" in rendered["label"]
            assert ",".join(source["source_rows"]) in rendered["label"]
    assert network.options["layout"]["hierarchical"]["enabled"] == graph["directed"]
    assert "new vis.Network" in to_html(network)


def test_interactive_annotations_and_controls():
    graph = build_steps()[7]["evidence"]
    network = to_network(graph, step=7, physics=False)
    nodes = {node["id"]: node for node in network.nodes}
    assert "H2 → H1" in nodes["u4"]["label"]
    assert "CHANGED HOUSEHOLD" in nodes["u4"]["title"]
    assert "returned match: 0" in nodes["u9"]["label"]
    assert not network.options["physics"]["enabled"]
    assert network.options["interaction"]["navigationButtons"]
    assert network.height == f"{GRAPH_HEIGHT_PX}px"
    detailed = to_network(graph, step=7, detailed_labels=True)
    assert "CHANGED HOUSEHOLD" in next(node for node in detailed.nodes if node["id"] == "u4")["label"]


def test_interactive_graph_does_not_deduplicate_parallel_edges():
    graph = deepcopy(build_steps()[2]["evidence"])
    graph["links"].append(deepcopy(graph["links"][0]))
    assert len(to_network(graph, step=2).edges) == len(graph["links"])


def test_interactive_node_types_have_distinct_shapes_and_backgrounds():
    network = to_network(build_steps()[7]["full"], step=7)
    nodes = {node["id"]: node for node in network.nodes}
    for node_id, kind in (("u1", "uid"), ("D1", "device"), ("M1", "match"), ("H1", "household")):
        assert nodes[node_id]["shape"] == NODE_STYLES[kind]["shape"]
        assert nodes[node_id]["color"]["background"] == NODE_STYLES[kind]["background"]
    assert len({NODE_STYLES[kind]["shape"] for kind in ("uid", "device", "match", "household")}) == 4
    assert len({NODE_STYLES[kind]["background"] for kind in ("uid", "device", "match", "household")}) == 4


def test_collapsed_graph_node_kinds_receive_identity_styles():
    network = to_network(build_steps()[5]["evidence"], step=5)
    assert all(node["shape"] == NODE_STYLES["match"]["shape"] for node in network.nodes)


def test_final_full_graph_keeps_all_layers_and_memberships():
    steps = build_steps()
    graph = steps[7]["full"]
    nodes = {node["id"]: node for node in graph["nodes"]}
    assert Counter(node["kind"] for node in nodes.values()) == {"uid": 12, "device": 8, "match": 6, "household": 3}
    assert Counter(edge["layer"] for edge in graph["links"]) == {
        "membership": 26,
        "UID evidence": 11,
        "Device evidence": 10,
        "Match evidence": 8,
    }
    memberships = {(edge["source"], edge["target"]) for edge in graph["links"] if edge["directed"]}
    assert len(memberships) == 26
    for row in steps[7]["uid_assignments"]:
        assert (row["uid"], row["deviceid"]) in memberships
        assert (row["deviceid"], row["internal_matchid"]) in memberships
        assert (row["internal_matchid"], row["internal_householdid"]) in memberships
    assert not {"0", "H2"} & nodes.keys()
    assert nodes["M2"]["preliminary_householdid"] == "H2"
    assert nodes["M2"]["internal_householdid"] == "H1"
    assert nodes["M4"]["matchid"] == nodes["M6"]["matchid"] == 0
    for number, layer in ((0, "UID evidence"), (2, "Device evidence"), (5, "Match evidence")):
        evidence = [edge for edge in graph["links"] if edge["layer"] == layer]
        for edge, source in zip(evidence, steps[number]["evidence"]["links"], strict=True):
            assert {key: edge[key] for key in source if key != "key"} == {
                key: value for key, value in source.items() if key != "key"
            }
    assert all(edge["source"] in nodes and edge["target"] in nodes for edge in graph["links"])


def test_final_full_graph_renderers_preserve_mixed_edge_directions():
    graph = build_steps()[7]["full"]
    network = to_network(graph, step=7)
    assert len(network.nodes) == 29
    assert len(network.edges) == 55
    assert sum(edge["arrows"]["to"]["enabled"] for edge in network.edges) == 26
    assert sum(edge["from"] == edge["to"] for edge in network.edges) == 8
    assert not network.options["layout"]["hierarchical"]["enabled"]
    dot = to_dot(graph, step=7)
    assert dot.count("dir=none") == 29
    assert "M2 -> H1" in dot
    assert "M2 -> H2" not in dot
    assert "new vis.Network" in to_html(network)


def test_streamlit_final_incremental_graph_and_navigation_back():
    app = AppTest.from_file(str(HERE / "streamlit_app.py"), default_timeout=15).run()
    app.radio(key="step").set_value(7).run()
    app.session_state["view"] = "Full graph"  # A stale session must not restore the removed view.
    app.run()
    assert not app.exception
    assert not app.segmented_control
    graph_nodes = next(
        frame.value for frame in app.dataframe if "history_note" in frame.value.columns and "id" in frame.value.columns
    )
    assert len(graph_nodes) == 29
    assert "Earlier context" in app.get("iframe")[0].proto.srcdoc
    app.session_state["renderer"] = "Static (Graphviz)"
    app.run()
    assert not app.exception
    assert not app.selectbox
    assert not app.get("graphviz_chart")
    assert "new vis.Network" in app.get("iframe")[0].proto.srcdoc
    app.radio(key="step").set_value(3).run()
    assert not app.exception
    assert not any("29 nodes · 55 relationships" in caption.value for caption in app.caption)


def test_streamlit_forces_canvas_to_match_iframe_height():
    app = AppTest.from_file(str(HERE / "streamlit_app.py"), default_timeout=15).run()
    srcdoc = app.get("iframe")[0].proto.srcdoc
    assert f"height: {GRAPH_HEIGHT_PX}px;" in srcdoc
    assert "#mynetwork { padding: 0 !important; box-sizing: border-box; }" in srcdoc
    assert "height: 650px;" not in srcdoc


def test_interactive_tooltips_use_newlines_not_literal_html_tags():
    html = to_html(to_network(build_steps()[7]["full"], step=7))
    assert "white-space: pre-line" in html
    assert "u10\\nu10" not in html
    assert "u10\\ndevice: D7\\nmatch: M5" in html
    assert "u10&lt;br&gt;device" not in html

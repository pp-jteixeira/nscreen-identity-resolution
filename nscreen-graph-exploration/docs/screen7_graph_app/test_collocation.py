from pathlib import Path

from collocation_example import UIDS, build_collocation_steps, collocation_graph
from interactive_graph import to_html, to_network
from streamlit.testing.v1 import AppTest


def test_ip_and_first_party_weight_semantics():
    steps = build_collocation_steps()
    first = [row for row in steps[2]["rows"] if row["day"] == "2026-09-09"]
    assert len(first) == 7  # One ip1 pair plus all six ip2 pairs, including B-D.

    def ab(rows):
        return [r for r in rows if (r["uid1"], r["uid2"]) == (UIDS["A"], UIDS["B"])]

    assert [row["weight"] for row in ab(steps[3]["rows"])] == [0.75, 0.25, 0.25]
    assert ab(steps[4]["rows"])[0]["weight"] == 1.25
    assert len(ab(steps[6]["rows"])) == 3
    assert ab(steps[7]["rows"])[0]["weight"] == 3
    assert ab(steps[8]["rows"])[0]["weight"] == 3
    assert ab(steps[8]["rows"])[0]["samedevice"]
    assert len(steps[8]["rows"]) == 7
    assert all(row["kept"] for row in steps[8]["rows"])
    assert sorted(row["uid_count"] for row in steps[1]["ip_stats"] if not row["kept"]) == [1, 9]
    assert not next(row for row in steps[4]["rows"] if row["uid1"] == UIDS["E"])["kept"]


def test_screen7_only_navigation():
    app = AppTest.from_file(str(Path(__file__).parent / "streamlit_app.py"), default_timeout=20).run()
    assert not app.exception
    assert not app.tabs
    assert len(app.sidebar.radio) == 1
    assert app.sidebar.radio[0].label == "Grouping step"
    # A browser session left on the removed tab must still render Screen7.
    app.session_state["pipeline_phase"] = "IP collocation & first party"
    app.run()
    assert not app.exception
    assert not app.tabs
    assert len(app.sidebar.radio) == 1
    assert app.sidebar.radio[0].label == "Grouping step"


def test_standalone_collocation_full_graph():
    steps = build_collocation_steps()
    for number in range(9):
        graph = collocation_graph(steps, number)
        assert "new vis.Network" in to_html(to_network(graph, step=0))
    graph = collocation_graph(steps, 8, full=True)
    assert {node["kind"] for node in graph["nodes"]} == {"uid", "ip", "event"}
    assert sum(edge.get("layer") == "clean" for edge in graph["links"]) == 7

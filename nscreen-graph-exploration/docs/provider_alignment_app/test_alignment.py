from collections import Counter
from pathlib import Path

from alignment_example import (
    ALIASES,
    EDGES,
    EXPERIAN,
    LIVERAMP,
    REPO_ROOT,
    THROTLE,
    align,
    build_example,
    build_steps,
    final_result,
    graph_for,
    propagate,
)
from alignment_graph import HEIGHT, to_html, to_network
from streamlit.testing.v1 import AppTest


def test_document_fixture_and_production_stages():
    d = build_example()
    assert (len(THROTLE), len(LIVERAMP), len(EXPERIAN), len(EDGES)) == (14, 12, 5, 8)
    assert [(r["left"], r["right"]) for r in d["job1"]["mapping"]] == [(101, 201), (102, 202)]
    assert [(r["count1"], r["count2"], r["accepted"]) for r in d["job1"]["limited"] if r["left"] == 106] == [
        (2, 1, False),
        (2, 1, False),
    ]
    assert Counter(r["stage"] for r in d["staged"]) == {
        "lrth": 21,
        "initial": 24,
        "connected_ns": 8,
        "stage1": 2,
        "stage2": 1,
        "louvain": 2,
    }
    assert {r["uid"] for r in d["initial"] if r["reason"] == "LRTHEX"} == {"v1", "v2", "v3", "v9", "v15"}
    assert [r["weight"] for r in d["p1"]["ranked"]] == [10, 4, 4, 4]
    assert {(r["uid"], r["matchid"]) for r in d["stage1"]} == {("v17", 201), ("v20", 105)}
    assert [(r["uid"], r["matchid"]) for r in d["stage2"]] == [("v18", 201)]
    assert len(d["result"]) == 29
    assert len({r["uid"] for r in d["result"]}) == 26
    assert {r["uid"] for r in d["initial"] if r["reason"] == "LREX"} == {"v30", "v31", "v32"}
    assert not {"v33", "v34"} & {r["uid"] for r in d["staged"]}
    assert not {"v33", "v34"} & {r["uid"] for r in d["diagnostic"]}
    assert {(r["uid1"], r["uid2"]) for r in d["remainder"]} == {("v19", "v21")}
    assert next(r for r in d["remainder_checks"] if r["uid1"] == "v33")["same_geo"] is False
    assert Counter(r["uid"] for r in d["result"])["v6"] == 3
    assert Counter(r["uid"] for r in d["result"])["v13"] == 2
    assert {r["matchid"] for r in d["result"] if r["reason"] == "LU"} == {"901"}
    assert all(r["householdid"] == "" for r in d["result"])


def test_count2_and_post_filter_counts():
    def rows(pairs):
        return [dict(uid=u, matchid=m, householdid=0, stable=True, reason="LR") for u, m in pairs]

    tied = align(rows([("a", 1), ("b", 2)]), rows([("a", 3), ("b", 3)]))
    assert not tied["mapping"]
    assert all(r["count1"] == 1 and r["count2"] == 2 for r in tied["limited"])
    # Second competitor prefers a stronger alternative, so it cannot cause count2=2.
    filtered = align(rows([("a", 1), ("b", 2), ("c", 2), ("d", 2)]), rows([("a", 3), ("b", 3), ("c", 4), ("d", 4)]))
    assert {(r["left"], r["right"]) for r in filtered["mapping"]} == {(1, 3), (2, 4)}


def test_cap_after_uid_winner_and_stable_boost():
    seeds = [dict(uid=u, matchid=m, householdid=0, stable=s) for u, m, s in [("a", 1, True), ("b", 2, False)]]
    edges = [dict(uid1=a, uid2=b, weight=w) for a, b, w in [("a", "x", 3), ("a", "y", 4), ("b", "x", 5)]]
    p = propagate(seeds, edges, cap=1)
    assert [(r["uid"], r["matchid"]) for r in p["output"]] == [("y", 1)]
    assert next(r for r in p["capped"] if r["uid"] == "x")["kept"] is False
    assert next(r for r in p["ranked"] if r["uid"] == "x" and r["matchid"] == 1)["weight"] == 6


def test_final_filters():
    row = dict(uid="valid", matchid=201, householdid=0, stable=True, reason="LR", stage="initial")
    assert final_result([row]) == [dict(uid="valid", matchid="S_201", householdid="", reason="LR")]
    assert not final_result(
        [
            dict(row, uid="LR_abc", reason="IC"),
            dict(row, uid="01-!*_"),
            dict(row, matchid=0),
            dict(row, stage="connected_ns"),
        ]
    )


def test_graph_and_source_coverage():
    d = build_example()
    steps = build_steps(d)
    assert len(steps) == 19
    for step in steps:
        graph = graph_for(step, d)
        ids = {n["id"] for n in graph["nodes"]}
        assert graph["links"]
        assert all(e["source"] in ids and e["target"] in ids for e in graph["links"])
        assert len(to_network(graph).edges) == len(graph["links"])
        for path, start, end in step["sources"]:
            lines = (REPO_ROOT / path).read_text().splitlines()
            assert 1 <= start <= end
            assert start <= len(lines)
    full = graph_for(steps[-1], d, True)
    assert len(full["links"]) == 31 + 58 + 6 + 8
    ip_edges = [e for e in full["links"] if e.get("origin") == "ip_collocation"]
    assert len(ip_edges) == len(EDGES)
    assert all("relationship_source: ip collocation" in e["details"] for e in ip_edges)
    assert {n["id"] for n in full["nodes"] if n["kind"] != "uid"} == set(ALIASES.values())
    assert len([e for e in full["links"] if e["source"] == "v6" and e["kind"] == "membership"]) == 12
    html = to_html(full)
    assert "white-space: pre-line" in html
    assert f"height: {HEIGHT}px !important" in html
    assert "new vis.Network" in html


def test_app_all_steps_incremental_only():
    app = AppTest.from_file(str(Path(__file__).parent / "streamlit_app.py"), default_timeout=20).run()
    assert not app.exception
    assert not app.tabs
    assert app.sidebar.radio[0].label == "Pipeline step"
    assert len(app.get("popover")) == 1
    assert not any(child.type in ("caption", "info") for child in app.main.children.values())
    for i in range(19):
        app.radio(key="alignment_step").set_value(i).run()
        assert not app.exception
        assert app.sidebar.subheader[0].value.startswith(f"{i}.")
        assert app.sidebar.markdown[0].value == build_steps(build_example())[i]["note"]
        assert not any(header.value.startswith(f"{i}.") for header in app.main.subheader)
    assert not app.segmented_control
    assert [toggle.label for toggle in app.toggle] == ["Relationship labels"]
    app.toggle(key="alignment_labels").set_value(False).run()
    assert not app.exception

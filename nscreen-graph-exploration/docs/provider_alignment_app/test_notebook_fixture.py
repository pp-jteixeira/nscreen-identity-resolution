"""Read notebook literals only; never execute its database-writing cells."""

import ast
import json
import re
from collections import Counter

from alignment_example import EDGES, EXPERIAN, GEO, LIVERAMP, REPO_ROOT, THROTLE, build_example, build_steps, graph_for


def notebook_code():
    notebook = json.loads((REPO_ROOT / "nscreen-graph/provider-alignment-toy.ipynb").read_text())
    return ["".join(cell["source"]) for cell in notebook["cells"] if cell["cell_type"] == "code"]


def test_sources_match_expanded_notebook():
    code = next(cell for cell in notebook_code() if '"nscreen_toy_th_source", recreate=True' in cell)
    blocks = re.findall(r"select \* from \(values(.*?)\) as t\(uid, matchid\)", code, re.DOTALL)
    assert len(blocks) == 3
    for block, rows in zip(blocks, [THROTLE, LIVERAMP, EXPERIAN], strict=True):
        expected = Counter((u, int(m)) for u, m in re.findall(r"\('(v\d+)',\s*(\d+)\)", block))
        assert expected == Counter((r["uid"], r["matchid"]) for r in rows)
    pairs = re.findall(r"\('(v\d+)','(v\d+)',(\d+),(false|true),(false|true)\)", code)
    assert Counter((a, b, float(w), s == "true", d == "true") for a, b, w, s, d in pairs) == Counter(
        (e["uid1"], e["uid2"], e["weight"], e["samedevice"], e["differentusers"]) for e in EDGES
    )
    assert {r["uid"]: r["geo"] for r in GEO} == {
        "v1": "G1",
        "v17": "G1",
        "v18": "G1",
        "v6": "G1",
        "v20": "G1",
        "v19": "G1",
        "v21": "G1",
        "v9": "G1",
        "v24": "G1",
        "v25": "G1",
        "v26": "G1",
        "v33": "G3",
        "v34": "G4",
    }


def test_diagnostics_match_notebook_and_geo_rejection_is_visible():
    cell = next(code for code in notebook_code() if "expected_diag =" in code)
    assignment = next(
        node
        for node in ast.parse(cell).body
        if isinstance(node, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == "expected_diag" for t in node.targets)
    )
    expected = Counter(ast.literal_eval(assignment.value))
    data = build_example()
    assert (
        Counter(
            (r["uid"], r["distinct_stage"], r["distinct_matchid"], r["distinct_reason"]) for r in data["diagnostic"]
        )
        == expected
    )
    graph = graph_for(build_steps(data)[14], data)
    rejected = next(e for e in graph["links"] if e["source"] == "v33")
    assert rejected["target"] == "v34"
    assert rejected["kind"] == "rejected"
    assert "geo1: G3" in rejected["details"]
    assert "geo2: G4" in rejected["details"]

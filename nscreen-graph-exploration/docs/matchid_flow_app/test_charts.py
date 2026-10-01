import itertools

import pandas as pd
import pytest
from charts import reason_attribution_chart
from pipeline_chart import identity_pipeline_chart
from test_support import build_test_snapshot


def diagram():
    metrics = build_test_snapshot("2026-09-17")["metrics"]
    return identity_pipeline_chart(
        metrics["sources"], metrics["flow"], metrics["stage_reason"]
    )


def test_pipeline_has_one_connected_component_and_no_duplicate_total_nodes():
    meta = diagram().layout.meta
    nodes = {n["key"]: n for n in meta["nodes"]}
    adjacency = {key: set() for key in nodes}
    for link in meta["links"]:
        adjacency[link["source"]].add(link["target"])
        adjacency[link["target"]].add(link["source"])
    reached, pending = set(), ["LiveRamp"]
    while pending:
        node = pending.pop()
        if node not in reached:
            reached.add(node)
            pending.extend(adjacency[node] - reached)
    assert reached == set(nodes)
    assert not any("total" in key or "representation:" in key for key in nodes)
    assert {"LR", "TH", "EX", "LRTH", "LREX", "THEX", "LRTHEX"} <= nodes.keys()
    assert {
        "initial",
        "ic1",
        "ic2",
        "lu",
        "final",
        "ipcollo",
        "remainder",
    } <= nodes.keys()


def test_measured_bands_share_scale_and_unknown_bands_use_display_minimum():
    figure = diagram()
    meta = figure.layout.meta
    scale = meta["matchid_scale"]
    for edge in meta["links"]:
        if edge["count"] is None:
            assert edge["width"] == 15
        else:
            assert edge["width"] == pytest.approx(
                max(15, scale * edge["count"]) + edge.get("inherited_padding_px", 0)
            )
    assert not any(t.mode == "lines" for t in figure.data)
    assert sum(bool(a.showarrow) for a in figure.layout.annotations) == 3
    assert figure.layout.font.size == 11
    assert figure.layout.font.shadow == "none"


def test_final_scales_from_distinct_total_and_graph_nodes_have_separate_units():
    meta = diagram().layout.meta
    nodes = {n["key"]: n for n in meta["nodes"]}
    final_bands = [
        e for e in meta["links"] if e["target"] == "final" and e["count"] is not None
    ]
    assert {e["source"] for e in final_bands} == {"initial", "ic1", "ic2", "lu"}
    stacked_bands = sorted(final_bands, key=lambda edge: edge["target_y"])
    assert sum(edge["count"] for edge in stacked_bands) == 261_500_000
    assert nodes["final"]["height"] == pytest.approx(
        sum(edge["width"] for edge in stacked_bands)
    )
    assert "union" not in nodes
    for a, b in itertools.pairwise(stacked_bands):
        assert a["target_y"] + a["width"] / 2 == pytest.approx(
            b["target_y"] - b["width"] / 2
        )
    assert nodes["ipcollo"]["count"] is None
    assert "Not measured" in nodes["ipcollo"]["label"]
    assert "same ID" not in str(nodes)
    assert nodes["ic1"]["count"] == 34_000_000


@pytest.mark.parametrize(
    "reason,vendors",
    [
        ("LRTH", {"LiveRamp", "Throtle"}),
        ("LREX", {"LiveRamp", "Experian"}),
        ("THEX", {"Throtle", "Experian"}),
        ("LRTHEX", {"LiveRamp", "Throtle", "Experian"}),
    ],
)
def test_shared_reason_bands_overlap_without_summing_destination(reason, vendors):
    meta = diagram().layout.meta
    node = next(n for n in meta["nodes"] if n["key"] == reason)
    incoming = [e for e in meta["links"] if e["target"] == reason]
    outgoing = next(e for e in meta["links"] if e["source"] == reason)
    assert {e["source"] for e in incoming} == vendors
    for edge in incoming:
        assert edge["count"] == node["count"]
        assert edge["width"] == pytest.approx(node["height"])
        assert edge["width"] == pytest.approx(outgoing["width"])
        assert edge["target_y"] == node["y"]
        assert edge["shared_attribution"]


def test_labels_have_nonoverlapping_vertical_slots_in_crowded_columns():
    meta = diagram().layout.meta
    for keys in (
        ["LR", "LRTH", "LREX", "LRTHEX", "TH", "THEX", "EX"],
        ["LiveRamp", "Throtle", "Experian"],
    ):
        nodes = {n["key"]: n for n in meta["nodes"]}
        for left, right in itertools.pairwise(keys):
            a, b = nodes[left], nodes[right]
            assert (
                a["y"] + max(42, a["height"]) / 2 + 18
                <= b["y"] - max(42, b["height"]) / 2 + 1e-6
            )


def test_initial_has_one_scaled_band_and_dashed_seed_dependencies():
    figure = diagram()
    meta = figure.layout.meta
    initial = next(n for n in meta["nodes"] if n["key"] == "initial")
    outgoing = [e for e in meta["links"] if e["source"] == "initial"]
    bands = [e for e in outgoing if not e["dependency"]]
    assert len(bands) == 1
    assert bands[0]["target"] == "final"
    assert bands[0]["count"] == initial["count"]
    assert {e["target"] for e in outgoing if e["dependency"]} == {"ic1", "ic2"}
    assert sum(s.line.dash == "dash" for s in figure.layout.shapes) == 3


def test_matchid_assignment_stages_use_measured_final_bands():
    figure = diagram()
    nodes = {node["key"]: node for node in figure.layout.meta["nodes"]}
    links = figure.layout.meta["links"]

    for source in ("ic1", "ic2"):
        edge = next(
            edge
            for edge in links
            if edge["source"] == source and edge["target"] == "final"
        )
        assert not edge["dependency"]
        assert edge["count"] == nodes[source]["count"]
        assert edge["width"] >= 15

    final_bands = sorted(
        (edge for edge in links if edge["target"] == "final"),
        key=lambda edge: edge["target_y"],
    )
    for a, b in itertools.pairwise(final_bands):
        assert a["target_y"] + a["width"] / 2 == pytest.approx(
            b["target_y"] - b["width"] / 2
        )


@pytest.mark.parametrize("count", [0, 1000, 5_000_000_000])
def test_clean_graph_node_uses_uid_scale_only_in_uid_mode(count):
    metrics = build_test_snapshot("2026-09-17")["metrics"]["uids"]
    graphs = pd.DataFrame([{"graph": "graph_clean", "unit": "uids", "count": count}])
    for unit in ("uids", "matchids"):
        fig = identity_pipeline_chart(
            metrics["sources"],
            metrics["flow"],
            metrics["stage_reason"],
            graph_size=graphs,
            unit=unit,
        )
        clean = next(n for n in fig.layout.meta["nodes"] if n["key"] == "ipcollo")
        outgoing = [e for e in fig.layout.meta["links"] if e["source"] == "ipcollo"]
        if unit == "uids":
            assert clean["count"] == count
            expected = (
                2 if count == 0 else max(15, count * fig.layout.meta["matchid_scale"])
            )
            assert clean["height"] == pytest.approx(
                max(
                    expected,
                    sum(e["width"] for e in outgoing if e["count"] is not None),
                )
            )
            assert clean["y"] + clean["height"] / 2 < fig.layout.yaxis.range[0]
        else:
            assert clean["count"] is None
            assert clean["height"] == 24
        if unit == "matchids":
            assert all(e["count"] is None and e["width"] == 15 for e in outgoing)
        else:
            assert {e["target"]: e["count"] for e in outgoing} == {
                "ic1": 33_000_000,
                "ic2": 8_000_000,
                "remainder": None,
            }


def test_uid_remainder_uses_measured_graph_not_subtraction():
    metrics = build_test_snapshot("2026-09-17")["metrics"]["uids"]
    graphs = pd.DataFrame(
        [
            {"graph": "graph_clean", "unit": "uids", "count": 1_000_000_000},
            {"graph": "graph_remainder", "unit": "uids", "count": 100_000_000},
        ]
    )
    fig = identity_pipeline_chart(
        metrics["sources"],
        metrics["flow"],
        metrics["stage_reason"],
        graph_size=graphs,
        unit="uids",
    )
    nodes = {n["key"]: n for n in fig.layout.meta["nodes"]}
    assert nodes["remainder"]["title"] == "Unassigned after IC2<br>(same geo)"
    assert not any(
        edge["source"] == "ic2" and edge["target"] == "remainder"
        for edge in fig.layout.meta["links"]
    )
    outgoing = [e for e in fig.layout.meta["links"] if e["source"] == "ipcollo"]
    assert {e["target"]: e["count"] for e in outgoing} == {
        "ic1": 33_000_000,
        "ic2": 8_000_000,
        "remainder": 100_000_000,
    }
    for edge in outgoing:
        assert edge["width"] == pytest.approx(nodes[edge["target"]]["height"])
    for a, b in itertools.pairwise(sorted(outgoing, key=lambda e: e["source_y"])):
        assert a["source_y"] + a["width"] / 2 == pytest.approx(
            b["source_y"] - b["width"] / 2
        )


def test_uid_chart_counts_uids_and_stacks_all_assignment_stages():
    metrics = build_test_snapshot("2026-09-17")["metrics"]["uids"]
    fig = identity_pipeline_chart(
        metrics["sources"], metrics["flow"], metrics["stage_reason"], unit="uids"
    )
    edges = fig.layout.meta["links"]
    incoming = [e for e in edges if e["target"] == "final"]
    assert {e["source"] for e in incoming} == {"initial", "ic1", "ic2", "lu"}
    assert sum(e["count"] for e in incoming) == 1_055_000_000
    assert not any(e["dependency"] for e in incoming)
    for a, b in itertools.pairwise(sorted(incoming, key=lambda e: e["target_y"])):
        assert a["target_y"] + a["width"] / 2 == pytest.approx(
            b["target_y"] - b["width"] / 2
        )
    assert all(e["count"] is None for e in edges if e["shared_attribution"])
    assert any("distinct uids" in str(trace.text) for trace in fig.data)


def test_uid_membership_slots_stack_sources_and_only_overlap_shared_atoms():
    metrics = build_test_snapshot("2026-09-17")["metrics"]["uids"]
    membership = metrics["membership"].copy()
    # Split LRTH into LR-only, TH-only and shared UID populations.
    membership = membership.loc[~membership.reason.eq("LRTH")]
    membership = pd.concat(
        [
            membership,
            pd.DataFrame(
                [
                    {"reason": "LRTH", "mask": "1", "count": 20_000_000},
                    {"reason": "LRTH", "mask": "2", "count": 30_000_000},
                    {"reason": "LRTH", "mask": "3", "count": 50_000_000},
                ]
            ),
        ],
        ignore_index=True,
    )
    sources = metrics["sources"].copy()
    for vendor, bit in {"LiveRamp": 1, "Throtle": 2, "Experian": 4}.items():
        sources.loc[sources.vendor.eq(vendor), "matchids"] = sum(
            int(r.count) for r in membership.itertuples() if int(r.mask) & bit
        )
    fig = identity_pipeline_chart(
        sources,
        metrics["flow"],
        metrics["stage_reason"],
        unit="uids",
        membership=membership,
    )
    nodes = {n["key"]: n for n in fig.layout.meta["nodes"]}
    edges = fig.layout.meta["links"]
    for vendor in sources.vendor:
        outgoing = sorted(
            (e for e in edges if e["source"] == vendor), key=lambda e: e["source_y"]
        )
        assert sum(e["count"] for e in outgoing) == nodes[vendor]["count"]
        assert sum(e["width"] for e in outgoing) == pytest.approx(
            nodes[vendor]["height"]
        )
        for a, b in itertools.pairwise(outgoing):
            assert a["source_y"] + a["width"] / 2 == pytest.approx(
                b["source_y"] - b["width"] / 2
            )
    incoming = [e for e in edges if e["target"] == "LRTH"]
    shared = [e for e in incoming if e["atom"] == 3]
    assert len(shared) == 2
    assert shared[0]["target_y"] == shared[1]["target_y"]
    assert shared[0]["width"] == shared[1]["width"]
    slots = {e["atom"]: e for e in incoming}
    for a, b in itertools.pairwise(sorted(slots.values(), key=lambda e: e["target_y"])):
        assert a["target_y"] + a["width"] / 2 == pytest.approx(
            b["target_y"] - b["width"] / 2
        )


def test_initial_band_carries_minimum_height_padding_to_final():
    metrics = build_test_snapshot("2026-09-17")["metrics"]
    reasons = metrics["stage_reason"].copy()
    reasons.loc[
        (reasons.stage == "initial") & (reasons.reason == "THEX"), "matchids"
    ] = 1
    flow = metrics["flow"].copy()
    initial_total = int(reasons.loc[reasons.stage == "initial", "matchids"].sum())
    flow.loc[flow.checkpoint == "Vendor alignment", "matchids"] = initial_total
    flow.loc[flow.checkpoint == "After LU / final", "matchids"] = (
        initial_total + 13_300_000
    )
    fig = identity_pipeline_chart(metrics["sources"], flow, reasons)
    nodes = {n["key"]: n for n in fig.layout.meta["nodes"]}
    edges = fig.layout.meta["links"]
    band = next(e for e in edges if e["source"] == "initial" and e["target"] == "final")
    assert band["inherited_padding_px"] > 0
    assert band["count"] == initial_total
    assert band["width"] == pytest.approx(nodes["initial"]["height"])
    assert band["width"] == pytest.approx(
        sum(e["width"] for e in edges if e["target"] == "initial")
    )
    final_bands = sorted(
        (
            edge
            for edge in edges
            if edge["target"] == "final"
            and edge["count"] is not None
        ),
        key=lambda e: e["target_y"],
    )
    assert sum(e["width"] for e in final_bands) == pytest.approx(
        nodes["final"]["height"]
    )
    assert final_bands[0]["target_y"] + final_bands[0]["width"] / 2 == pytest.approx(
        final_bands[1]["target_y"] - final_bands[1]["width"] / 2
    )


def test_multiple_reason_uids_are_counted_once_in_separate_branch():
    metrics = build_test_snapshot("2026-09-17")["metrics"]["uids"]
    membership = metrics["membership"].copy()
    membership.loc[membership.reason.eq("LR"), "reason"] = "multiple_reasons"
    fig = identity_pipeline_chart(
        metrics["sources"],
        metrics["flow"],
        metrics["stage_reason"],
        unit="uids",
        membership=membership,
    )
    nodes = {n["key"]: n for n in fig.layout.meta["nodes"]}
    assert nodes["multiple_reasons"]["count"] == 400_000_000
    assert nodes["LR"]["count"] == 0
    incoming = [e for e in fig.layout.meta["links"] if e["target"] == "initial"]
    assert sum(e["count"] for e in incoming) == nodes["initial"]["count"]


def test_dense_uid_layout_fits_nodes_labels_and_arrowheads():
    metrics = build_test_snapshot("2026-09-17")["metrics"]["uids"]
    membership = pd.DataFrame(
        [
            {"reason": reason, "mask": str(mask), "count": 1000}
            for reason in [
                "LR",
                "LRTH",
                "LREX",
                "LRTHEX",
                "TH",
                "THEX",
                "EX",
                "multiple_reasons",
            ]
            for mask in range(1, 8)
        ]
    )
    fig = identity_pipeline_chart(
        metrics["sources"],
        metrics["flow"],
        metrics["stage_reason"],
        unit="uids",
        membership=membership,
    )
    nodes = {n["key"]: n for n in fig.layout.meta["nodes"]}
    for node in nodes.values():
        assert node["y"] - max(42, node["height"]) / 2 >= 0
        assert node["y"] + max(42, node["height"]) / 2 < fig.layout.yaxis.range[0]
    reason_bottom = max(
        n["y"] + max(42, n["height"]) / 2
        for key, n in nodes.items()
        if key
        in {"LR", "LRTH", "LREX", "LRTHEX", "TH", "THEX", "EX", "multiple_reasons"}
    )
    assert (
        min(
            n["y"] - max(42, n["height"]) / 2
            for key, n in nodes.items()
            if key.startswith("excluded:")
        )
        > reason_bottom
    )
    for arrow in fig.layout.annotations:
        if arrow.showarrow:
            assert (
                (arrow.ax - arrow.x) ** 2 + (arrow.ay - arrow.y) ** 2
            ) ** 0.5 == pytest.approx(12)


@pytest.mark.parametrize("masks,expected", [([1, 3, 5], 1), ([1, 2, 3], 2)])
def test_adjacent_vendor_ribbons_merge_without_filling_membership_gaps(masks, expected):
    metrics = build_test_snapshot("2026-09-17")["metrics"]["uids"]
    membership = pd.DataFrame(
        [{"reason": "LR", "mask": str(mask), "count": 1_000_000} for mask in masks]
    )
    fig = identity_pipeline_chart(
        metrics["sources"],
        metrics["flow"],
        metrics["stage_reason"],
        unit="uids",
        membership=membership,
    )
    original = [
        e
        for e in fig.layout.meta["links"]
        if e["source"] == "LiveRamp" and e["target"] == "LR"
    ]
    rendered = [
        e
        for e in fig.layout.meta["rendered_ribbons"]
        if e["source"] == "LiveRamp" and e["target"] == "LR"
    ]
    assert len(rendered) == expected
    assert sum(e["count"] for e in rendered) == sum(e["count"] for e in original)
    assert sum(e["width"] for e in rendered) == pytest.approx(
        sum(e["width"] for e in original)
    )


def test_aggregate_view_has_one_band_per_vendor_reason_even_with_gaps():
    metrics = build_test_snapshot("2026-09-17")["metrics"]["uids"]
    membership = pd.DataFrame(
        [
            {"reason": "LR", "mask": str(mask), "count": 1_000_000}
            for mask in range(1, 8)
        ]
    )
    fig = identity_pipeline_chart(
        metrics["sources"],
        metrics["flow"],
        metrics["stage_reason"],
        unit="uids",
        membership=membership,
        aggregate_vendor_bands=True,
    )
    incoming = [e for e in fig.layout.meta["links"] if e["target"] == "LR"]
    assert len(incoming) == 3
    assert all(e["count"] == 4_000_000 for e in incoming)
    rendered = [e for e in fig.layout.meta["rendered_ribbons"] if e["target"] == "LR"]
    assert len(rendered) == 3
    assert any(
        "overlap positions are schematic" in str(trace.text) for trace in fig.data
    )


def test_eight_uid_reasons_have_positive_proportional_scale():
    metrics = build_test_snapshot("2026-09-17")["metrics"]["uids"]
    membership = metrics["membership"].copy()
    membership = pd.concat(
        [
            membership,
            pd.DataFrame(
                [{"reason": "multiple_reasons", "mask": "7", "count": 20_000_000}]
            ),
        ],
        ignore_index=True,
    )
    fig = identity_pipeline_chart(
        metrics["sources"],
        metrics["flow"],
        metrics["stage_reason"],
        unit="uids",
        membership=membership,
        aggregate_vendor_bands=True,
    )
    scale = fig.layout.meta["matchid_scale"]
    nodes = {n["key"]: n for n in fig.layout.meta["nodes"]}
    assert scale > 0
    assert nodes["LR"]["height"] > nodes["EX"]["height"] > 15
    assert nodes["LR"]["height"] / nodes["EX"]["height"] == pytest.approx(
        nodes["LR"]["count"] / nodes["EX"]["count"]
    )
    for edge in fig.layout.meta["links"]:
        if edge["target"] == "initial":
            assert edge["width"] == pytest.approx(max(15, scale * edge["count"]))
            assert edge["width"] == pytest.approx(nodes[edge["source"]]["height"])


def test_dependency_arrows_are_straight_and_centered():
    fig = diagram()
    nodes = {n["key"]: n for n in fig.layout.meta["nodes"]}
    paths = [s.path for s in fig.layout.shapes if s.line.dash == "dash"]
    for edge in fig.layout.meta["links"]:
        if edge["dependency"]:
            a, b = nodes[edge["source"]], nodes[edge["target"]]
            assert f"M {a['x'] + 10},{a['y']} L {b['x']},{b['y']}" in paths
    assert all(" C " not in path for path in paths)


def test_reason_chart_includes_intermediate_and_final_counts():
    metrics = build_test_snapshot("2026-09-17")["metrics"]

    chart = reason_attribution_chart(
        metrics["stage_reason"], metrics["final_reason"]
    ).to_dict()
    values = next(iter(chart["datasets"].values()))

    assert any(
        row["stage_label"] == "IC stage 1"
        and row["reason"] == "IC"
        and row["matchids"] == 34_000_000
        for row in values
    )
    assert any(
        row["stage_label"] == "Final"
        and row["reason"] == "LU"
        and row["matchids"] == 13_300_000
        for row in values
    )

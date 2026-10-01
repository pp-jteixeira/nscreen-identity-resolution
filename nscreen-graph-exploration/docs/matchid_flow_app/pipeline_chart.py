"""Connected pipeline with measured ribbons and schematic dependency bands.

Dependency bands have no measured quantity and must not distort the matchid
scale. This renderer uses Plotly paths and scatter traces with calculated
vertical packing, keeping semantic stage columns and one matchid scale.
"""

from collections import defaultdict
from math import hypot

import plotly.graph_objects as go

MIN_BAND = 15
FONT = {"family": "Arial, sans-serif", "size": 11, "color": "#0F172A", "shadow": "none"}
REASONS = ["LR", "LRTH", "LREX", "LRTHEX", "TH", "THEX", "EX"]
COLORS = dict(
    zip(
        REASONS,
        ["#2563EB", "#14B8A6", "#6366F1", "#0F766E", "#F59E0B", "#D97706", "#8B5CF6"],
        strict=True,
    )
)


def compact(count):
    if count is None:
        return "Not measured"
    if count >= 1_000_000_000:
        return f"{count / 1_000_000_000:.2f}B"
    if count >= 1_000_000:
        return f"{count / 1_000_000:.1f}M"
    if count >= 1000:
        return f"{count / 1000:.1f}K"
    return str(count)


def identity_pipeline_chart(
    sources,
    flow,
    stage_reason,
    vendor_representation=None,
    graph_size=None,
    *,
    unit="matchids",
    membership=None,
    aggregate_vendor_bands=False,
):
    uid_mode = unit == "uids"
    atoms = (
        []
        if membership is None
        else [
            {"reason": str(r.reason), "mask": int(r.mask), "count": int(r.count)}
            for r in membership.itertuples()
            if int(r.count) > 0
        ]
    )
    reasons = REASONS + (
        ["multiple_reasons"]
        if any(a["reason"] == "multiple_reasons" for a in atoms)
        else []
    )
    colors = {**COLORS, "multiple_reasons": "#DB2777"}
    source_counts = {str(r.vendor): int(r.matchids) for r in sources.itertuples()}
    flow_counts = {str(r.checkpoint): int(r.matchids) for r in flow.itertuples()}
    counts = {
        (str(r.stage), str(r.reason)): int(r.matchids)
        for r in stage_reason.itertuples()
    }
    if uid_mode and atoms:
        for reason in reasons:
            counts["initial", reason] = sum(
                a["count"] for a in atoms if a["reason"] == reason
            )
    representation = (
        {}
        if vendor_representation is None
        else {
            (str(r.vendor), str(r.outcome)): int(r.matchids)
            for r in vendor_representation.itertuples()
        }
    )
    graphs = (
        {}
        if graph_size is None
        else {
            (str(r.graph), str(r.unit)): int(r.count) for r in graph_size.itertuples()
        }
    )
    vendors = {"LiveRamp": "LR", "Throtle": "TH", "Experian": "EX"}
    nodes, links = {}, []

    def node(key, title, count, color, x, graph=None):
        if graph:
            details = (
                "<br>".join(
                    f"{graphs[graph, unit]:,} {unit}"
                    for unit in ("uids", "relationships")
                    if (graph, unit) in graphs
                )
                or "Not measured"
            )
            label = (
                title
                + "<br>"
                + "<br>".join(
                    f"{compact(graphs[graph, unit])} {unit}"
                    for unit in ("uids", "relationships")
                    if (graph, unit) in graphs
                )
            )
            if details == "Not measured":
                label += "<br>Not measured"
        else:
            label = title + (
                f"<br><b>{compact(count)}</b>" if count is not None else ""
            )
            details = "Process step" if count is None else f"{count:,} distinct {unit}"
        nodes[key] = {
            "key": key,
            "title": title,
            "count": count,
            "color": color,
            "x": x,
            "label": label,
            "details": details,
        }

    def link(
        source,
        target,
        count=None,
        route=None,
        shared_attribution=False,
    ):
        if count == 0:
            return
        links.append(
            {
                "source": source,
                "target": target,
                "count": count,
                "route": route,
                "shared_attribution": shared_attribution,
            }
        )

    for vendor, code in vendors.items():
        node(vendor, vendor, source_counts.get(vendor), COLORS[code], 25)
        known = any(v == vendor for v, _ in representation)
        value = representation.get((vendor, "unrepresented"), 0) if known else None
        if uid_mode and atoms:
            known = True
            bit = {"LiveRamp": 1, "Throtle": 2, "Experian": 4}[vendor]
            value = sum(
                a["count"]
                for a in atoms
                if a["reason"] == "unrepresented" and a["mask"] & bit
            )
        node(f"excluded:{vendor}", f"{code} unrepresented", value, "#DC2626", 245)
        if not known:
            nodes[f"excluded:{vendor}"]["label"] += "<br>Not measured"
        link(vendor, f"excluded:{vendor}", value)
    for reason in reasons:
        title = "Multiple initial reasons" if reason == "multiple_reasons" else reason
        node(reason, title, counts.get(("initial", reason), 0), colors[reason], 245)
        for vendor, code in vendors.items():
            if uid_mode and atoms:
                bit = {"LiveRamp": 1, "Throtle": 2, "Experian": 4}[vendor]
                if aggregate_vendor_bands:
                    value = sum(
                        a["count"]
                        for a in atoms
                        if a["reason"] == reason and a["mask"] & bit
                    )
                    link(vendor, reason, value, shared_attribution=True)
                    continue
                for atom in atoms:
                    if atom["reason"] == reason and atom["mask"] & bit:
                        link(vendor, reason, atom["count"], shared_attribution=True)
                        links[-1]["atom"] = atom["mask"]
                continue
            if code in reason:
                link(
                    vendor,
                    reason,
                    None if uid_mode else counts.get(("initial", reason), 0),
                    shared_attribution=True,
                )
        link(reason, "initial", counts.get(("initial", reason), 0))

    node(
        "initial",
        "Initial assignments",
        flow_counts.get("Vendor alignment"),
        "#14B8A6",
        465,
    )
    node("ic1", "IC stage 1 · IC", counts.get(("stage1", "IC")), "#3B82F6", 675)
    node("ic2", "IC stage 2 · IC", counts.get(("stage2", "IC")), "#2563EB", 875)
    node("lu", "Louvain · LU", counts.get(("louvain", "LU")), "#64748B", 1075)
    node("final", "Final result", flow_counts.get("After LU / final"), "#1D4ED8", 1495)
    node(
        "ipcollo",
        "Clean IP-collocation",
        graphs.get(("graph_clean", "uids")) if uid_mode else None,
        "#64748B",
        465,
        graph="graph_clean",
    )
    node(
        "remainder",
        "Unassigned after IC2<br>(same geo)",
        graphs.get(("graph_remainder", "uids")) if uid_mode else None,
        "#94A3B8",
        875,
        graph="graph_remainder",
    )
    for a, b in [
        ("initial", "ic1"),
        ("ic1", "ic2"),
        ("ipcollo", "ic1"),
        ("ipcollo", "ic2"),
        ("ipcollo", "remainder"),
        ("remainder", "lu"),
    ]:
        link(a, b)
    link("initial", "ic2", route=65)
    link("initial", "final", flow_counts.get("Vendor alignment"))
    link(
        "ic1",
        "final",
        counts.get(("stage1", "IC")),
        route=95,
    )
    link(
        "ic2",
        "final",
        counts.get(("stage2", "IC")),
        route=130,
    )
    link("lu", "final", counts.get(("louvain", "LU")))
    if uid_mode:
        for edge in links:
            if edge["source"] == "ipcollo":
                edge["count"] = nodes[edge["target"]]["count"]
            if edge["target"] == "final" and edge["source"] in {"ic1", "ic2"}:
                edge["route"] = None
    for edge in links:
        edge["dependency"] = (edge["source"], edge["target"]) in {
            ("initial", "ic1"),
            ("initial", "ic2"),
            ("ic1", "ic2"),
        }
    links = [edge for edge in links if edge["count"] != 0]

    # Fit a common scale to the populated source and reason columns. Label
    # slots are at least 42px, independently of a 15px minimum measured band.
    bank_counts = [
        [source_counts.get(v, 0) for v in vendors],
        [counts.get(("initial", r), 0) for r in reasons],
    ]
    all_counts = [n["count"] for n in nodes.values() if n["count"] is not None]
    # Eight reason labels already require 462px without any value-scaled
    # height. A fixed 460px budget has no feasible solution and yields zero.
    # Reserve proportional space beyond the minimum labels and gaps.
    minimum_slots = max(42 * len(bank) + 18 * (len(bank) - 1) for bank in bank_counts)
    height_budget = max(460, minimum_slots + 200)
    low, high = 0.0, height_budget / max([*all_counts, 1])
    for _ in range(80):
        scale = (low + high) / 2
        needed = max(
            sum(max(42, scale * c) for c in bank) + 18 * (len(bank) - 1)
            for bank in bank_counts
        )
        if needed <= height_budget:
            low = scale
        else:
            high = scale
    scale = low

    def thickness(value):
        if value is None:
            return 24.0
        if value == 0:
            return 2.0
        return max(MIN_BAND, scale * value)

    for n in nodes.values():
        n["height"] = thickness(n["count"])
    for edge in links:
        edge["width"] = (
            thickness(edge["count"]) if edge["count"] is not None else MIN_BAND
        )
    # Each exact membership atom owns a destination slot. Vendors sharing that
    # atom overlap there; different UID sets occupy different slots.
    atom_slots = {}
    for reason in reasons:
        members = sorted(
            (a for a in atoms if a["reason"] == reason and not aggregate_vendor_bands),
            key=lambda a: a["mask"],
        )
        total = sum(thickness(a["count"]) for a in members)
        cursor = -total / 2
        for atom in members:
            width = thickness(atom["count"])
            atom_slots[reason, atom["mask"]] = cursor + width / 2
            cursor += width
        if members:
            nodes[reason]["height"] = max(nodes[reason]["height"], total)
            for edge in links:
                if edge["source"] == reason and edge["target"] == "initial":
                    edge["width"] = total
    # Carry the minimum-height padding of incoming reason slots through the
    # single Initial ribbon, rather than narrowing immediately after the node.
    initial_in = sum(
        e["width"] for e in links if e["target"] == "initial" and e["count"] is not None
    )
    for edge in links:
        if (
            edge["source"] == "initial"
            and edge["target"] == "final"
            and edge["count"] is not None
        ):
            width = max(edge["width"], initial_in)
            edge["inherited_padding_px"] = width - edge["width"]
            edge["width"] = width
    # Vendor attribution ribbons describe the same output identities. They
    # share a destination slot instead of adding to that node's height.
    measured_in, measured_out = defaultdict(float), defaultdict(float)
    shared_in = defaultdict(float)
    for edge in links:
        if edge["count"] is not None:
            if edge["shared_attribution"]:
                shared_in[edge["target"]] = max(
                    shared_in[edge["target"]], edge["width"]
                )
            else:
                measured_in[edge["target"]] += edge["width"]
            measured_out[edge["source"]] += edge["width"]
    for key, n in nodes.items():
        n["height"] = max(
            n["height"], measured_in[key], shared_in[key], measured_out[key]
        )

    def pack(keys, center):
        slots = [max(42, nodes[key]["height"]) for key in keys]
        cursor = center - (sum(slots) + 18 * (len(slots) - 1)) / 2
        for key, slot in zip(keys, slots, strict=True):
            nodes[key]["y"] = cursor + slot / 2
            cursor += slot + 18

    pack(list(vendors), 385)
    pack(reasons, 385)
    excluded_keys = [f"excluded:{v}" for v in vendors]
    reason_bottom = max(
        nodes[key]["y"] + max(42, nodes[key]["height"]) / 2 for key in reasons
    )
    excluded_span = sum(max(42, nodes[key]["height"]) for key in excluded_keys) + 18 * (
        len(excluded_keys) - 1
    )
    pack(excluded_keys, max(755, reason_bottom + 36 + excluded_span / 2))
    for key, y in {
        "initial": 385,
        "ic1": 355,
        "ic2": 405,
        "lu": 585,
        "final": 385,
        "ipcollo": 735,
        "remainder": 735,
    }.items():
        nodes[key]["y"] = y

    canvas_bottom = 860
    if uid_mode and nodes["ipcollo"]["count"] is not None:
        clean = nodes["ipcollo"]
        initial = nodes["initial"]
        clean["y"] = max(
            clean["y"], initial["y"] + initial["height"] / 2 + 60 + clean["height"] / 2
        )
    if uid_mode:
        remainder = nodes["remainder"]
        ic2 = nodes["ic2"]
        remainder["y"] = max(
            remainder["y"], ic2["y"] + ic2["height"] / 2 + 60 + remainder["height"] / 2
        )
        canvas_bottom = max(
            canvas_bottom, *(n["y"] + n["height"] / 2 + 40 for n in nodes.values())
        )

    # Minimum-width atoms can make columns taller than the initial scale budget.
    # Translate the entire layout and its explicit routes, then fit both bounds.
    top = min(n["y"] - max(42, n["height"]) / 2 for n in nodes.values())
    shift = max(0, 80 - top)
    for n in nodes.values():
        n["y"] += shift
    for edge in links:
        if edge["route"] is not None:
            edge["route"] += shift
    canvas_bottom = max(
        860, *(n["y"] + max(42, n["height"]) / 2 + 40 for n in nodes.values())
    )

    figure = go.Figure()
    merged_ribbons = []
    last_ribbon = {}
    used_in, used_out = defaultdict(float), defaultdict(float)
    for edge in links:
        a, b = nodes[edge["source"]], nodes[edge["target"]]
        x0, x1 = a["x"] + 10, b["x"]
        y0, y1 = edge.get("source_y", a["y"]), b["y"]
        dx = (x1 - x0) * 0.45
        if edge["dependency"]:
            # Dashed arrows describe reuse of seed identities, not new IDs.
            y0, y1 = a["y"], b["y"]
            tangent_length = max(hypot(x0 - x1, y0 - y1), 1)
            figure.add_shape(
                type="path",
                path=f"M {x0},{y0} L {x1},{y1}",
                line={"color": a["color"], "width": 1.5, "dash": "dash"},
                layer="above",
            )
            figure.add_annotation(
                x=x1,
                y=y1,
                ax=x1 + (x0 - x1) * 12 / tangent_length,
                ay=y1 + (y0 - y1) * 12 / tangent_length,
                xref="x",
                yref="y",
                axref="x",
                ayref="y",
                text="",
                showarrow=True,
                arrowhead=2,
                arrowwidth=1.5,
                arrowcolor=a["color"],
            )
            continue
        if edge["count"] is not None:
            width = edge["width"]
            y0 = a["y"] - measured_out[a["key"]] / 2 + used_out[a["key"]] + width / 2
            if edge["shared_attribution"]:
                y1 = b["y"] + atom_slots.get((b["key"], edge.get("atom")), 0)
            else:
                y1 = b["y"] - measured_in[b["key"]] / 2 + used_in[b["key"]] + width / 2
                used_in[b["key"]] += width
            used_out[a["key"]] += width
            edge["source_y"] = y0
            edge["target_y"] = y1
            # Coalesce only intervals that touch at BOTH ends. Filling a gap
            # at the reason node would falsely include another vendor's UIDs.
            key = (edge["source"], edge["target"])
            previous = last_ribbon.get(key) if "atom" in edge else None
            merge = previous is not None and all(
                abs(current - (previous[axis] + previous["width"] / 2)) < 1e-6
                for current, axis in (
                    (y0 - width / 2, "source_y"),
                    (y1 - width / 2, "target_y"),
                )
            )
            if merge:
                old_width = previous["width"]
                width += old_width
                y0 = previous["source_y"] - old_width / 2 + width / 2
                y1 = previous["target_y"] - old_width / 2 + width / 2
                previous.update(
                    width=width,
                    source_y=y0,
                    target_y=y1,
                    count=previous["count"] + edge["count"],
                )
                ribbon = previous
            else:
                ribbon = {
                    "source": edge["source"],
                    "target": edge["target"],
                    "source_y": y0,
                    "target_y": y1,
                    "width": width,
                    "count": edge["count"],
                    "shape_index": len(figure.layout.shapes),
                    "trace_index": len(figure.data),
                }
                merged_ribbons.append(ribbon)
                if "atom" in edge:
                    last_ribbon[key] = ribbon
            half = width / 2
            shape = {
                "type": "path",
                "path": (
                    f"M {x0},{y0 - half} C {x0 + dx},{y0 - half} {x1 - dx},{y1 - half} {x1},{y1 - half} "
                    f"L {x1},{y1 + half} C {x1 - dx},{y1 + half} {x0 + dx},{y0 + half} {x0},{y0 + half} Z"
                ),
                "fillcolor": a["color"],
                "opacity": 0.25,
                "line_width": 0,
                "layer": "below",
            }
            if merge:
                figure.layout.shapes[ribbon["shape_index"]].update(shape)
                figure.data[ribbon["trace_index"]].update(
                    x=[(x0 + x1) / 2],
                    y=[(y0 + y1) / 2],
                    text=[
                        f"{a['title']} → {b['title']}<br>{ribbon['count']:,} distinct {unit}<br>Shared initial-reason identities; do not sum vendor bands"
                    ],
                )
                continue
            figure.add_shape(shape)
            figure.add_trace(
                go.Scatter(
                    x=[(x0 + x1) / 2],
                    y=[(y0 + y1) / 2],
                    mode="markers",
                    marker={"size": 12, "opacity": 0},
                    showlegend=False,
                    text=[
                        f"{a['title']} → {b['title']}<br>{edge['count']:,} distinct {unit}"
                        + (
                            "<br>Shared initial-reason identities; do not sum vendor bands"
                            + (
                                "<br>Aggregate membership; overlap positions are schematic"
                                if aggregate_vendor_bands
                                else ""
                            )
                            if edge["shared_attribution"]
                            else ""
                        )
                    ],
                    hoverinfo="text",
                )
            )
        else:
            # Unmeasured dependencies keep the requested ribbon appearance,
            # but carry no invented count and do not influence measured scale.
            half = MIN_BAND / 2
            control0 = y0 if edge["route"] is None else edge["route"]
            control1 = y1 if edge["route"] is None else edge["route"]
            figure.add_shape(
                type="path",
                path=(
                    f"M {x0},{y0 - half} C {x0 + dx},{control0 - half} {x1 - dx},{control1 - half} {x1},{y1 - half} "
                    f"L {x1},{y1 + half} C {x1 - dx},{control1 + half} {x0 + dx},{control0 + half} {x0},{y0 + half} Z"
                ),
                fillcolor=a["color"],
                opacity=0.18,
                line_width=0,
                layer="below",
            )
            figure.add_trace(
                go.Scatter(
                    x=[(x0 + x1) / 2],
                    y=[(y0 + 3 * control0 + 3 * control1 + y1) / 8],
                    mode="markers",
                    marker={"size": 15, "opacity": 0},
                    showlegend=False,
                    text=[
                        f"{a['title']} → {b['title']}<br>Transfer count not measured; schematic 15px band"
                    ],
                    hoverinfo="text",
                )
            )

    for key, n in nodes.items():
        figure.add_shape(
            type="rect",
            x0=n["x"],
            x1=n["x"] + 10,
            y0=n["y"] - n["height"] / 2,
            y1=n["y"] + n["height"] / 2,
            fillcolor=n["color"],
            line_width=0,
        )
        figure.add_annotation(
            x=n["x"] + 16,
            y=n["y"],
            text=n["label"],
            showarrow=False,
            xanchor="left",
            align="left",
            font=FONT,
            bgcolor="rgba(255,255,255,0.85)",
            borderpad=2,
        )
        figure.add_trace(
            go.Scatter(
                x=[n["x"] + 5],
                y=[n["y"]],
                mode="markers",
                marker={"size": 15, "opacity": 0},
                showlegend=False,
                text=[n["title"] + "<br>" + n["details"]],
                hoverinfo="text",
            )
        )

    figure.update_layout(
        height=canvas_bottom + 40,
        margin={"l": 10, "r": 10, "t": 20, "b": 20},
        xaxis={"range": [0, 1670], "visible": False, "fixedrange": True},
        yaxis={"range": [canvas_bottom, 0], "visible": False, "fixedrange": True},
        font=FONT,
        paper_bgcolor="white",
        plot_bgcolor="white",
        showlegend=False,
        meta={
            "nodes": list(nodes.values()),
            "links": links,
            "matchid_scale": scale,
            "minimum_band_px": MIN_BAND,
            "unit": unit,
            "aggregate_vendor_bands": aggregate_vendor_bands,
            "rendered_ribbons": merged_ribbons,
        },
    )
    return figure

"""Independent PyVis renderer; no imports or mutations of the Screen7 app."""

import json
from pathlib import Path

from pyvis.network import Network

HEIGHT = 900
STYLES = {
    "uid": ("ellipse", "#dbeafe", "#2563eb"),
    "throtle": ("box", "#fef3c7", "#b45309"),
    "liveramp": ("diamond", "#dcfce7", "#15803d"),
    "experian": ("triangle", "#f3e8ff", "#9333ea"),
    "community": ("hexagon", "#cffafe", "#0891b2"),
}
COLORS = {
    "membership": "#0284c7",
    "evidence": "#64748b",
    "ip_collocation": "#0f766e",
    "accepted": "#15803d",
    "rejected": "#dc2626",
    "candidate": "#d97706",
}


def layout_positions(universe_json):
    """Load offline force-layout coordinates; never optimize during navigation."""
    universe = json.loads(universe_json)
    positions = json.loads(Path(__file__).with_name("fixed_layout.json").read_text())["positions"]
    if set(positions) != {n["id"] for n in universe["nodes"]}:
        raise ValueError("Regenerate fixed_layout.json for the changed alignment dataset")
    return positions


def with_stable_positions(graph, universe):
    positions = layout_positions(json.dumps(universe, sort_keys=True))
    bounds = {axis: 2 * max(abs(p[axis]) for p in positions.values()) + 180 for axis in ("x", "y")}
    return dict(
        graph, stable_layout=True, layout_bounds=bounds, nodes=[dict(n, **positions[n["id"]]) for n in graph["nodes"]]
    )


def to_network(graph, physics=True, labels=True):
    stable_layout = graph.get("stable_layout", False)
    focus_final = graph.get("focus_final", False)
    physics = physics and not stable_layout
    network = Network(height=f"{HEIGHT}px", width="100%", directed=True, cdn_resources="in_line")
    for node in graph["nodes"]:
        shape, background, border = STYLES[node["kind"]]
        current = node.get("current", True)
        future = node.get("future", False)
        if not current:
            background, border = (
                ("#fafafa", "#dfe3e8")
                if future
                else ("#fafafa", "#e5e7eb")
                if focus_final
                else ("#f1f3f5", "#9ca3af")
            )
        font_color = (
            "#172033"
            if current
            else "#bdc4ce"
            if future
            else "#d1d5db"
            if focus_final
            else "#6b7280"
        )
        network.add_node(
            node["id"],
            label=node["id"],
            title=node["details"],
            shape=shape,
            color={"background": background, "border": border},
            borderWidth=1 if focus_final and not current else 2,
            font={"size": 20, "color": font_color},
            margin=12,
            **({"x": node["x"], "y": node["y"], "physics": False} if stable_layout else {}),
        )
    # Paint faded context first so it cannot cover current-step relationships.
    for i, edge in sorted(
        enumerate(graph["links"]),
        key=lambda item: (item[1].get("current", True), not item[1].get("future", False)),
    ):
        current = edge.get("current", True)
        future = edge.get("future", False)
        ip_collocation = edge.get("origin") == "ip_collocation"
        muted_ip = focus_final and current and ip_collocation
        if current and not muted_ip:
            color = (
                COLORS["ip_collocation"]
                if ip_collocation and edge["kind"] != "rejected"
                else COLORS[edge["kind"]]
            )
            width = 4 if edge["kind"] == "accepted" else 3.5 if ip_collocation else 2.5
        elif muted_ip:
            color = "#cbd5e1"
            width = 1.2
        else:
            color = "#e2e5e9" if future else "#e5e7eb" if focus_final else "#a8afb9"
            width = 1 if future else 0.8 if focus_final else 1.5
        dashes = (
            [12, 6]
            if ip_collocation
            else [4, 4]
            if edge["kind"] == "rejected"
            else False
        )
        network.add_edge(
            edge["source"],
            edge["target"],
            id=edge.get("id", f"relationship-{i}"),
            label=edge["label"] if labels and current else "",
            title=edge["details"],
            arrows={"to": {"enabled": edge["directed"]}},
            color={"color": color, "inherit": False},
            dashes=dashes,
            width=width,
            **({"font": {"color": "#cbd5e1"}} if muted_ip else {}),
            **(
                {"smooth": {"type": "curvedCW", "roundness": 0.08 + (int(edge["id"][:6], 16) % 13) * 0.025}}
                if stable_layout and "id" in edge
                else {}
            ),
        )
    network.set_options(
        json.dumps(
            {
                "layout": {"randomSeed": 19},
                "physics": {
                    "enabled": physics,
                    "solver": "barnesHut",
                    "barnesHut": {"gravitationalConstant": -9000, "springLength": 230, "avoidOverlap": 0.7},
                    "stabilization": {"iterations": 250},
                },
                "interaction": {
                    "hover": True,
                    "navigationButtons": True,
                    "tooltipDelay": 100,
                    "keyboard": {"enabled": True, "bindToWindow": False},
                },
                "edges": {
                    "smooth": {"enabled": True, "type": "curvedCW" if stable_layout else "dynamic", "roundness": 0.12},
                    "font": {"size": 11, "color": "#334155", "align": "horizontal"},
                },
            }
        )
    )
    return network


def to_html(graph, physics=True, labels=True):
    network = to_network(graph, physics, labels)
    style = f"""<style>
html, body {{ margin: 0; padding: 0; height: {HEIGHT}px; overflow: hidden; }}
.card {{ border: 0; }}
#mynetwork {{ width: 100% !important; height: {HEIGHT}px !important; padding: 0 !important; box-sizing: border-box; border: 1px solid #d1d5db !important; }}
.vis-tooltip {{ white-space: pre-line; max-width: 640px; overflow-wrap: anywhere; }}
</style>"""
    html = network.generate_html().replace("</head>", style + "</head>", 1)
    if graph.get("stable_layout"):
        # Keep the camera identical rather than refitting a different subset.
        bounds = graph["layout_bounds"]
        camera_script = """<script>
const viewport = document.getElementById('mynetwork');
network.moveTo({position: {x: 0, y: 0}, scale: Math.min(viewport.clientWidth / WIDTH, viewport.clientHeight / HEIGHT)});
</script></body>""".replace("WIDTH", str(bounds["x"])).replace("HEIGHT", str(bounds["y"]))
        return html.replace(
            "</body>",
            camera_script,
            1,
        )
    return html.replace(
        "</body>",
        "<script>network.once('stabilizationIterationsDone', function () {network.fit();});</script></body>",
        1,
    )

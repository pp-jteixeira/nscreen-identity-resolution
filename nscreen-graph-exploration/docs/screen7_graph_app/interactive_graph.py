"""PyVis rendering only: no changes to the Java-verified graph snapshots."""

import json

from example import node_color, node_label
from pyvis.network import Network

GRAPH_HEIGHT_PX = 900
TOOLTIP_STYLE = """<style>
.vis-tooltip { max-width: 720px; overflow-wrap: anywhere; white-space: pre-line; }
#mynetwork { padding: 0 !important; box-sizing: border-box; }
</style>"""
NODE_STYLES = {
    "uid": {"shape": "ellipse", "background": "#dbeafe"},
    "device": {"shape": "box", "background": "#fef3c7"},
    "match": {"shape": "diamond", "background": "#f3e8ff"},
    "household": {"shape": "hexagon", "background": "#dcfce7"},
    "ip": {"shape": "dot", "background": "#bfdbfe"},
    "event": {"shape": "star", "background": "#ffedd5"},
}


def node_type(node: dict) -> str:
    return {"deviceid": "device", "internal_matchid": "match"}.get(node["kind"], node["kind"])


def to_network(
    graph: dict, *, step: int, detailed_labels: bool = False, physics: bool = True, height_px: int = GRAPH_HEIGHT_PX
) -> Network:
    # Directed construction prevents PyVis from deduplicating parallel edges.
    # Explicit arrows below still keep evidence relationships undirected.
    network = Network(height=f"{height_px}px", width="100%", directed=True, cdn_resources="in_line")
    incremental = graph.get("graph", {}).get("incremental", False)
    network.incremental = incremental
    network.layout_bounds = graph.get("graph", {}).get("layout_bounds")
    hierarchical = graph.get("graph", {}).get("hierarchical", graph["directed"])
    for node in graph["nodes"]:
        kind = node_type(node)
        details = node.get("details", node_label(node, step=step))
        if "history_note" in node:
            details += "\n\n" + node["history_note"]
        label = details if detailed_labels else node["id"]
        if not detailed_labels:
            if node.get("household_changed"):
                label += f"\n{node['preliminary_householdid']} → {node['internal_householdid']}"
            if step == 7 and node.get("matchid") == 0:
                label += "\nreturned match: 0"
        color = node_color(node)
        style = NODE_STYLES[kind]
        current = node.get("current", True)
        background = style["background"] if current else "#f1f3f5"
        if not current:
            color = "#9ca3af"
        network.add_node(
            node["id"],
            label=label,
            title=details,
            shape=style["shape"],
            color={
                "border": color,
                "background": background,
                "highlight": {"border": color, "background": background},
            },
            borderWidth=4 if node.get("household_changed") else 2,
            font={"color": "#172033" if current else "#6b7280", "size": 20 if incremental else 16},
            margin=12,
            **({"level": {"uid": 0, "device": 1, "match": 2, "household": 3}[kind]} if hierarchical else {}),
            **({"x": node["x"], "y": node["y"], "physics": False} if incremental else {}),
        )
    for index, edge in sorted(enumerate(graph["links"]), key=lambda item: item[1].get("current", True)):
        directed = edge.get("directed", graph["directed"])
        if edge.get("kind") == "observation":
            label = edge.get("label", "observed")
            details = edge["details"]
            color, conflict, width = "#2b9348", False, 2
        elif directed:
            label = ""
            details = f"{edge['source']} → {edge['target']}: membership (not input evidence)"
            color, conflict, width = "#0284c7", False, 1.5
        else:
            same, conflict = edge["same_device"], edge["different_users"]
            label = f"{edge['weight']:.6g}\nrows {','.join(edge['source_rows'])}"
            if same:
                label += "\nsameDevice"
            if conflict:
                label += "\ndifferentUsers"
            details = f"{edge['source']} — {edge['target']}\n{label}\nsameDevice={same}\ndifferentUsers={conflict}"
            if "layer" in edge:
                details = edge["layer"] + "\n" + details
            color = "#c0392b" if conflict else "#15803d" if same else "#64748b"
            width = 3 if same or conflict else 1.5
        label = edge.get("label", label)
        details = edge.get("details", details)
        if "history_note" in edge:
            details += "\n\n" + edge["history_note"]
        if not edge.get("current", True):
            color, width, label = "#a8afb9", 1.5, ""
        elif incremental:
            width = max(width, 2.5)
        network.add_edge(
            edge["source"],
            edge["target"],
            id=edge["key"] if incremental else f"edge-{index}",
            label=label,
            title=details,
            arrows={"to": {"enabled": directed}},
            color={"color": color, "highlight": color, "hover": color, "inherit": False},
            dashes=conflict,
            width=width,
        )
    network.set_options(
        json.dumps(
            {
                "layout": {
                    "randomSeed": 7,
                    "hierarchical": {
                        "enabled": hierarchical,
                        "direction": "LR",
                        "sortMethod": "directed",
                        "levelSeparation": 260,
                        "nodeSpacing": 150,
                    },
                },
                "physics": {
                    "enabled": physics and not hierarchical and not incremental,
                    "solver": "barnesHut",
                    "barnesHut": {"gravitationalConstant": -9000, "springLength": 220, "avoidOverlap": 0.7},
                    "stabilization": {"iterations": 200},
                },
                "interaction": {
                    "hover": True,
                    "navigationButtons": True,
                    "dragNodes": True,
                    "dragView": True,
                    "zoomView": True,
                    "selectConnectedEdges": True,
                    "tooltipDelay": 100,
                    "keyboard": {"enabled": True, "bindToWindow": False},
                },
                "edges": {
                    "font": {"size": 12, "color": "#334155", "align": "horizontal"},
                    "smooth": {"enabled": True, "type": "continuous"},
                    "selfReference": {"size": 45, "renderBehindTheNode": False},
                },
            }
        )
    )
    return network


def to_html(network: Network) -> str:
    """Make trusted, fixed-example tooltips preserve newline detail text."""
    html = network.generate_html().replace("</head>", TOOLTIP_STYLE + "</head>", 1)
    if getattr(network, "incremental", False):
        html = html.replace(
            "</body>",
            """<script>
const viewport = document.getElementById('mynetwork');
const bounds = __LAYOUT_BOUNDS__;
network.moveTo({position: {x: 0, y: 0}, scale: Math.min(viewport.clientWidth / bounds.x, viewport.clientHeight / bounds.y)});
</script></body>""".replace("__LAYOUT_BOUNDS__", json.dumps(network.layout_bounds)),
            1,
        )
    return html

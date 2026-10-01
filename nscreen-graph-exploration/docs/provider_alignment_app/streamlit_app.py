"""Separate provider-alignment walkthrough. Suggested port: 8504."""

import json

import streamlit as st
from alignment_example import ALIASES, REPO_ROOT, build_example, build_steps, graph_for
from alignment_graph import HEIGHT, to_html, with_stable_positions
from alignment_history import incremental_graph

st.set_page_config(page_title="Provider alignment walkthrough", page_icon=":material/hub:", layout="wide")
st.html("""
<style>
@media (min-width: calc(736px + 8rem)) {
    [data-testid="stMainBlockContainer"] {
        padding-left: 1rem !important;
        padding-right: 1rem !important;
    }
}
</style>
""")
st.title("Provider alignment walkthrough")
data = build_example()
steps = build_steps(data)

with st.sidebar:
    number = st.radio(
        "Pipeline step", range(len(steps)), format_func=lambda n: f"{n}. {steps[n]['title']}", key="alignment_step"
    )
    step = steps[number]
    st.subheader(f"{number}. {step['title']}")
    st.write(step["note"])

with st.container(horizontal=True):
    graph_info = st.popover(
        "Graph info",
        icon=":material/info:",
        type="tertiary",
        help="Color = current step; gray = history; lighter gray = future preview. Teal long-dashed = IP-collocation; green = accepted; red short-dashed = rejected; amber = candidate. Click for the full legend, controls and dataset scope.",
    )
with graph_info:
    st.caption("LiveRamp · Throtle · Experian → connected seeds → propagation → remainder → final result")
    with st.expander("Scope and differences from the document", expanded=False):
        st.markdown(
            "Uses the expanded provider-alignment-toy.ipynb dataset: 14 Throtle claims, 12 LiveRamp claims, five Experian claims and eight IP edges. "
            "Numeric match IDs preserve production-style numeric tie-breaks; short aliases are display labels. "
            "Additional production fields: LiveRamp stable=true, all source household IDs=0. "
            "Notebook geo inputs place v33 in G3, v34 in G4, and other edge endpoints in G1; both edge flags=false. These are illustrative inputs.\n\n"
            "All 21 Job 1 rows go to lrth. There are **58 staged rows** and **29 exported rows for 26 UIDs**. "
            "L6 gains LREX through E3; v33/v34 are excluded by the geo check. "
            "v9-v24/v25/v26 are IP-collocated, which makes all four graph-connected (`connected_ns` grows from 4 to 8 rows) without changing a single matchid: every one of them was already assigned before propagation runs, so none is a candidate. "
            "Production SQL doubles stable propagation scores (10, 4, 6); the notebook's simplified propagation omits that multiplier.\n\n"
            "Python computes the alignment and propagation snapshots. The Louvain result is a fixed "
            "two-UID reference with synthetic match C1, not a clustering engine inside this app. "
            "See README.md for reproducible SQL/Java checks. No production tables are read or written."
        )
        st.dataframe([{"alias": label, "numeric_matchid": value} for value, label in ALIASES.items()], hide_index=True)

snapshots = [graph_for(item, data) for item in steps]
graph = with_stable_positions(incremental_graph(snapshots, number), graph_for(steps[-1], data, full=True))
graph["focus_final"] = number == len(steps) - 1
graph_info.caption(
    "Color: current step. Gray: earlier context. Lighter gray: future relationships and their endpoints, not yet produced. Only current relationship labels are shown; hover for details and step history. Captured force-layout positions from the complete final incremental graph are reused (24 trials of 12,000 iterations per non-singleton component). Manual dragging resets when changing steps."
)
with st.container(horizontal=True):
    labels = st.toggle("Relationship labels", value=True, key="alignment_labels")
graph_info.caption(
    f"{len(graph['nodes'])} nodes · {len(graph['links'])} relationships · 900px canvas. "
    "UID: blue ellipse · Throtle: amber box · LiveRamp: green diamond · Experian: purple triangle · Louvain: cyan hexagon."
)
graph_info.caption(
    "Arrows: memberships or candidate translations. Gray solid lines: shared-UID evidence. Teal long-dashed lines: IP-collocation. Rejected relationships stay red; IP-collocation keeps its long-dash pattern. Green: accepted; amber: candidate. Drag, zoom, hover for details; fit button shows all nodes."
)
if graph["focus_final"]:
    graph_info.caption("Final-result focus mutes earlier context and IP-collocation edges in light gray.")
html = to_html(graph, physics=False, labels=labels)
st.iframe(html, height=HEIGHT, tab_index=0)
with st.container(horizontal=True):
    st.download_button(
        "Graph as HTML", html, file_name=f"provider-alignment-{number}.html", mime="text/html", on_click="ignore"
    )
    st.download_button(
        "Graph as JSON",
        json.dumps(graph, indent=2),
        file_name=f"provider-alignment-{number}.json",
        mime="application/json",
        on_click="ignore",
    )
    st.download_button(
        "All steps as JSON",
        json.dumps(steps, indent=2),
        file_name="provider-alignment-all-steps.json",
        mime="application/json",
        on_click="ignore",
    )

st.subheader("Step inputs and outputs")
for title, rows in step["tables"].items():
    st.markdown(f"**{title}** · {len(rows)} rows")
    st.dataframe(rows, hide_index=True)

with st.expander("Complete input dataset"):
    for title, rows in steps[0]["tables"].items():
        st.markdown(f"**{title}**")
        st.dataframe(rows, hide_index=True)
with st.expander("Exact graph nodes and relationships"):
    st.dataframe(graph["nodes"], hide_index=True)
    st.dataframe(graph["links"], hide_index=True)
with st.expander("Source files and line numbers"):
    for path, start, end in step["sources"]:
        st.markdown(f"**{path}:{start}**")
        file = REPO_ROOT / path
        if file.is_file():
            lines = file.read_text().splitlines()
            snippet = "\n".join(f"{n}: {lines[n - 1]}" for n in range(start, min(end, len(lines)) + 1))
            language = (
                "sql"
                if path.endswith(".sql")
                else "java"
                if path.endswith(".java")
                else "python"
                if path.endswith(".py")
                else "markdown"
            )
            st.code(snippet, language=language)
        else:
            st.caption("Source is available only inside the Forge checkout.")

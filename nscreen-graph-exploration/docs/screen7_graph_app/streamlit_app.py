"""Run with: streamlit run nscreen-graph/docs/screen7_graph_app/streamlit_app.py."""

import json

import streamlit as st
from example import EXAMPLE_EDGES, REPO_ROOT, TITLES, build_steps
from interactive_graph import GRAPH_HEIGHT_PX, to_html, to_network
from screen7_history import incremental_graph

st.set_page_config(page_title="Screen7 graph walkthrough", page_icon=":material/hub:", layout="wide")
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
st.title("Screen7 graph walkthrough")
steps = build_steps()

with st.sidebar:
    step_number = st.radio("Grouping step", range(8), format_func=lambda index: f"{index}. {TITLES[index]}", key="step")
    step = steps[step_number]
    st.subheader(f"{step_number}. {step['title']}")
    st.write(step["note"])
    st.caption(
        "Fixed example from the documentation. Community memberships are Java-verified reference assignments; "
        "this viewer does not run clustering on arbitrary datasets. D/M/H labels replace random numeric IDs."
    )

with st.container(horizontal=True):
    detailed_labels = st.toggle("Detailed node labels", key="detailed_labels")
    physics = st.toggle("Force layout", value=False, disabled=True, key="physics")
    graph_info = st.popover(
        "Graph info",
        icon=":material/info:",
        type="tertiary",
        help="Color = current step; gray = history in Incremental view. Arrows = membership; undirected lines = evidence. Click for the full legend and view details.",
    )
graph = incremental_graph(steps, step_number)
export_name = f"screen7-step-{step_number}-incremental"
with graph_info:
    st.caption("12 UIDs · 4 preliminary households · 6 matches · 3 final households")
    st.caption(
        "Color: current-step evidence and newly created mappings. Gray: earlier relationships. Future relationships are hidden. Hover for weights, source rows and step history. Repeated graph layers are not additional evidence to sum."
    )
    st.caption(
        "Captured force-layout positions from the full final graph stay fixed across steps (24 trials of 12,000 iterations per connected component). No preliminary-household nodes. Live physics is disabled; manual dragging resets on step changes."
    )

with graph_info:
    st.caption(
        "PyVis / vis-network · drag nodes or the background · scroll to zoom · hover for full details · "
        "click a node to highlight its connections · use the bottom-right fit button to show everything. "
        "Node positions are visual only; dragging never changes groups."
    )
    st.caption(
        "Node legend · UID: blue ellipse · device: amber box · match: purple diamond · household: green hexagon. "
        "Borders still show final-household membership."
    )
network = to_network(
    graph, step=step_number, detailed_labels=detailed_labels, physics=physics, height_px=GRAPH_HEIGHT_PX
)
html = to_html(network)
html = html.replace("height: 650px;", f"height: {GRAPH_HEIGHT_PX}px;")
st.iframe(html, height=GRAPH_HEIGHT_PX, tab_index=0)
st.download_button(
    "Interactive graph as HTML",
    html,
    file_name=f"{export_name}.html",
    mime="text/html",
    on_click="ignore",
)

if step_number >= 6:
    st.subheader("Preliminary to final household")
    transitions = {}
    for row in step["uid_assignments"]:
        match = row["internal_matchid"]
        transition = transitions.setdefault(
            match,
            {
                "match": match,
                "preliminary": row["preliminary_householdid"],
                "final": row["internal_householdid"],
                "changed": row["household_changed"],
                "uids": [],
            },
        )
        transition["uids"].append(row["uid"])
    st.dataframe(list(transitions.values()), hide_index=True)
    st.caption("M2 moves as one unit: u4, u5, and u6 stay together. H2 disappears; no new household label is minted.")

with st.container(horizontal=True):
    st.download_button(
        "All steps as JSON",
        json.dumps(steps, indent=2),
        file_name="screen7-all-steps.json",
        mime="application/json",
        on_click="ignore",
    )

st.subheader("UID assignments at this step")
st.dataframe(step["uid_assignments"], hide_index=True)
if step_number == 7:
    st.caption("matchid and householdid are returned fields. internal_* fields explain how those values were derived.")

with st.expander("Complete input dataset"):
    st.dataframe(
        [
            {
                "row": edge.source_rows[0],
                "uid1": edge.source,
                "uid2": edge.target,
                "weight": edge.weight,
                "sameDevice": edge.same_device,
                "differentUsers": edge.different_users,
            }
            for edge in EXAMPLE_EDGES
        ],
        hide_index=True,
    )

with st.expander("Graph nodes and relationships"):
    st.caption("This is the exact graph data used by the selected view, including self-edges and provenance.")
    st.dataframe(graph["nodes"], hide_index=True)
    st.dataframe(graph["links"], hide_index=True)
    if step["excluded_relationships"]:
        st.caption("Cross-household edges excluded from Step 4 only; Step 5 uses them again.")
        st.dataframe(step["excluded_relationships"], hide_index=True)

with st.expander("Java source for this step"):
    for path, start, end in step["sources"]:
        st.markdown(f"**{path.rsplit('/', 1)[-1]}:{start}**")
        source_file = REPO_ROOT / path
        if source_file.is_file():
            source = source_file.read_text().splitlines()
            numbered = "\n".join(
                f"{number}: {source[number - 1]}" for number in range(start, min(end, len(source)) + 1)
            )
            st.code(numbered, language="java")
        else:
            st.caption(f"Source unavailable outside the Forge checkout: {path}")

"""Streamlit view for upstream IP and first-party relationship construction."""

import json

import streamlit as st
from collocation_example import ALIASES, OBSERVATIONS, PIXELS, build_collocation_steps, collocation_graph
from example import REPO_ROOT
from interactive_graph import GRAPH_HEIGHT_PX, to_html, to_network


def render_collocation():
    st.subheader("IP collocation and first-party relationships")
    st.caption(
        "A complete upstream example: A/B share ip1; A/B/C/D share ip2. "
        "Three days of IP evidence and five recording events show how clean UID relationships are formed. "
        "This is a separate example from the grouping tab; its seven output edges are not the grouping tab's eleven inputs."
    )
    steps = build_collocation_steps()
    number = st.sidebar.radio(
        "Relationship phase",
        range(len(steps)),
        format_func=lambda i: f"{i}. {steps[i]['title']}",
        key="collocation_step",
    )
    step = steps[number]
    st.write(step["note"])
    full = st.sidebar.toggle("Full graph: IPs, recording events, and final UID pairs", key="collocation_full")
    st.sidebar.caption(
        "IP and first-party relationship construction. Select a phase to inspect its graph, rows, and SQL source."
    )
    if full:
        st.caption(
            "Overview of retained UID/IP observations, accepted event identifiers, and the seven final pairs. Rejected IP groups remain in the input tables. Context links describe observations; only UID-UID links are clean graph output."
        )
    elif number == 2:
        st.caption(
            "Graph zooms into September 9 to match your drawing: ip1 contributes 0.5 and ip2 contributes 0.25. The table includes contributions from every input hour."
        )
    st.caption(
        "UID: pale-blue ellipse · IP: blue circle · recording event: orange star. Hover for source rows and weights. Drag, zoom, and use fit-to-view; canvas height is 900 px."
    )
    graph = collocation_graph(steps, number, full=full)
    html = to_html(to_network(graph, step=0))
    st.iframe(html, height=GRAPH_HEIGHT_PX, tab_index=0)
    with st.container(horizontal=True):
        st.download_button(
            "Collocation graph as HTML",
            html,
            file_name="collocation-graph.html",
            mime="text/html",
            key="collocation_html",
            on_click="ignore",
        )
        st.download_button(
            "Collocation steps and graph as JSON",
            json.dumps({"steps": steps, "graph": graph}, indent=2),
            file_name="collocation-example.json",
            mime="application/json",
            key="collocation_json",
            on_click="ignore",
        )
    st.subheader("Rows at this phase")
    st.dataframe(step["rows"], hide_index=True)
    for key, title in (("ip_stats", "IP eligibility"), ("daily", "Daily IP pairs"), ("union", "Rows before MAX merge")):
        if key in step:
            st.caption(title)
            st.dataframe(step[key], hide_index=True)
    with st.expander("Complete input and UID aliases"):
        st.caption(
            "Starting boundary: normalized IPs and eligible, exploded UID observations. All listed observations are the complete input; dates not listed have no rows. Real UID strings, rather than A/B display aliases, determine SQL ordering. UA lookup is empty in this fixture."
        )
        st.dataframe([{"alias": alias, "uid": uid} for uid, alias in ALIASES.items()], hide_index=True)
        st.dataframe(OBSERVATIONS, hide_index=True)
        st.dataframe(PIXELS, hide_index=True)
    with st.expander("Graph nodes and relationships", expanded=False):
        st.dataframe(graph["nodes"], hide_index=True)
        st.dataframe(graph["links"], hide_index=True)
    with st.expander("Source code for this phase"):
        for path, start, end in step["sources"]:
            st.markdown(f"**{path}:{start}**")
            file = REPO_ROOT / path
            if file.is_file():
                lines = file.read_text().splitlines()
                st.code(
                    "\n".join(f"{n}: {lines[n - 1]}" for n in range(start, min(end, len(lines)) + 1)),
                    language="sql" if path.endswith(".sql") else "java" if path.endswith(".java") else "python",
                )

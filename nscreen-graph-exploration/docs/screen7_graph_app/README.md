# Screen7 graph walkthrough

Interactive companion to [the evaluator guide](../udaf-calc-screen7-ids-evaluator.md).
The app shows only the Java-verified Screen7 device / match / household
grouping example, with grouping controls in the sidebar.

**Incremental** is now the default graph view. Previous nodes and relationships
remain gray; current evidence and newly created mappings stay colored. Future
relationships are hidden, even when navigating backwards. Tooltips preserve
weights, flags, source rows and the steps where each relationship appeared.
Current mappings appear at Steps 1 (UID → device), 4 (device → match),
6 (match → final household), and 7 (all returned identity mappings).

The incremental view reuses captured force-layout coordinates from `fixed_layout.json`.
`optimize_layout.py` ran NetworkX Fruchterman–Reingold on the full final graph
(29 nodes, 55 relationships), independently per connected component: 24 seeds ×
12,000 iterations × 2 components = 576,000 iterations. Candidates were ranked by
straight-edge crossings, then bounding-box area; the selected layout has two
crossings and at least 170 layout pixels between node centers (before rounding).
Self-loops/shared endpoints are excluded from that score; browser curves and
labels may still overlap. Unit force weights affect presentation only.
Run `uv run --no-project --python ../../../.venv/bin/python python optimize_layout.py`
from this directory to print replacement JSON (NetworkX 3.6.1).
The app loads saved coordinates without optimizing again, and preserves the
same viewport across steps. Gray edges remain visible; live physics is disabled, and
manual dragging resets on step changes. Only final households become nodes;
preliminary households remain annotations/tables. PyVis grays historical
context. There is no renderer or graph-view selector;
all eight sidebar steps use the incremental graph, with no calculation changes.

The unused upstream example modules remain available separately, outside the app.
That example starts with normalized, UID-exploded observations. It shows
IP sizes 2 and 4 contributing 0.5 and 0.25 per pair, the 2-to-8-UID filter,
hour/day aggregation, and the three-day IP gate. First-party identifiers are
paired by event GUID and deduplicated per hour; their lookback weights count
hourly pair rows. Clean merging uses MAX weight and both flags, followed by two
top-10 ranks. Its seven final pairs are a separate dataset from the grouping
example's eleven input rows. Empty UA metadata makes both UA predicates false.

`verify_collocation_spark.py` executes the seven repository SQL files against
this fixture using local Spark. IP normalization and UA predicate results are
stubbed only for this already-normalized, missing-UA example; SQL joins,
filters, aggregation, and ranking run from the repository sources. Run from
this directory with the shared root environment:

```bash
JAVA_HOME=/opt/homebrew/opt/openjdk@21 SPARK_LOCAL_IP=127.0.0.1 uv run --no-project --python ../../../.venv/bin/python python verify_collocation_spark.py
```

Select input or Steps 1–7 to follow the incremental graph. Step 7 shows all
UID → device → match → household memberships and evidence together, with history gray.

The only app renderer is [PyVis](https://pyvis.readthedocs.io/en/latest/), powered
by vis-network. Drag nodes, pan, zoom, hover for details, and click a node to
highlight its connections. Navigation buttons include fit-to-view. The interactive
graph uses captured coordinates with live physics disabled.
Positions are visual only and never change the verified assignments.
Toggle detailed labels to expand node annotations.
Download the interactive graph as HTML or all steps as JSON.

At Step 7, select **Full graph** to see all 29 final nodes and 55 relationships:
12 UID → device links, 8 device → match links, 6 match → final-household links,
11 original UID evidence edges, 10 collapsed device edges, and 8 collapsed match
edges. Blue arrows denote membership; evidence edges remain undirected, with
weights, flags, source-row provenance, and self-loops preserved. The evidence
layers are different representations of the same input, not additional weights
to add together. This view does not run another grouping step.

Only final households H1/H3/H4 are household nodes. Former H2 is retained in
change annotations and the before/after table, not as a current membership.
All internal matches remain separate even when the returned match ID is zero.

Every relationship shows its weight, flags, and original input-row provenance.
Self-edges are retained. UID tables distinguish internal identities from returned
zero sentinels. The Java source panel shows the relevant file and line numbers.

The example has 12 UIDs, 8 devices, 4 preliminary households, 6 internal matches,
and 3 final households. Step 6 shows `M2` moving from `H2` into `H1`, carrying
`u4`, `u5`, and `u6` together. Its before/after table and graph labels expose
that change. Bridges excluded from the Step 4 Louvain scopes are retained in
Step 5's complete graph.

## Run

Follow the [shared environment setup](../../../README.md#set-up-the-shared-environment)
once. Both apps, notebooks, and verification scripts use the repository-root `.venv`.
Start the app from the repository root:

```bash
uv run --no-project --python .venv/bin/python python -m streamlit run nscreen-graph-exploration/docs/screen7_graph_app/streamlit_app.py --server.port 8502
```

Graph rendering happens in the browser; no Graphviz system binary is needed.
PyVis embeds its network library into exported HTML. Its standard template also
loads Bootstrap styling/scripts from a public CDN; no graph dataset is sent to it.

## Scope and correctness

This is a viewer for the **fixed eleven-row example**, not a general-purpose
Python replacement for the Java UDAF. Device, match, and household memberships
are explicit reference assignments checked against the actual Java evaluator
in 1,000 shuffled runs, including complete and partial-merge execution paths.
Collapses, member lists, and singleton output rules are derived in Python.
If the example changes, its reference memberships must be revalidated against
Java. Python floats are used for display; generated Java labels are replaced
with readable D/M/H labels.

Steps 0–6 show their relationship graphs. Step 7 overlays returned UID
assignments on the original evidence; the UDAF itself returns structs, not
edges. Identity arrows are membership relationships, never extra input evidence.
The downstream SQL filter is annotated but is not applied to the UDAF output.

## Reuse the graphs

`example.build_steps()` returns eight dictionaries. Each contains `evidence`
and `identities` graphs in NetworkX node-link form (`nodes` and `links`), the
UID assignment table, and source locations. `example.to_dot()` generates DOT.
Both graph views and all-step JSON are downloadable in the app.
The final combined graph is also available as `build_steps()[7]["full"]` and in
the all-step JSON export. Its node-link container is directed to support the
membership arrows; read each edge's `directed` flag to distinguish undirected
evidence when consuming this mixed graph outside the app.

If NetworkX is installed separately:

```python
import networkx as nx
from example import build_steps

steps = build_steps()
graph = nx.node_link_graph(steps[3]["evidence"], edges="links")
print(graph.nodes(data=True))
print(graph.edges(data=True))
```

## Tests

```bash
uv run --no-project --python .venv/bin/python python -m pytest -c /dev/null -p no:cacheprovider nscreen-graph-exploration/docs/screen7_graph_app/test_app.py
```

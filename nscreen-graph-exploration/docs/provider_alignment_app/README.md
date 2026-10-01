# Provider alignment walkthrough

Separate Streamlit app for the expanded dataset in
[provider-alignment-toy.ipynb](../../provider-alignment-toy.ipynb), illustrating
[provider-alignment-phase.md](../analysis/provider-alignment-phase.md).
The Screen7 app is not changed or imported.

## Run

Follow the [shared environment setup](../../../README.md#set-up-the-shared-environment)
once. Both apps, notebooks, and verification scripts use the repository-root `.venv`.
Start the app from the repository root:

```bash
uv run --no-project --python .venv/bin/python python -m streamlit run nscreen-graph-exploration/docs/provider_alignment_app/streamlit_app.py --server.port 8504 --server.address 127.0.0.1
```

## Views

Nineteen screens show the full input, shared-UID joins, shared counts, both ranks,
uniqueness counters, accepted mappings, Job 1 writes, Experian alignment and writes,
connected seeds, candidate scoring and winners for both propagation rounds,
same-geo remainder filtering, Louvain output, the full staged table, diagnostics,
and final exported result.

Each screen includes input/output tables and repository source excerpts with line
numbers. PyVis graphs use a 900px canvas, distinct shapes and background colors,
plain multiline tooltips, pan/zoom, drag and fit controls. HTML and JSON exports
are available. IP-collocation relationships use teal long-dashed lines, while
shared-UID evidence uses solid gray lines. Rejected relationships remain red;
their dash length still distinguishes IP-collocation from other rejections.
Graph positions have no effect on assignments.

**Incremental** is the default graph view. It retains nodes and relationships from
all steps. Current-step elements keep their colors; earlier
context fades to gray; future edges and endpoints use lighter gray. Non-current edge labels are hidden to reduce clutter, while
tooltips retain original details and the steps where each relationship appeared.
Repeated identical records share one history entry; different stages, reasons,
rank records, and within-step duplicate occurrences remain distinct.

Future nodes/relationships are explicitly labeled as previews in tooltips, not
current outputs. Going backwards recalculates their status. Captured force-layout coordinates and a shared camera keep positions consistent
between steps; force layout is disabled in incremental mode. Manual dragging resets
on a rerun. The final-result view fades earlier context to extra-light gray and
mutes current IP-collocation edges in light gray, so exported membership
relationships remain visually dominant. Only the incremental view is available;
there are no view or force-layout selectors.

`fixed_layout.json` stores an offline NetworkX Fruchterman–Reingold layout of the
complete final incremental graph: 45 nodes and 146 stage-specific relationships.
`optimize_layout.py` tries 24 seeds with 12,000 iterations each for each of eight
connected components (2,304,000 iterations). It selects candidates by straight-edge
crossings, then area, scales node-center spacing to 170 layout pixels, and packs
components into rows. Parallel relationships remain in the displayed graph;
the force solver uses unique endpoint pairs with unit visual weights.
The selected layout has two straight-edge crossings. This score excludes shared
endpoints and self-loops; curved browser edges and labels can still overlap.
No alignment calculations change, and navigation never reruns the optimizer.
To print regenerated coordinates using NetworkX 3.6.1, run from this directory:
`uv run --no-project --python ../../../.venv/bin/python python optimize_layout.py`.
All changes are presentation-only; input data and SQL/Java reference results are unchanged.

The incremental graph includes all 45 nodes and 146 stage-specific relationships,
with future entries explicitly styled as previews. Parallel claims remain distinct.
Repeated stage memberships are history, not extra evidence to sum.
No preliminary-household nodes are introduced.

## Exact scope and differences from the Markdown

This uses the notebook's expanded 14 Throtle rows, 12 LiveRamp rows, five Experian
rows and eight activity edges. L6/E3 adds LiveRamp-only alignment with Experian:
v30/v31/v32 receive L6 with reason LREX. The v33-v34 edge adds a geo-mismatch
rejection: neither UID receives an assignment. The remainder screen shows this
rejected edge in red alongside the accepted v19-v21 edge. The v9-v24/v25/v26
edges add a graph-connectivity case: all four already have a matchid, so the
edges make them graph-connected (`connected_ns` copies) without ever making
v24/v25/v26 candidates to inherit v9's LiveRamp match.
The model derives snapshots in Python; it does not read production tables or run
Spark on app reruns. It is an educational fixed-example viewer, not a replacement
for the production pipeline or an arbitrary-data clustering service.

Fields omitted by the notebook's simplified queries are explicit fixture choices:

- Provider match IDs are numeric (T1=101, L1=201, E1=301, etc.). Graph labels use
  aliases; SQL tie-breaks compare numbers. C1=901 aliases the random UDAF match ID.
- LiveRamp `stable=true`; all source `householdid=0`.
- Both edge flags are false. Notebook geo rows cover only edge endpoints:
  v33 is in G3, v34 in G4, and all other endpoints are in G1.
- The two-UID Louvain component returns one shared nonzero match, two device IDs,
  and household ID 0. Only the match assignment is displayed in this phase.

Production writes override Job 1's SQL stage literals. The model applies that
override: **21 lrth + 24 initial + 8 connected_ns + 2 stage1 + 1 stage2 + 2 louvain
= 58 staged rows**, matching the expanded notebook.
Every L1 member in `initial` is `LRTHEX`, including v1/v2/v9. The final result is
29 rows for 26 UIDs; v6 retains three matches and v13 retains two. The two
unassigned UIDs remain visible as input history, not as result rows. Diagnostics
match the notebook's staged-table query and do not invent zero-count rows for them.

Propagation doubles weights from stable seeds before ranking: v17/L1 scores 10,
v20/T3/T4/T5 score 4 each, and v18/L1 scores 6. The notebook omits the stable multiplier; the app retains the
production SQL rule. This changes displayed scores but not this fixture's winners.
The cap is applied after choosing
one match per UID; alternatives are not reconsidered. This small fixture does not
hit the cap; a unit test exercises that ordering separately.

The final SQL is not only a stage filter: it also removes zero match IDs, `LR_`
UIDs with reason `IC`, and placeholder UIDs, prefixes stable IDs with `S_`, and
turns household ID 0 into empty text. The model includes these rules.

## Validation

From this directory, using the shared root environment:

```bash
uv run --no-project --python ../../../.venv/bin/python python -m pytest test_alignment.py test_history.py test_notebook_fixture.py -q
uv run --no-project --python ../../../.venv/bin/python python -m ruff check .
uv run --no-project --python ../../../.venv/bin/python python -m ruff format --check .
```

`verify_spark.py` compiles the current repository Java calculator/UDAF and runs
all seven repository SQL files (propagation twice) against local temporary views.
It compares row multisets, counts, rank counters, stable-weight boosts, assignments,
58 staged rows and 29 exported rows. The external `murmur3` UDF alone is replaced
by collision-free toy UID numbers; **the Screen7 Java UDAF itself is executed**.
Random community IDs are canonicalized to 901 after checking shared membership.
No production catalog is contacted and no source SQL/Java is edited.

Needs a JDK, PySpark from the shared root environment, and a fastutil JAR:

```bash
JAVA_HOME=/opt/homebrew/opt/openjdk@21 SPARK_LOCAL_IP=127.0.0.1 uv run --no-project --python ../../../.venv/bin/python python verify_spark.py --fastutil /path/to/fastutil-8.1.1.jar
```

Spark requires permission to bind local sockets. The Java compilation uses a
temporary directory and removes its outputs when finished. PyVis bundles its
network library in exported HTML; the standard template also references Bootstrap
from a public CDN. No graph data is sent to that CDN.

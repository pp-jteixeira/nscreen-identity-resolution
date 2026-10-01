# Graph Report - nscreen_analysis  (2026-09-18)

## Corpus Check
- Corpus is ~45,352 words - fits in a single context window. You may not need a graph.

## Summary
- 169 nodes · 375 edges · 16 communities (14 shown, 2 thin omitted)
- Extraction: 98% EXTRACTED · 2% INFERRED · 0% AMBIGUOUS · INFERRED: 6 edges (avg confidence: 0.9)
- Token usage: unavailable for host-agent review; no external LLM API was called.

## Community Hubs (Navigation)
- Project Setup and Documentation
- Collocation Pipeline Viewer
- Provider Alignment Model
- Alignment History Visualization
- Screen7 Graph Model
- Interactive Graph Rendering
- Alignment Fixtures Layout
- Interactive Graph Rendering
- Screen7 Graph Model
- Interactive Graph Rendering
- Notebook Verification
- Interactive Graph Rendering
- Spark Java Verification
- Screen7 Graph Model
- Identity Reconciliation Analysis
- Identity Reconciliation Analysis

## God Nodes (most connected - your core abstractions)
1. `build_steps()` - 29 edges
2. `build_example()` - 21 edges
3. `to_network()` - 21 edges
4. `build_steps()` - 15 edges
5. `to_html()` - 15 edges
6. `NScreen Identity Resolution` - 14 edges
7. `graph_for()` - 13 edges
8. `incremental_graph()` - 10 edges
9. `build_collocation_steps()` - 9 edges
10. `Provider Neutral Canonical Matchids` - 9 edges

## Surprising Connections (you probably didn't know these)
- `NScreen Graph Terse Guide` --semantically_similar_to--> `NScreen Graph Pipeline`  [INFERRED] [semantically similar]
  nscreen-graph-exploration/docs/guides/graph-pipeline-caveman.md → nscreen-graph-exploration/docs/guides/graph-pipeline.md
- `NScreen Identity Resolution` --references--> `First Party Collocation Daily`  [EXTRACTED]
  README.md → nscreen-graph-exploration/docs/nscreen-1p-collocation-daily-recap.md
- `NScreen Identity Resolution` --references--> `Shared Python Dependencies`  [EXTRACTED]
  README.md → requirements.txt
- `NScreen Identity Resolution` --references--> `Provider Neutral Canonical Matchids`  [EXTRACTED]
  README.md → nscreen-graph-exploration/docs/plans/matchid-collocation-reconciliation-plan.md
- `NScreen Identity Resolution` --references--> `Matchid Reduction Options`  [EXTRACTED]
  README.md → nscreen-graph-exploration/docs/analysis/matchid-reduction-options.md

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **Matchid Reduction Strategy** — nscreen_graph_exploration_docs_analysis_matchid_reduction_options_liveramp_consolidation, nscreen_graph_exploration_docs_analysis_matchid_reduction_options_capacity_aware_propagation, nscreen_graph_exploration_docs_analysis_matchid_reduction_options_reduction_guardrails [EXTRACTED 1.00]
- **NScreen Identity Pipeline** — nscreen_graph_exploration_docs_guides_graph_pipeline_hourly_evidence, nscreen_graph_exploration_docs_guides_graph_pipeline_daily_clean_graph, nscreen_graph_exploration_docs_guides_graph_pipeline_provider_alignment, nscreen_graph_exploration_docs_guides_graph_pipeline_identity_propagation, nscreen_graph_exploration_docs_guides_graph_pipeline_remainder_clustering [EXTRACTED 1.00]

## Communities (16 total, 2 thin omitted)

### Community 0 - "Project Setup and Documentation"
Cohesion: 0.07
Nodes (41): Capacity Aware Propagation, LiveRamp Identity Consolidation, Matchid Reduction Options, Matchid Reduction Guardrails, Propagation Cap Ordering Defect, Stage Literal Defect, Propagation Assignment Loss, Mutual Best Rank (+33 more)

### Community 1 - "Collocation Pipeline Viewer"
Cohesion: 0.20
Nodes (13): build_collocation_steps(), collocation_graph(), pair_row(), Executable example of the IP and first-party SQL relationship stages. Input…, Streamlit view for upstream IP and first-party relationship construction., render_collocation(), identity_graph(), node_link() (+5 more)

### Community 2 - "Provider Alignment Model"
Cohesion: 0.24
Nodes (14): align(), build_example(), final_result(), propagate(), Expose joined, grouped, ranked, limited, and mapping without UID dedup., Independent PyVis renderer; no imports or mutations of the Screen7 app., to_html(), to_network() (+6 more)

### Community 3 - "Alignment History Visualization"
Cohesion: 0.25
Nodes (13): graph_for(), layout_positions(), Load offline force-layout coordinates; never optimize during navigation., with_stable_positions(), incremental_graph(), Presentation-only history: no changes to pipeline calculations., Union all snapshots; distinguish current, historical and future entries.…, Separate provider-alignment walkthrough. Suggested port: 8504. (+5 more)

### Community 4 - "Screen7 Graph Model"
Cohesion: 0.22
Nodes (11): build_steps(), collapse_graph(), Apply collapseGraph's rules, retaining source-row provenance for display., Return independent graph snapshots for input and all seven steps., test_all_steps_keep_every_uid_without_future_assignments(), test_collapses_preserve_provenance_and_internal_edges(), test_cross_household_bridges_reappear_after_match_grouping(), test_documented_output_matches_app() (+3 more)

### Community 5 - "Interactive Graph Rendering"
Cohesion: 0.24
Nodes (9): node_color(), node_type(), PyVis rendering only: no changes to the Java-verified graph snapshots., to_network(), Run with: streamlit run nscreen-graph/docs/screen7_graph_app/streamlit_app.py., test_collapsed_graph_node_kinds_receive_identity_styles(), test_interactive_annotations_and_controls(), test_interactive_graph_does_not_deduplicate_parallel_edges() (+1 more)

### Community 6 - "Alignment Fixtures Layout"
Cohesion: 0.29
Nodes (7): build_steps(), output_alignment(), Computed walkthrough of the expanded notebook inputs with production semantics.…, source(), crossing_count(), optimize(), Optimize the final provider alignment graph offline; emit captured coordinates…

### Community 7 - "Interactive Graph Rendering"
Cohesion: 0.42
Nodes (6): current_graph(), incremental_graph(), Incremental presentation of Screen7 snapshots, without changing calculations., test_captured_force_positions_and_viewport(), test_history_renderers_keep_gray_edges_and_provenance(), test_incremental_history_no_future_or_preliminary_nodes()

### Community 8 - "Screen7 Graph Model"
Cohesion: 0.33
Nodes (6): Edge, evidence_graph(), full_graph(), Graph snapshots for the fixed, Java-verified eleven-row documentation example.…, Combine final memberships with all three evidence resolutions, without…, uid_assignments()

### Community 9 - "Interactive Graph Rendering"
Cohesion: 0.33
Nodes (6): Network, Make trusted, fixed-example tooltips preserve newline detail text., to_html(), test_interactive_graph_preserves_snapshots(), test_interactive_tooltips_use_newlines_not_literal_html_tags(), parametrize

### Community 10 - "Notebook Verification"
Cohesion: 0.60
Nodes (4): notebook_code(), Read notebook literals only; never execute its database-writing cells., test_diagnostics_match_notebook_and_geo_rejection_is_visible(), test_sources_match_expanded_notebook()

### Community 11 - "Interactive Graph Rendering"
Cohesion: 0.40
Nodes (5): node_label(), Use the same assignment annotations in both graph renderers., Render evidence (undirected) or membership (directed) without losing loops., to_dot(), test_final_full_graph_renderers_preserve_mixed_edge_directions()

### Community 12 - "Spark Java Verification"
Cohesion: 0.67
Nodes (3): compile_udaf(), Execute repository SQL and the actual Java UDAF on local toy tables. Requires…, verify()

### Community 13 - "Screen7 Graph Model"
Cohesion: 0.67
Nodes (3): crossing_count(), optimize(), Optimize the final Screen7 graph offline; emit captured coordinates as JSON.…

## Knowledge Gaps
- **19 isolated node(s):** `Provider Alignment Incremental Graph`, `Screen7 Incremental Graph`, `Stage Literal Defect`, `NScreen Graph Terse Guide`, `Matchid Reduction Guardrails` (+14 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 53 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **2 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `to_network()` connect `Provider Alignment Model` to `Interactive Graph Rendering`, `Alignment History Visualization`?**
  _High betweenness centrality (0.268) - this node is a cross-community bridge._
- **Why does `to_network()` connect `Interactive Graph Rendering` to `Collocation Pipeline Viewer`, `Screen7 Graph Model`, `Interactive Graph Rendering`, `Interactive Graph Rendering`, `Interactive Graph Rendering`?**
  _High betweenness centrality (0.175) - this node is a cross-community bridge._
- **Why does `to_html()` connect `Interactive Graph Rendering` to `Collocation Pipeline Viewer`, `Screen7 Graph Model`, `Interactive Graph Rendering`, `Interactive Graph Rendering`, `Interactive Graph Rendering`?**
  _High betweenness centrality (0.128) - this node is a cross-community bridge._
- **What connects `Provider Alignment Incremental Graph`, `Screen7 Incremental Graph`, `Stage Literal Defect` to the rest of the system?**
  _19 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Project Setup and Documentation` be split into smaller, more focused modules?**
  _Cohesion score 0.07073170731707316 - nodes in this community are weakly interconnected._
## Refresh Method

Refreshed against current source files. Python structure was re-extracted with the AST parser. Reviewed document concepts were retained with relocated source paths and identifiers; deleted dependency files were pruned. README, shared-environment, and reconciliation concepts were added, and document citations were rebuilt from current relative links. Community memberships, report, and HTML were regenerated. No warehouse queries or application execution were performed.

### Extraction diagnostics

Raw extraction contained 99 edges with unresolved endpoints before Graphify build-time resolution, and 3 parallel edge variants collapsed by the undirected graph. The graph is a navigation summary; it does not retain every distinct call/reference relationship.

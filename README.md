# NScreen Identity Resolution

Analysis and prototypes to improve NScreen identities using vendor mappings, IP-collocation, first-party data, and device evidence.

**Goal: each UID maps to one matchid; each matchid can contain many UIDs.** Reconciliation covers both different vendors and multiple IDs from the same vendor.

This repository contains research, examples, and a [prepared-source replay pipeline](nscreen-replay/README.md). Production code lives at `~/forge/nscreen-graph/`.

## Outline

- [What problem are we solving?](#what-problem-are-we-solving)
- [Reading order](#reading-order)
- [High-level workload](#high-level-workload)
- [Set up the shared environment](#set-up-the-shared-environment)
- [Run the examples](#run-the-examples)

## What problem are we solving?

A **UID** identifies a cookie or device. A **matchid** groups UIDs believed to represent one person.

Today, ordinary propagation excludes already-assigned UIDs, even when strong graph evidence connects their different matchids. Multiple matchids claimed for one UID by the same vendor can also survive into final output.

Two separate changes address these gaps. Source normalization selects one provider claim per UID without dropping UIDs. Collocation reconciliation uses IP-collocation, first-party relationships, and device signals to merge supported matchid groups. `samedevice` supports a merge; `differentusers` signals conflict. A false `differentusers` value alone does not establish identity.

## Reading order

1. [Pipeline guide](nscreen-graph-exploration/docs/guides/graph-pipeline.md) — how the current system works.
2. [Provider alignment](nscreen-graph-exploration/docs/analysis/provider-alignment-phase.md) and [toy notebook](nscreen-graph-exploration/provider-alignment-toy.ipynb) — concrete examples and observed results.
3. [Known defects](nscreen-graph-exploration/docs/analysis/provider-alignment-defects.md) and [reduction options](nscreen-graph-exploration/docs/analysis/matchid-reduction-options.md) — limitations and tradeoffs.
4. [Provider multi-assignment plan](nscreen-graph-exploration/docs/plans/provider-source-multi-assignment-plan.md) — retain every UID while selecting one vendor claim.

Further references: [first-party evidence](nscreen-graph-exploration/docs/nscreen-1p-collocation-daily-recap.md), [lookback windows](nscreen-graph-exploration/docs/lookback-windows.md), and [Screen7 clustering](nscreen-graph-exploration/docs/udaf-calc-screen7-ids-evaluator.md).

For production-parity experiments, see the [NScreen replay runner](nscreen-replay/README.md). It reuses Forge SQL from prepared vendor, collocation, and geographic inputs, executes relational stages in Trino, and runs the original Java clustering locally. Outputs use `iceberg.jteixeira_ipa.nscreen2_*`; each run records its own validation results.

Documentation is organized under `nscreen-graph-exploration/docs/` into `guides/`, `analysis/`, and `plans/`. Production `src/...` references in these documents resolve against the separate Forge checkout.

## Set up the shared environment

All Python work uses **one repository-root `.venv`** and [requirements.txt](requirements.txt): apps, notebooks, scripts, and tests. With `uv` installed, run from the repository root:

```bash
# Create once; reuse on subsequent visits.
uv venv .venv --python 3.12

# Install or update dependencies.
uv pip install --python .venv/bin/python -r requirements.txt

# Register the notebook kernel inside this environment.
.venv/bin/python -m ipykernel install --prefix .venv \
  --name nscreen-identity-resolution \
  --display-name "NScreen Identity Resolution (.venv)"
```

Select `<repo>/.venv/bin/python` in your editor and **NScreen Identity Resolution (.venv)** as the notebook kernel. Re-register the kernel if you move the checkout. The explicit interpreter paths below require no environment activation.

## Run the examples

Run each command from the repository root, in a separate terminal:

```bash
# JupyterLab
.venv/bin/python -m jupyterlab

# Provider alignment — port 8504
.venv/bin/python -m streamlit run \
  nscreen-graph-exploration/docs/provider_alignment_app/streamlit_app.py \
  --server.port 8504 --server.address 127.0.0.1

# Screen7 clustering — port 8502
.venv/bin/python -m streamlit run \
  nscreen-graph-exploration/docs/screen7_graph_app/streamlit_app.py \
  --server.port 8502 --server.address 127.0.0.1
```

Both apps use fixed examples and need no warehouse connection. Their READMEs cover scope, tests, and Spark/Java verification: [provider alignment](nscreen-graph-exploration/docs/provider_alignment_app/README.md) · [Screen7](nscreen-graph-exploration/docs/screen7_graph_app/README.md).

**Before executing the notebook:** configure internal `dbfuncs` and Trino access, and select your writable development schema. It recreates `nscreen_toy_*` tables in `iceberg.jteixeira_ipa` by default. Its SQL is adapted and Louvain is simulated; saved outputs can be read without running it.

When contributing findings, include the processing day, query or fixture, and evidence. Keep observed behavior in analysis documents and proposed changes in the plan.

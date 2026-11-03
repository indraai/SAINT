# pySAINT documentation

**pySAINT** is a modern, open re-implementation of **SAINT** (*Systems Analysis of
Integrated Networks of Tasks*), the simulation language Pritsker & Associates built
for the U.S. Air Force Aerospace Medical Research Laboratory in 1974-1978 to study
how people and machines work together.

In SAINT you describe a job as a **network of tasks**. Each task takes some (often
random) time, may need **resources** (operators, equipment), waits for its
**predecessors** to finish, and then **branches** to the next tasks. The simulator
runs the network many times (**iterations**) with different random numbers and
reports statistics: how long things take, how busy each resource is, how often a
path is taken.

## Start here

| If you want to... | Read |
|---|---|
| Install it and see it run (step by step, any OS) | [getting-started.md](getting-started.md) |
| Write or edit a model file | [model-format.md](model-format.md) |
| Call the web API (curl, scripts) | [api.md](api.md) |
| Understand how the code is organised | [architecture.md](architecture.md) |
| See what is coming next | [roadmap.md](roadmap.md) |
| The full design (long, technical) | [SAINT_modern_build_spec.md](SAINT_modern_build_spec.md) |

## What works today (Steps 1 and 2)

- **Model files** in YAML or JSON with tasks, resources, 12 distribution types,
  information/system attributes, statistics and marks.
- **Validator** that finds every problem at once with clear codes (`I401 unknown
  successor task`, ...).
- **Discrete-event engine**: predecessor release counts (first and repeat), waiting
  queue with ranking rules, AND/OR resources, all four branching types
  (deterministic, probabilistic, conditional take-first, conditional take-all),
  attribute assignments, sinks that end an iteration, reproducible seeds.
- **Statistics and reports**: per-task and per-resource summaries with 95%
  confidence intervals, text report, CSV export.
- **Command line**: `saint validate`, `saint run`, `saint serve`.
- **Web API** (FastAPI) with interactive docs at `/docs`.
- **Browser UI**: pick or paste a model, validate, run, see tables, a network
  diagram and download CSVs. No build step, no internet needed.

## Not built yet

Moderator functions, task/resource clearing, network modification, switches and
regulation, continuous state variables and monitors, the legacy 80-column card
deck reader, the interactive graph editor and charts. See [roadmap.md](roadmap.md).

## Glossary

| Term | Meaning |
|---|---|
| Task | A node in the network: something that takes time. |
| Source / sink | Task released at time 0 / task whose completion counts toward ending an iteration. |
| Release (PR1/PR2) | A task starts once enough predecessors completed: `pr1` the first time, `pr2` each time after. |
| Branching | What happens after a task completes: which successors get a completion signal. |
| Resource | Something a task must hold while it runs (one task at a time). |
| Packet / attributes | Data carried from task to task (`IA`, information attributes); `SA` are global system attributes. |
| Iteration | One complete simulated run of the network. |

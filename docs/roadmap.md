# Roadmap

The phases follow §13.1 of the [build spec](SAINT_modern_build_spec.md).

| Step | Status | Contents |
|---|---|---|
| 1 | **done** | Schema, YAML/JSON I/O, validator, discrete engine, stats, text/CSV reports, CLI. |
| 2 | **done** | Web API (FastAPI, `/docs`), `saint serve`, browser UI (validate, run, tables, network diagram, CSV), documentation. |
| 3 | next | **Moderator functions** (MODF: change a task's time or branching based on attributes/state) and **task modification** (DMOD, network modification). |
| 4 | | **Clearing** (TCLR/RCLR: abort tasks, release resources), **switches** (SWIT) and **regulation** (REGL), priority changes (PRTY). |
| 5 | | **Continuous state variables** (SS/DD equations, Runge-Kutta-England integrator), threshold crossings, **monitors** (MONF, MTAS, MSWT, LABL). |
| 6 | | **Legacy card-deck parser**: read original 1978 80-column decks (33 card types) and convert them to YAML (`saint convert`). Needs AMRL-TR-77-61/63 to settle the 20 open questions in spec §13.3. |
| 7 | | **Graph editor** in the browser: drag tasks, draw branches, edit fields, save YAML; charts (histograms, time plots). |
| 8 | | Hardening for v1.0: plugin API for user functions, batch/parameter sweeps, parquet export, performance, hierarchical models, packaging. |

## Known gaps today

- Features listed above are accepted by the schema only where noted; models using
  them cannot run yet.
- The UI shows tables and a diagram, no charts yet; the diagram is read-only.
- The API runs simulations synchronously with no authentication: fine for local
  use, not for a public server.
- Python user functions (`UF`) are available from Python only, not from the web UI.

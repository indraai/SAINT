# Architecture

```
model file (YAML/JSON)
      │  pysaint.io            load_model / loads
      ▼
  Model (pydantic)  ──► pysaint.model.validate ──► InputReport (diagnostics)
      │
      ▼  pysaint.kernel        Simulation(model, seed).run(iterations)
  discrete-event engine  (events, tasks, queue, resources, branching, rng)
      │
      ▼  pysaint.stats         RunResult (pandas tables + summaries)
      │
      ├─► pysaint.report       text report, CSV export
      ├─► pysaint.cli          saint validate | run | serve
      └─► pysaint.api          FastAPI JSON endpoints + static browser UI
```

Everything above the API is plain Python with no web dependency; the API is a thin
layer, and the UI only talks to the API. Any other front end (notebook, desktop
app, the future graph editor, an LLM agent) can use the same Python API or HTTP API.

## Package layout

| Path | Contents | Status |
|---|---|---|
| `pysaint/model/` | `enums.py` (codes), `schema.py` (pydantic model), `validate.py` | Step 1 |
| `pysaint/io/` | `yaml_io.py`, `json_io.py`, `load_model`/`save_model` | Step 1 |
| `pysaint/kernel/` | `engine.py` (event loop, `Simulation`), `events.py`, `tasks.py`, `queue.py`, `resources.py`, `branching.py`, `rng.py` | Step 1 |
| `pysaint/stats/` | collectors, task statistics, `RunResult`/`Summary` | Step 1 |
| `pysaint/report/` | `text.py` (report), `export.py` (CSV) | Step 1 |
| `pysaint/cli.py` | typer command line | Steps 1-2 |
| `pysaint/api/` | `app.py` (FastAPI routes), `service.py` (framework-free helpers), `static/` (UI) | Step 2 |
| `pysaint/continuous/` | state variables, integrator, monitors | placeholder |
| `pysaint/legacy/` | 1978 card-deck parser | placeholder |
| `pysaint/plugins/` | user-function hooks | placeholder |
| `pysaint/ext/` | batch runs, hierarchy, graph editor, LLM helpers | placeholder |
| `tests/unit`, `tests/regression` | pytest; regression = analytic/statistical checks | |
| `examples/yaml` | runnable example models (also served by the API) | |

## How a run works

1. **Load**: YAML/JSON → dict → `Model`. Pydantic checks types and rejects unknown
   fields. Map keys become ids.
2. **Validate**: cross-references (successors, resources, distributions),
   consistency (probabilities, sources, sinks, reachability). All problems are
   collected rather than stopping at the first.
3. **Simulate**: for each iteration, state is reset; sources are released at time 0.
   A released task waits in a ranked queue until its resources are free, starts,
   samples its time, completes, then branches; successors count completions toward
   `pr1`/`pr2`. The iteration ends when `sinks_to_complete` sink completions occur.
4. **Collect**: observations (one row per recorded value), counts, resource busy
   time and per-iteration rows; `RunResult` turns them into summary tables.
5. **Report**: text, CSV, or JSON via `RunResult.to_dict()` (used by the API).

## Web layer (Step 2)

- `service.py` holds parse/validate/run/graph/CSV logic with no FastAPI imports, so
  it is easy to test and reuse.
- `app.py` maps HTTP requests to it, defines request bodies with pydantic (which
  produces the OpenAPI docs) and turns problems into 422/400 responses with a
  `stage` field (`parse`, `validate`, `run`) so a client knows what went wrong.
- `static/index.html`, `app.js`, `style.css`: vanilla JavaScript, no framework,
  build step or CDN; works offline. The network diagram is drawn as inline SVG
  with a simple layered layout (column = breadth-first distance from a source;
  loops drawn as curves underneath).
- `saint serve` runs it with uvicorn. FastAPI/uvicorn are an optional `[web]`
  extra so the core simulator stays light.
- Examples are read from `examples/yaml` in the repo, or `$SAINT_EXAMPLES`.

## Design decisions (from Steps 1-2)

- **Python 3.11+, pydantic v2, numpy, pandas**: readable, typed, fast enough.
- **Modeling separated from analysis**: the model is data; results are tables.
- **Reproducible randomness**: numpy PCG64 with `SeedSequence(seed, iteration)`
  spawned into independent streams (time, branch, assign, user). Any iteration can
  be reproduced alone, and results do not depend on the order iterations run.
- **Statistical, not bit-exact, compatibility** with 1978 SAINT: its random number
  generator was machine-specific, so tests check analytic results (e.g. queue
  utilization) within confidence bounds.
- **Clamping** of distribution samples to `[min, max]`, as SAINT did; normal and
  lognormal default to `min: 0`.
- **Each iteration fully re-initializes state.** Tasks still running when the
  iteration ends are abandoned; their busy time counts toward utilization.
- **Utilization = busy time / iteration end time**; with `OR` resources only the
  one actually seized is counted.
- **Deadlock** (nothing left to happen before enough sinks finish) is an error
  (SAINT code 3010).
- **Diagnostic codes**: pySAINT `I2xx/I4xx/I5xx` for input; original SAINT numbers
  (3001-3604) for execution errors.
- **Web API is stateless**: each request carries the full model text; nothing is
  stored on the server. Simple, safe to restart, easy to script.

## Running the checks

```bash
pytest -q          # all tests
ruff check .       # lint
```

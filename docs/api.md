# Web API

Start the server with `saint serve` (see [getting-started.md](getting-started.md)).
Base URL below: `http://127.0.0.1:8000`. Interactive, try-it-out documentation is
generated automatically at **`/docs`** (Swagger UI) and the machine-readable schema
at `/openapi.json`.

All request and response bodies are JSON. A model is always sent as **text** (the
contents of a YAML or JSON model file) in the field `text`, plus an optional
`format` (`auto` default, `yaml`, `json`).

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/health` | Server is up; version. |
| GET | `/api/examples` | List bundled example models. |
| GET | `/api/examples/{name}` | Source text of one example. |
| POST | `/api/validate` | Parse and validate a model; diagnostics + network graph. |
| POST | `/api/run` | Validate and run; full results. |
| POST | `/api/run/csv?table=...` | Validate and run; one result table as CSV. |
| GET | `/` | The browser UI. |

## Health

```bash
curl http://127.0.0.1:8000/api/health
```

```json
{"status":"ok","version":"0.1.0"}
```

## Examples

```bash
curl http://127.0.0.1:8000/api/examples
curl http://127.0.0.1:8000/api/examples/inspection_network.yaml
```

Returns `[{"name": "...yaml", "description": "first comment line"}, ...]` and
`{"name", "format", "text"}`. Unknown names give 404.

## Validate

The easiest way to send a file is to wrap it in JSON with Python (works on every
OS) and post it:

```bash
python3 -c "import json;print(json.dumps({'text':open('examples/yaml/inspection_network.yaml').read()}))" > req.json
curl -X POST http://127.0.0.1:8000/api/validate -H "Content-Type: application/json" -d @req.json
```

Response (shortened):

```json
{
  "ok": true, "errors": [], "warnings": [], "stage": "validate",
  "model": {"name": "INSPECTION", "iterations": 500, "seed": 71268659},
  "graph": {
    "nodes": [{"id": 1, "label": "RECEIVE", "role": "SO", "resources": []}, ...],
    "edges": [{"from": 4, "to": 6, "type": "PRO", "label": "p=0.8"}, ...]
  }
}
```

Each diagnostic is `{"code", "severity", "message", "location"}`; codes are
listed in [model-format.md](model-format.md#validation-messages). A model with
validation errors still returns **200** with `"ok": false`.

If the text cannot be read at all (bad YAML, unknown field) the status is **422**:

```json
{"detail": {"ok": false, "stage": "parse",
            "message": "model does not match the schema (1 problem(s))",
            "details": [{"location": "tasks.1.bogus", "message": "Extra inputs are not permitted"}]}}
```

## Run

Add `seed` and `iterations` (both optional; defaults come from the model's
`general` section; `iterations` must be 1-100000):

```bash
python3 -c "import json;print(json.dumps({'text':open('examples/yaml/inspection_network.yaml').read(),'seed':1,'iterations':50}))" > run.json
curl -X POST http://127.0.0.1:8000/api/run -H "Content-Type: application/json" -d @run.json
```

Response:

```json
{
  "ok": true,
  "validation": {"ok": true, "errors": [], "warnings": []},
  "graph": {...},
  "result": {
    "model": "INSPECTION", "seed": 1, "iterations": 50,
    "end_time": {"n": 50, "mean": 8.4, "sd": 2.5, "min": 4.9, "max": 17.0},
    "tasks": [{"task": 4, "label": "INSPECT", "stat": "NUM-COM", "n": 50, "mean": 1.3,
               "sd": 0.6, "min": 1, "max": 4, "ci95": 0.17}, ...],
    "resources": [{"resource": 1, "label": "INSPECTR", "n": 50, "mean": 0.29, ...,
                   "busy_time": 2.37, "n_tasks": 1.22}],
    "iterations_table": [{"iteration": 1, "end_time": 7.3, "events": 5, "sinks_done": 1}, ...],
    "warnings": []
  }
}
```

`resources[].mean` is mean utilization (0-1). Errors: **422** with
`"stage": "parse"` or `"stage": "validate"` (the diagnostics are included), **400**
with `"stage": "run"` if the simulation itself fails (e.g. deadlock, code 3010).

## CSV

Same body as `/api/run`; choose the table with `table` = `task_summary` (default),
`resources`, `iterations`, `observations` (every recorded value) or `task_counts`
(releases/starts/completions per iteration).

```bash
curl -X POST "http://127.0.0.1:8000/api/run/csv?table=resources" -H "Content-Type: application/json" -d @run.json -o resources.csv
```

```
resource,label,n,mean,sd,min,max,ci95,busy_time,n_tasks
1,INSPECTR,50,0.285,0.0756,0.152,0.408,0.0210,2.37,1.22
```

## From Python

```python
import json, urllib.request
body = json.dumps({"text": open("examples/yaml/two_operator_queue.yaml").read(),
                   "iterations": 3}).encode()
req = urllib.request.Request("http://127.0.0.1:8000/api/run", body,
                             {"Content-Type": "application/json"})
print(json.load(urllib.request.urlopen(req))["result"]["resources"])
```

Notes: the server has no authentication and runs simulations synchronously, so a
very large run blocks other requests until it finishes. Bind to `127.0.0.1` (the
default) unless you trust your network.

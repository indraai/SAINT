# SAINT

Modern SAINT (Systems Analysis of Integrated Networks of Tasks): `pysaint`, a Python re-implementation of the
combined discrete/continuous man-machine network simulation language developed by Pritsker & Associates
for the USAF Aerospace Medical Research Laboratory (1974-1978).

Status: Steps 1-2 done: YAML/JSON models, validator, discrete-event engine, statistics, reports,
command line, web API and browser UI. See [docs/index.md](docs/index.md).

## Quickstart

```bash
git clone https://github.com/indraai/SAINT.git && cd SAINT
python3 -m venv .venv && source .venv/bin/activate      # Windows: py -m venv .venv; .venv\Scripts\Activate.ps1
pip install -e '.[web,dev]'
saint run examples/yaml/inspection_network.yaml -n 100 -s 1
saint serve        # then open http://127.0.0.1:8000/
```

## Documentation

- [docs/index.md](docs/index.md): what SAINT is, what works, glossary
- [docs/getting-started.md](docs/getting-started.md): install and run, step by step (macOS, Linux, Windows)
- [docs/model-format.md](docs/model-format.md): every field of a model file
- [docs/api.md](docs/api.md): web API with curl examples
- [docs/architecture.md](docs/architecture.md): how the code fits together, design decisions
- [docs/roadmap.md](docs/roadmap.md): what's next
- [docs/SAINT_modern_build_spec.md](docs/SAINT_modern_build_spec.md): full build specification
- Primary source: *The SAINT User's Manual*, AMRL-TR-77-62, June 1978.

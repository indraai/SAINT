# Getting started

This guide assumes nothing beyond a computer with internet access. Every command
here has been run and checked. Commands are shown for **macOS / Linux** (Terminal)
and **Windows** (PowerShell).

## 1. Install Python 3.11 or newer

Check what you have:

```bash
python3 --version        # macOS / Linux
py --version             # Windows
```

If it prints `Python 3.11` or higher, skip ahead. Otherwise:

- **macOS**: install from <https://www.python.org/downloads/> (or `brew install python@3.12`).
- **Linux (Debian/Ubuntu)**: `sudo apt install python3 python3-venv python3-pip`.
- **Windows**: install from <https://www.python.org/downloads/> and tick
  **"Add python.exe to PATH"** in the installer.

You also need **git** (<https://git-scm.com/downloads>), or download the repo as a ZIP
from GitHub and unzip it.

## 2. Get the code

```bash
git clone https://github.com/indraai/SAINT.git
cd SAINT
```

## 3. Create a virtual environment

A virtual environment ("venv") keeps pySAINT's packages separate from the rest of
your system.

macOS / Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Windows (PowerShell):

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
```

If PowerShell refuses to run the script, run
`Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once, then try again.

Your prompt now starts with `(.venv)`. Run the activate command again whenever
you open a new terminal.

## 4. Install pySAINT

```bash
pip install -e '.[web,dev]'
```

(On Windows use double quotes: `pip install -e ".[web,dev]"`.)

- `web` adds the web server (FastAPI, uvicorn).
- `dev` adds the test tools (pytest, ruff).
- `-e` ("editable") means changes you make to the code take effect immediately.

Plain `pip install -e .` installs only the simulator and command line.

## 5. Run the tests

```bash
pytest -q
```

You should see something like `62 passed`. Code style check (optional):

```bash
ruff check .
```

## 6. Use the command line

Check a model for mistakes:

```bash
saint validate examples/yaml/inspection_network.yaml
```

```
examples/yaml/inspection_network.yaml: 0 error(s), 0 warning(s)
```

Run it (100 iterations, seed 1) and print the report:

```bash
saint run examples/yaml/inspection_network.yaml --iterations 100 --seed 1
```

Also write the tables as CSV files into a folder `out/`:

```bash
saint run examples/yaml/inspection_network.yaml -n 100 -s 1 --csv out
```

This creates `out/task_summary.csv`, `out/resources.csv`, `out/observations.csv`
and `out/iterations.csv`, which open in Excel, Numbers or LibreOffice.

Help for any command: `saint --help`, `saint run --help`.

## 7. Start the web interface

```bash
saint serve
```

```
pySAINT UI: http://127.0.0.1:8000/   API docs: http://127.0.0.1:8000/docs
```

Open **<http://127.0.0.1:8000/>** in your browser. Then:

1. Pick an example in **Example** (or paste a model, or **Upload** a `.yaml`/`.json` file).
2. Click **Validate**. Problems appear in red (errors) or yellow (warnings) with
   the location, e.g. `ERROR I401 [tasks[1].branching]: unknown successor task 9`.
   The network diagram is drawn on the right.
3. Optionally set **Seed** and **Iterations** (empty = the values in the model).
4. Click **Run**. Task statistics, resource utilization and per-iteration results
   appear below; the **Download CSV** buttons save each table.

Tip: `http://127.0.0.1:8000/?example=inspection_network.yaml&run=1` loads and runs
an example directly.

Options: `saint serve --port 9000`, or `saint serve --host 0.0.0.0` to allow other
computers on your network to connect (only do this on a trusted network; there is
no login). Stop the server with **Ctrl+C**.

The API itself is documented at <http://127.0.0.1:8000/docs> and in [api.md](api.md).

## 8. Use it from Python

```python
import pysaint as ps

model = ps.load_model("examples/yaml/two_operator_queue.yaml")
print(ps.validate(model).ok)                 # True
result = ps.Simulation(model, seed=1).run(iterations=5)
print(result.task_summary())                 # pandas DataFrame
print(result.utilization(1))                 # Summary(n, mean, sd, min, max)
result.export_csv("out")
```

## Troubleshooting

| Problem | Fix |
|---|---|
| `saint: command not found` | Activate the venv (step 3) in this terminal. |
| `error: the web extra is not installed` | `pip install -e '.[web]'` |
| `address already in use` | Another program uses port 8000: `saint serve --port 8001`. |
| `requires-python >=3.11` during install | Your venv uses an old Python; recreate it with Python 3.11+. |
| Examples list in the UI is empty | Use the editable install (`pip install -e`) from the repo, or set `SAINT_EXAMPLES=/path/to/examples/yaml` before `saint serve`. |

Next: write your own model with [model-format.md](model-format.md).

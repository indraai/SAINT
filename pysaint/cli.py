"""Command line: ``saint validate MODEL``, ``saint run MODEL``, ``saint serve`` (spec §3.2).

``convert``, ``graph`` and ``schema`` arrive with later phases.
"""

from __future__ import annotations

from pathlib import Path

import typer
from ruamel.yaml.error import YAMLError

from .errors import SaintError
from .io import load_model
from .kernel.engine import Simulation
from .model.validate import validate as validate_model
from .report.text import render

app = typer.Typer(add_completion=False, help="pySAINT: modern SAINT task-network simulator.")


def _load(path: Path):
    try:
        return load_model(path)
    except (OSError, ValueError, YAMLError, SaintError) as e:  # ValidationError is a ValueError
        typer.echo(f"error: cannot load {path}: {e}", err=True)
        raise typer.Exit(2)


@app.command()
def validate(model: Path, strict: bool = typer.Option(False, help="Warnings fail too.")) -> None:
    """Validate a model file and print diagnostics."""
    rep = validate_model(_load(model))
    for d in rep.diagnostics:
        typer.echo(str(d))
    bad = rep.diagnostics if strict else rep.errors
    typer.echo(f"{model}: {len(rep.errors)} error(s), {len(rep.warnings)} warning(s)")
    raise typer.Exit(1 if bad else 0)


@app.command()
def run(
    model: Path,
    iterations: int | None = typer.Option(None, "--iterations", "-n", min=1),
    seed: int | None = typer.Option(None, "--seed", "-s"),
    csv: Path | None = typer.Option(None, "--csv", help="Write CSV tables (file or dir)."),
) -> None:
    """Run a model and print the text report."""
    m = _load(model)
    rep = validate_model(m)
    if not rep.ok:
        for d in rep.diagnostics:
            typer.echo(str(d), err=True)
        raise typer.Exit(1)
    try:
        res = Simulation(m, seed=seed, validate=False).run(iterations)
    except SaintError as e:
        typer.echo(f"execution error: {e}", err=True)
        raise typer.Exit(3)
    typer.echo(render(res))
    if csv is not None:
        for f in res.export_csv(str(csv)):
            typer.echo(f"wrote {f}")


@app.command()
def serve(
    host: str = typer.Option("127.0.0.1", help="Interface to bind (0.0.0.0 = all)."),
    port: int = typer.Option(8000, help="TCP port."),
    reload: bool = typer.Option(False, help="Auto-reload on code changes (development)."),
) -> None:
    """Start the web API and browser UI (needs the 'web' extra installed)."""
    try:
        import uvicorn
    except ImportError:
        typer.echo("error: the web extra is not installed; run: pip install -e '.[web]'",
                   err=True)
        raise typer.Exit(2)
    typer.echo(f"pySAINT UI: http://{host}:{port}/   API docs: http://{host}:{port}/docs")
    uvicorn.run("pysaint.api:create_app", factory=True, host=host, port=port, reload=reload)


def main() -> None:
    app()


if __name__ == "__main__":
    main()

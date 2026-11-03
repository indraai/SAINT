"""Command line: ``saint validate MODEL`` and ``saint run MODEL`` (spec §3.2).

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


def main() -> None:
    app()


if __name__ == "__main__":
    main()

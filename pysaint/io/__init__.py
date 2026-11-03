"""Model I/O: ``load_model(path)`` dispatches on suffix (.yaml/.yml/.json)."""

from __future__ import annotations

from pathlib import Path

from ..errors import SaintInputError
from ..model.schema import Model
from . import json_io, yaml_io


def load_model(path: str | Path) -> Model:
    p = Path(path)
    suffix = p.suffix.lower()
    if suffix in (".yaml", ".yml"):
        return yaml_io.load(p)
    if suffix == ".json":
        return json_io.load(p)
    raise SaintInputError(f"unsupported model format '{suffix}' (legacy decks: later phase)")


def save_model(model: Model, path: str | Path) -> None:
    p = Path(path)
    (json_io if p.suffix.lower() == ".json" else yaml_io).dump(model, p)


__all__ = ["json_io", "load_model", "save_model", "yaml_io"]

"""JSON load/dump for the modern model format (spec §5.4)."""

from __future__ import annotations

import json
from pathlib import Path

from ..model.schema import Model


def loads(text: str) -> Model:
    return Model.model_validate_json(text)


def load(path: str | Path) -> Model:
    return loads(Path(path).read_text())


def dumps(model: Model, indent: int = 2) -> str:
    return json.dumps(model.model_dump(mode="json", exclude_none=True), indent=indent)


def dump(model: Model, path: str | Path) -> None:
    Path(path).write_text(dumps(model))

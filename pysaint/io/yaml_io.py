"""YAML load/dump for the modern model format (spec §5.4)."""

from __future__ import annotations

import io
from pathlib import Path
from typing import Any

from ruamel.yaml import YAML

from ..model.schema import Model


def _yaml() -> YAML:
    y = YAML(typ="safe", pure=True)
    y.default_flow_style = False
    return y


def loads(text: str) -> Model:
    data: Any = _yaml().load(text)
    return Model.model_validate(data or {})


def load(path: str | Path) -> Model:
    return loads(Path(path).read_text())


def dumps(model: Model) -> str:
    buf = io.StringIO()
    _yaml().dump(model.model_dump(mode="json", exclude_none=True), buf)
    return buf.getvalue()


def dump(model: Model, path: str | Path) -> None:
    Path(path).write_text(dumps(model))

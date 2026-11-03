"""FastAPI application (spec §3.2 ``ext/web``; Step 2).

Endpoints (all JSON unless noted; OpenAPI docs at ``/docs``):

GET  /api/health                 liveness + version
GET  /api/examples               bundled example models
GET  /api/examples/{name}        one example's source text
POST /api/validate               parse + validate a model -> InputReport + graph
POST /api/run                    validate + run -> RunResult
POST /api/run/csv?table=...      validate + run -> one CSV table (text/csv)
GET  /                           browser UI (static files)
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .. import __version__
from ..errors import SaintError
from ..model.validate import validate as validate_model
from . import service as svc

STATIC = Path(__file__).parent / "static"


class ModelText(BaseModel):
    text: str = Field(..., description="Model source (YAML or JSON).")
    format: svc.Format = Field("auto", description="auto | yaml | json")


class RunRequest(ModelText):
    seed: int | None = Field(None, description="Base seed; default = general.seed.")
    iterations: int | None = Field(None, ge=1, le=svc.MAX_ITERATIONS,
                                   description="Default = general.iterations.")


def _parse(req: ModelText):
    try:
        return svc.parse(req.text, req.format)
    except svc.ParseFailure as e:
        raise HTTPException(422, {"ok": False, "stage": "parse", "message": e.message,
                                  "details": e.details}) from e


def _validated_run(req: RunRequest):
    model = _parse(req)
    rep = validate_model(model)
    if not rep.ok:
        raise HTTPException(422, {"ok": False, "stage": "validate", **svc.report_dict(rep)})
    try:
        return model, rep, svc.run(model, req.seed, req.iterations)
    except (SaintError, ValueError) as e:
        raise HTTPException(400, {"ok": False, "stage": "run", "message": str(e)}) from e


def create_app() -> FastAPI:
    app = FastAPI(title="pySAINT", version=__version__,
                  description="Modern SAINT task-network simulator API.")

    @app.get("/api/health")
    def health() -> dict[str, Any]:
        return {"status": "ok", "version": __version__}

    @app.get("/api/examples")
    def examples() -> list[dict[str, str]]:
        return svc.list_examples()

    @app.get("/api/examples/{name}")
    def example(name: str) -> dict[str, str]:
        text = svc.read_example(name)
        if text is None:
            raise HTTPException(404, f"no example named {name!r}")
        return {"name": name, "format": "json" if name.endswith(".json") else "yaml",
                "text": text}

    @app.post("/api/validate")
    def validate(req: ModelText) -> dict[str, Any]:
        model = _parse(req)
        return {**svc.report_dict(validate_model(model)), "stage": "validate",
                "model": {"name": model.general.name,
                          "iterations": model.general.iterations,
                          "seed": model.general.seed},
                "graph": svc.graph(model)}

    @app.post("/api/run")
    def run(req: RunRequest) -> dict[str, Any]:
        model, rep, res = _validated_run(req)
        return {"ok": True, "validation": svc.report_dict(rep), "graph": svc.graph(model),
                "result": svc.result_dict(res)}

    @app.post("/api/run/csv", response_class=PlainTextResponse)
    def run_csv(req: RunRequest,
                table: Literal["task_summary", "resources", "observations", "iterations",
                               "task_counts"] = Query("task_summary")):
        if table not in svc.CSV_TABLES:
            raise HTTPException(400, f"table must be one of {svc.CSV_TABLES}")
        _, _, res = _validated_run(req)
        return PlainTextResponse(
            svc.table_csv(res, table), media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{table}.csv"'})

    @app.get("/", include_in_schema=False)
    def index() -> FileResponse:
        return FileResponse(STATIC / "index.html")

    app.mount("/static", StaticFiles(directory=STATIC), name="static")
    return app

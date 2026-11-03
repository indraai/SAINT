"""Web API tests (Step 2)."""

from __future__ import annotations

import json

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from pysaint.api import create_app
from pysaint.api import service as svc

GOOD = """
general: {name: TINY, iterations: 5}
resources: {1: {label: OP}}
tasks:
  1: {label: A, role: source, time: 2, resources: {ids: [1]}, branching: {successors: [2]}}
  2: {label: B, role: sink, time: 3, stat: {type: INT, at: COM}}
"""


@pytest.fixture(scope="module")
def client():
    return TestClient(create_app())


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200 and r.json()["status"] == "ok"


def test_examples_list_and_get(client):
    names = [e["name"] for e in client.get("/api/examples").json()]
    assert "inspection_network.yaml" in names
    r = client.get("/api/examples/inspection_network.yaml")
    assert r.status_code == 200 and "INSPECT" in r.json()["text"]
    assert client.get("/api/examples/nope.yaml").status_code == 404
    assert client.get("/api/examples/..%2Fpyproject.toml").status_code == 404


def test_validate_ok_and_graph(client):
    d = client.post("/api/validate", json={"text": GOOD}).json()
    assert d["ok"] and d["errors"] == []
    assert {n["id"] for n in d["graph"]["nodes"]} == {1, 2}
    assert d["graph"]["edges"] == [{"from": 1, "to": 2, "type": "DET", "label": ""}]


def test_validate_reports_errors(client):
    bad = GOOD.replace("successors: [2]", "successors: [9]")
    d = client.post("/api/validate", json={"text": bad}).json()
    assert not d["ok"] and any(e["code"] == "I401" for e in d["errors"])


def test_parse_errors_are_422(client):
    r = client.post("/api/validate", json={"text": "tasks: [unclosed"})
    assert r.status_code == 422 and r.json()["detail"]["stage"] == "parse"
    r = client.post("/api/validate", json={"text": "tasks: {1: {bogus: 1}}"})
    assert r.status_code == 422 and r.json()["detail"]["details"]


def test_json_input(client):
    from pysaint.io import json_io, yaml_io
    text = json_io.dumps(yaml_io.loads(GOOD))
    assert client.post("/api/validate", json={"text": text, "format": "json"}).json()["ok"]


def test_run_deterministic(client):
    d = client.post("/api/run", json={"text": GOOD, "seed": 7, "iterations": 3}).json()
    res = d["result"]
    assert res["iterations"] == 3 and res["seed"] == 7
    assert len(res["iterations_table"]) == 3
    assert res["end_time"]["mean"] == pytest.approx(5.0)
    assert res["resources"][0]["mean"] == pytest.approx(0.4)
    json.dumps(d)  # fully serialisable


def test_run_is_reproducible(client):
    text = client.get("/api/examples/inspection_network.yaml").json()["text"]
    a = client.post("/api/run", json={"text": text, "seed": 1, "iterations": 20}).json()
    b = client.post("/api/run", json={"text": text, "seed": 1, "iterations": 20}).json()
    assert a["result"]["tasks"] == b["result"]["tasks"]


def test_run_invalid_model_422(client):
    bad = GOOD.replace("successors: [2]", "successors: [9]")
    r = client.post("/api/run", json={"text": bad})
    assert r.status_code == 422 and r.json()["detail"]["stage"] == "validate"


def test_run_iterations_bounds(client):
    assert client.post("/api/run", json={"text": GOOD, "iterations": 0}).status_code == 422


@pytest.mark.parametrize("table", svc.CSV_TABLES)
def test_csv(client, table):
    r = client.post(f"/api/run/csv?table={table}", json={"text": GOOD, "iterations": 2})
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/csv")
    assert r.text.count("\n") >= 2


def test_csv_bad_table(client):
    r = client.post("/api/run/csv?table=zzz", json={"text": GOOD})
    assert r.status_code in (400, 422)


def test_ui_and_docs(client):
    r = client.get("/")
    assert r.status_code == 200 and "pySAINT" in r.text
    assert client.get("/static/app.js").status_code == 200
    assert client.get("/docs").status_code == 200
    assert "/api/run" in client.get("/openapi.json").json()["paths"]

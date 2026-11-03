import pandas as pd
from typer.testing import CliRunner

from pysaint.cli import app

runner = CliRunner()


def test_validate_cli(examples, tmp_path):
    r = runner.invoke(app, ["validate", str(examples / "inspection_network.yaml")])
    assert r.exit_code == 0, r.output
    bad = tmp_path / "bad.yaml"
    bad.write_text("tasks:\n  1: {role: source, branching: {successors: [9]}}\n")
    r = runner.invoke(app, ["validate", str(bad)])
    assert r.exit_code == 1 and "I401" in r.output


def test_run_cli_csv(examples, tmp_path):
    out = tmp_path / "res.csv"
    r = runner.invoke(app, ["run", str(examples / "inspection_network.yaml"),
                            "--iterations", "20", "--seed", "3", "--csv", str(out)])
    assert r.exit_code == 0, r.output
    assert "TASK STATISTICS" in r.output and "RESOURCE UTILIZATION" in r.output
    df = pd.read_csv(out)
    assert {"task", "stat", "n", "mean", "sd", "min", "max"} <= set(df.columns)
    assert (tmp_path / "res_resources.csv").exists()

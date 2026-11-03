"""pySAINT: modern SAINT (Systems Analysis of Integrated Networks of Tasks).

Public API (stable from Step 1)::

    import pysaint as ps
    model = ps.load_model("model.yaml")
    report = ps.validate(model)          # InputReport (.ok, .errors, .warnings)
    result = ps.Simulation(model, seed=1).run(iterations=100)   # -> RunResult
    result.task_summary(); result.resource_summary(); result.export_csv("out.csv")
"""

from .io import load_model, save_model
from .kernel.engine import Context, Simulation, run
from .model.schema import Model, Task
from .model.validate import validate
from .stats.summary import RunResult, Summary

__version__ = "0.1.0"

__all__ = [
           "Context",
           "Model",
           "RunResult",
           "Simulation",
           "Summary",
           "Task",
           "__version__",
           "load_model",
           "run",
           "save_model",
           "validate",
]

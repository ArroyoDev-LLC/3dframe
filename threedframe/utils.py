# -*- coding: utf-8 -*-

"""Model Generator Utils."""
import subprocess as sp
from dataclasses import dataclass
from pathlib import Path

from euclid3 import Point3
from rich.console import RenderableType
from rich.progress import ProgressColumn, SpinnerColumn, Task, TextColumn
from rich.text import Text


class ComputeTestResultsColumn(ProgressColumn):
    """Renders test results with ascii characters."""

    def render(self, task: "Task") -> RenderableType:
        """Show compute test results."""
        results = task.fields.get("results", None)
        if not results:
            return Text.from_markup("")
        output = " ".join(["[bold green]✔[/]" if i else "[bold red]𐄂[/]" for i in results])
        return Text.from_markup(output)


class ComputeTestResultsTextColumn(ProgressColumn):
    def render(self, task: "Task") -> RenderableType:
        results = task.fields.get("results", None)
        if not results:
            return Text.from_markup("")
        output = f"[bold white]Testing point: [gold1]{task.fields['ran_point']}[/gold1] [bold white]@ [bold cyan]{task.fields['current_boundary']}[white] boundary."
        return Text.from_markup(output)


class ParentProgressColumn(TextColumn):
    """Renders test results with ascii characters."""

    def render(self, task: "Task") -> RenderableType:
        """Show compute test results."""
        results = task.fields.get("results", None)
        if not results:
            return super().render(task)
        return Text.from_markup("")


class ParentSpinnerColumn(SpinnerColumn):
    def render(self, task: "Task") -> Text:
        results = task.fields.get("results", None)
        if not results:
            return super().render(task)
        return Text.from_markup("")


@dataclass
class ModelInfo:
    num_vertices: int
    num_edges: int


def round_point(point: Point3, n_digits=2):
    """Round a given 3d point."""
    p = point.copy()
    p.x = round(p.x, n_digits)
    p.y = round(p.y, n_digits)
    p.z = round(p.z, n_digits)
    return p.z


def openscad_cmd(*args) -> sp.Popen:
    """Execute openscad command."""
    _cmd = ["/usr/bin/openscad"]
    _cmd.extend(args)
    return sp.Popen(_cmd, stdout=sp.PIPE, stderr=sp.PIPE)


def exec_blender_script(model_path: Path, script_path: Path, out_path: Path):
    """Execute blender command."""
    _cmd = [
        "/usr/bin/blender",
        str(model_path.absolute()),
        "--background",
        "--python-use-system-env",
        "--python",
        str(script_path.absolute()),
    ]
    _cmd_env = dict(
        THREEDFRAME_OUT=str(out_path.absolute()), PYTHONPATH=str(Path(__file__).parent.parent)
    )
    return sp.run(_cmd, check=True, env=_cmd_env)

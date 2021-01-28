# -*- coding: utf-8 -*-

"""Model Generator Utils."""
import subprocess as sp

from euclid3 import Point3
from rich.progress import ProgressColumn, Task
from rich.text import Text


class ComputeTestResultsColumn(ProgressColumn):
    """Renders test results with ascii characters."""

    def render(self, task: "Task") -> Text:
        """Show compute test results."""
        results = task.fields.get("results", [])
        output = " ".join(["[bold green]✔[/]" if i else "[bold red]𐄂[/]" for i in results])
        return Text.from_markup(output)


def round_point(point: Point3, n_digits=2):
    p = point.copy()
    p.x = round(p.x, n_digits)
    p.y = round(p.y, n_digits)
    p.z = round(p.z, n_digits)
    return p.z


def openscad_cmd(*args):
    _cmd = ["/usr/bin/openscad"]
    _cmd.extend(args)
    return sp.run(_cmd, check=True)

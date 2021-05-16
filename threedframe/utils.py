# -*- coding: utf-8 -*-

"""3DFrame Model Generator Utils."""
import sys
import time
import subprocess as sp
from typing import List, Tuple, Union, Callable, Sequence
from pathlib import Path
from tempfile import TemporaryDirectory

import sh
import numpy as np
import sympy as S
from rich import print
from solid import OpenSCADObject, text, union, resize, translate, scad_render, linear_extrude
from euclid3 import Point3
from rich.text import Text
from rich.console import RenderableType
from rich.progress import Task, TextColumn, SpinnerColumn, ProgressColumn
from watchdog.events import PatternMatchingEventHandler
from watchdog.observers import Observer


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
    blender_loc = sh.which("blender")
    _cmd = [
        blender_loc,
        str(model_path.absolute()),
        "--background",
        "--python-use-system-env",
        "--python",
        str(script_path.absolute()),
    ]
    py_path = ":".join(sys.path)
    _cmd_env = dict(
        THREEDFRAME_OUT=str(out_path.absolute()),
        PYTHONPATH=py_path,
        BLENDER_SYSTEM_PYTHON=sys.executable,
    )
    print(_cmd_env)
    print(sys.path)
    return sp.run(_cmd, check=True, env=_cmd_env)


def write_scad(element: OpenSCADObject, path: Path, segments=48):
    out_render = scad_render(element, file_header=f"$fn = {segments};")
    path.write_text(out_render)
    return out_render


class TemporaryScadWorkspace(TemporaryDirectory):
    def __init__(
        self, *args, scad_objs: List[Tuple[str, OpenSCADObject, Union[str, None]]], **kwargs
    ):
        super().__init__(*args, **kwargs)
        self.scad_objs = scad_objs
        self.path: Path = Path(self.name)
        self.proc = None

    def _stream_proc(self, proc: sp.Popen):
        for line in iter(proc.stderr.readline, b""):
            outline = line.decode().rstrip("\n")
            print(f"[grey42]{outline}")

    def __enter__(self) -> Tuple[Path, List[Tuple[str, Path, Union[Path, None]]]]:
        files = []
        for name, obj, mesh_format in self.scad_objs:
            obj_path = (self.path / name).with_suffix(".scad")
            render_path = None
            write_scad(obj, obj_path)
            if mesh_format:
                render_path = obj_path.with_suffix(f".{mesh_format}")
                self.proc = openscad_cmd("-o", str(render_path), str(obj_path))
                self._stream_proc(self.proc)
            files.append((name, obj_path, render_path))
        return self.path, files


# Fixed version of label size.
def label_size(
    a_str: str,
    width: float = 15,
    halign: str = "left",
    valign: str = "baseline",
    size: int = 10,
    depth: float = 0.5,
    lineSpacing: float = 1.4,
    font: str = "Impact:style=Bold",
    segments: int = 48,
    spacing: int = 1.2,
    direction: str = "ltr",
    center: bool = False,
    do_resize=True,
) -> Tuple[OpenSCADObject, Tuple[float, float, float]]:
    """Renders a multi-line string into a single 3D object.

    __author__    = 'NerdFever.com'
    __copyright__ = 'Copyright 2018-2019 NerdFever.com'
    __version__   = ''
    __email__     = 'dave@nerdfever.com'
    __status__    = 'Development'
    __license__   = Copyright 2018-2019 NerdFever.com

    """

    lines = a_str.splitlines()

    texts = []

    for idx, l in enumerate(lines):
        t = text(
            text=l,
            halign=halign,
            valign=valign,
            font=font,
            spacing=spacing,
            size=size,
            direction=direction,
        ).add_param("$fn", segments)
        t = linear_extrude(height=depth, center=center)(t)
        tvals = (0, -size * idx * lineSpacing, 0)
        if any(tvals):
            t = translate(tvals)(t)
        texts.append(t)

    if len(texts) > 1:
        result = union()(texts)
    else:
        result = texts[0]
    resize_vals = (
        width,
        0,
        depth,
    )
    if do_resize:
        result = resize(resize_vals)(result)
    restvals = (0, (len(lines) - 1) * size / 2, 0)
    if any(restvals):
        result = translate(restvals)(result)
    return result, resize_vals


class FileModifiedPatternEvent(PatternMatchingEventHandler):
    def __init__(self, glob_pattern: str, on_modify: Callable):
        super().__init__(patterns=glob_pattern)
        self._on_modified = on_modify

    def on_modified(self, event):
        print(event)
        self._on_modified()


class FileModifiedWatcher:
    def __init__(self, on_modify: Callable):
        self.src_path = Path(__file__).parent
        self.event_handler = FileModifiedPatternEvent("*.py", on_modify)
        self.event_observer = Observer()

    def start(self):
        self.schedule()
        self.event_observer.start()

    def stop(self):
        self.event_observer.stop()
        self.event_observer.join()

    def schedule(self):
        self.event_observer.schedule(self.event_handler, str(self.src_path), recursive=True)

    def run(self):
        self.start()
        try:
            while True:
                print("Watching for file changes...")
                time.sleep(30)
        except KeyboardInterrupt:
            self.stop()


def find_missing_rect_vertex(pa: S.Point3D, pb: S.Point3D, pc: S.Point3D) -> S.Point3D:
    """Given 3 3d points of a rectangle, find a return the fourth missing
    vertex."""
    x, y, z = S.symbols("x y z")
    expr = x + y - z
    pd_pts = []
    for attr in (
        "x",
        "y",
        "z",
    ):
        attr_pt = expr.subs(
            [(x, getattr(pa, attr)), (y, getattr(pc, attr)), (z, getattr(pb, attr))]
        )
        pd_pts.append(attr_pt)
    return S.Point3D(*pd_pts)


def find_center_of_gravity(*points: Sequence[S.Point3D]) -> S.Point3D:
    """Find the barycenter of X num of points."""
    pts_range = len(points)
    x_coord = sum([p.x for p in points]) / pts_range
    y_coord = sum([p.y for p in points]) / pts_range
    z_coord = sum([p.z for p in points]) / pts_range
    return S.Point3D(x_coord, y_coord, z_coord)


def rand_rgb_color() -> List[int]:
    """Generate random RGB color."""
    return list(np.random.random(size=3) * 256)

# -*- coding: utf-8 -*-

"""3DFrame Model Generator Utils."""
import sys
import time
import string
import subprocess as sp
from typing import Dict, List, Tuple, Union, Callable, Iterator, Sequence
from pathlib import Path
from tempfile import TemporaryDirectory
from dataclasses import field, dataclass

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


def label_generator() -> Iterator[str]:
    """Generates labels for vertices.

    Yields: 'AA', 'AB', 'AC'...'ZW', 'ZY', 'ZZ'

    """
    base_charmap = iter(string.ascii_uppercase)
    _label_charmap = iter(string.ascii_uppercase)
    _base_label = None
    while True:
        if not _base_label:
            _base_label = next(base_charmap)
        try:
            label = next(_label_charmap)
        except StopIteration:
            try:
                _base_label = next(base_charmap)
            except StopIteration:
                break
            _label_charmap = iter(string.ascii_uppercase)
            label = next(_label_charmap)
        yield f"{_base_label}{label}"


MODEL_LABELS = label_generator()


@dataclass
class ModelData:
    """Computed model info."""

    # Total number of vertices in model.
    num_vertices: int
    # Total number of edges in model.
    num_edges: int
    # Vertices.
    vertices: Dict[int, "ModelVertex"]

    def get_edge_target_vertex(self, edge: "ModelEdge") -> "ModelVertex":
        """Retrieve an edges target vertex."""
        vertex = self.vertices[edge.target_vidx]
        return vertex


@dataclass
class ModelEdge:
    """Computed edge info."""

    # Edge index.
    eidx: int
    # Edge length.
    length: float
    # Joint vertex index.
    joint_vidx: int
    # Target vertex index.
    target_vidx: int
    # Vector FROM target vertex into joint.
    vector_ingress: Tuple[float, float, float]

    @property
    def length_in(self) -> float:
        """Length in inches."""
        return self.length / 25.4


@dataclass
class ModelVertex:
    """Computed Vertex info."""

    # Vertex index.
    vidx: int
    # Edge map.
    edges: List[ModelEdge]
    # Generated label for vertex.
    label: str = field(default_factory=lambda: next(MODEL_LABELS))


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
    py_path = ":".join(sys.path)
    _cmd_env = dict(
        THREEDFRAME_OUT=str(out_path.absolute()),
        PYTHONPATH=py_path,
        BLENDER_SYSTEM_PYTHON=sys.executable,
    )
    print(_cmd_env)
    print(sys.path)
    return sp.run(_cmd, check=True, env=_cmd_env)


# Fixed version of label size.
def label_size(
    a_str: str,
    width: float = 15,
    halign: str = "left",
    valign: str = "baseline",
    size: int = 10,
    depth: float = 0.5,
    lineSpacing: float = 1.15,
    font: str = "MgOpen Modata:style=Bold",
    segments: int = 40,
    spacing: int = 1,
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



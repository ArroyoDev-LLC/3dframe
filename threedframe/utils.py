# -*- coding: utf-8 -*-

"""3DFrame Model Generator Utils."""
import sys
import json
import time
import string
import itertools
import subprocess as sp
from typing import Dict, List, Tuple, Union, Callable, Iterator, Optional, Sequence
from pathlib import Path
from tempfile import TemporaryDirectory
from dataclasses import field, dataclass

import numpy as np
import sympy as S
from rich import print
from solid import OpenSCADObject, text, union, resize, translate, scad_render, linear_extrude
from euclid3 import Point3, Vector3
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


@dataclass
class MeshPoint:
    """Mesh Point."""

    # Vertex Index.
    vidx: int
    # 3D Coordinate of point.
    point: Tuple[float, float, float]
    # Point normal.
    normal: Optional[Tuple[float, float, float]]
    # Parent Mesh Data.
    _parent: Optional["MeshData"] = field(repr=False, hash=False, default=None)

    @property
    def faces(self) -> List["MeshFace"]:
        return [f for f in self._parent.faces if self.vidx in f.vertex_indices]

    @property
    def as_euclid(self) -> Point3:
        return Point3(*self.point)

    @property
    def as_sympy(self) -> S.Point3D:
        return S.Point3D(*self.point)

    @property
    def as_vector(self) -> Vector3:
        return Vector3(*self.point)

    @property
    def normal_vector(self) -> Vector3:
        return Vector3(*self.normal)


@dataclass
class MeshFace:
    """Mesh Face."""

    # Face Index.
    fidx: int
    # Vertices that makeup face.
    vertex_indices: List[int]
    # Face normal.
    normal: Optional[Tuple[float, float, float]]
    # Face area.
    area: float
    # Vector representing face centroids.
    centroid: Optional[Tuple[float, float, float]]
    # Parent Mesh Data.
    _parent: Optional["MeshData"] = field(repr=False, hash=False, default=None)

    @property
    def vertices(self) -> List[MeshPoint]:
        return [v for v in self._parent.vertices if v.vidx in self.vertex_indices]

    @property
    def sympy_vertices(self) -> List[S.Point3D]:
        return [p.as_sympy for p in self.vertices]

    @property
    def euclid_vertices(self) -> List[Point3]:
        return [p.as_euclid for p in self.vertices]

    @property
    def as_sympy_plane(self) -> S.Plane:
        return S.Plane(*self.sympy_vertices, normal_vector=self.normal)

    @property
    def missing_rect_vertex(self) -> S.Point3D:
        points_perms = itertools.permutations(self.sympy_vertices, 3)
        least_dist = None
        least_dist_point = None
        for perm in points_perms:
            midp = find_missing_rect_vertex(*perm)
            dist = self.centroid_point.distance(midp)
            if least_dist is None or least_dist > dist:
                least_dist = dist
                least_dist_point = midp
        return least_dist_point

    @property
    def midpoint_by_canberra(self) -> S.Point3D:
        fp_1 = self.vertices[0].as_sympy
        fp_2 = max(self.sympy_vertices, key=lambda p: fp_1.canberra_distance(p))
        return fp_1.midpoint(fp_2)

    @property
    def normal_vector(self) -> Vector3:
        return Vector3(*self.normal)

    @property
    def centroid_point(self) -> S.Point3D:
        return S.Point3D(*self.centroid)

    # def calc_absolute_midpoint(self):
    #     return find_center_of_gravity(*self.sympy_vertices)


@dataclass
class MeshData:
    """Mesh Analysis Data."""

    # Vertices of mesh.
    vertices: List[MeshPoint]
    # Faces of mesh.
    faces: List[MeshFace]

    def __post_init__(self):
        for vert in self.vertices:
            vert._parent = self
        for face in self.faces:
            face._parent = self

    @classmethod
    def from_dict(cls, data):
        vertices = data.get("vertices", [])
        faces = data.get("faces", [])
        verts = [MeshPoint(**v) for v in vertices]
        fces = [MeshFace(**f) for f in faces]
        return cls(vertices=verts, faces=fces)

    def calc_absolute_midpoint(self):
        face_mps = []
        for face in self.faces:
            face_mps.append(find_center_of_gravity(*face.sympy_vertices, face.missing_rect_vertex))
        return find_center_of_gravity(*face_mps)


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


def exec_pymesh(*args, host_mount: Path):
    pkg_root = Path(__file__).parent
    _pkg_mount = [str(pkg_root.absolute()), "/script"]
    _vol_mount = [str(host_mount.absolute()), "/models"]
    _cmd = [
        "/usr/bin/docker",
        "run",
        "-it",
        "--rm",
        "-v",
        ":".join(_vol_mount),
        "-v",
        ":".join(_pkg_mount),
        "pymesh/pymesh",
        "python3",
        "/script/mesh.py",
    ]
    _cmd.extend(args)
    return sp.run(_cmd, check=True)


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


def analyze_scad(obj: OpenSCADObject) -> MeshData:
    scad_obj = [("target", union()(obj), "stl")]
    data = None
    with TemporaryScadWorkspace(scad_objs=scad_obj) as tmpdata:
        tmp_path, tmp_files = tmpdata
        exec_pymesh("analyze", tmp_files[0][-1].name, "out.json", host_mount=tmp_path)
        data = json.loads((tmp_path / "out.json").read_text())
    return MeshData.from_dict(data)


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

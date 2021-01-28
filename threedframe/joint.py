# -*- coding: utf-8 -*-

"""3DFrame joint module."""

import math
import pickle
import random
import shutil
import statistics
import tempfile
from os import PathLike

from euclid3 import Sphere
from rich import print, progress
from solid import *
from solid.utils import *

from threedframe import utils
from threedframe.utils import label_size

ROOT = Path(__file__).parent

MODEL_DATA_PATH = None
MODEL_DATA: Optional[Dict[int, List[Tuple[int, float, Tuple[float, float, float]]]]] = None

LIB_DIR = ROOT / "lib"
MCAD = LIB_DIR / "MCAD"

TAU = 6.2831853071  # 2*PI
deg = lambda x: 360 * x / TAU

mcad = import_scad(str(Path(ROOT / "lib/MCAD")))

MM = 1
INCH = 25.4 * MM

inch = lambda x: x * INCH

SEGMENTS = 48

CORE_SIZE = inch(1.4)

# Global Params
GAP = 0.02  # fudge factor

# Fixture Params
SUPPORT_SIZE = inch(0.69)  # size of wooden support
FIXTURE_WALL_THICKNESS = 6  # thickness of support fixture wall
FIXTURE_HOLE_SIZE = SUPPORT_SIZE + GAP
FIXTURE_SIZE = FIXTURE_HOLE_SIZE + FIXTURE_WALL_THICKNESS

FIXTURE_ANGLE_FUDGE = 6.3  # Fudge value for fixture angles length.


def assemble_core(
    vidx: int,
    fixture_points: List[Point3],
    debug=False,
    progress: Optional[progress.Progress] = None,
):
    union()
    prog = progress
    core_radius = CORE_SIZE / 2
    core = sphere(core_radius)

    # Here, we use the fixture reference points
    # to calculate a safe area (one that isn't covered by a fixture)
    # to place our vertex label.

    # reference sphere for calculations
    sphere_obj = Sphere(Point3(*ORIGIN), radius=CORE_SIZE)

    # Create a line segment from the fixture points
    # reaching back to origin.
    # Adds the point of contact of the line on the core to the array below.
    points_on_core = []
    for point in fixture_points:
        sphere_at_point = Sphere(point, FIXTURE_SIZE)
        line_to_origin_sphere: LineSegment3 = sphere_at_point.connect(sphere_obj)
        print(line_to_origin_sphere, line_to_origin_sphere.p2)
        points_on_core.append(line_to_origin_sphere.p2)

    # Determine mean/stdev for Guassian distribution.
    points_dataset = list(frange(-core_radius, core_radius))
    points_mean = statistics.mean(points_dataset)
    points_stdev = statistics.stdev(points_dataset)
    points_gauss = lambda: random.gauss(points_mean, points_stdev)

    # Generate "random" XYZ coords using Guassian distribution for uniformity
    # on the surface of the spherical core.
    attempted_points = []
    fixture_boundary = reversed(range(10, 21))
    current_boundary = next(fixture_boundary)
    task = None
    while True:
        ran_x = points_gauss()
        ran_y = points_gauss()
        ran_z = points_gauss()
        norm = 1 / math.sqrt(math.pow(ran_x, 2) + math.pow(ran_y, 2) + math.pow(ran_z, 2))
        ran_x *= norm
        ran_y *= norm
        ran_z *= norm
        # Subtract 4 to make the point 4mm inside the core,
        # so it will later extruded outwards with the correct orientation.
        ran_x *= core_radius - 4
        ran_y *= core_radius - 4
        ran_z *= core_radius - 4
        _point = (ran_x, ran_y, ran_z)
        ran_point = Point3(*_point)
        roun_point = utils.round_point(ran_point, n_digits=6)
        if roun_point in attempted_points:
            current_boundary = next(fixture_boundary)
            prog.print(f"[red bold]Reducing boundary to: {current_boundary}")
            attempted_points = []
            continue
        attempted_points.append(roun_point)
        if task is None:
            task = prog.add_task(
                f"  Computing Core Label Position for V{vidx}",
                ran_point=ran_point,
                current_boundary=current_boundary,
            )
        else:
            prog.update(task, ran_point=ran_point, current_boundary=current_boundary)
        # Create a sphere (with some breathing room) at each of
        # the previously collected points of fixture contact on the core.
        # Then, test to see if our random point does not intersect with any
        # of the spheres. This ensures our point is in a clear area on the core.
        is_clear_fixtures = [
            not ran_point.intersect(Sphere(p, FIXTURE_SIZE + current_boundary))
            for p in points_on_core
        ]
        prog.update(task, results=is_clear_fixtures)
        if all(is_clear_fixtures):
            label_point = ran_point
            prog.update(task, visible=False)
            break

    print(
        f"[bold white]Found clear point: [/]{label_point} @ {current_boundary}[bold white] boundary."
    )

    text_el, res_vals = label_size(
        f"V{vidx}\n ",
        halign="center",
        size=min([current_boundary, 8]),
        width=min([current_boundary, 16]),
        depth=4,
    )
    inverse_label = Point3(-label_point.x, -label_point.y, -label_point.z)
    text_el = transform_to_point(
        text_el.copy(), dest_point=label_point, dest_normal=inverse_label.normalized()
    )
    core -= text_el
    return core


def assemble_vertex(vidx: int, debug=False):
    v_data = MODEL_DATA[vidx]

    base_fix = square(FIXTURE_SIZE, center=True)
    base_hole = square(FIXTURE_HOLE_SIZE, center=True)

    for edge, length, vector in v_data:
        point = Point3(*[inch(p) for p in vector])
        if debug:
            to_origin: LineSegment3 = point.connect(Point3(0, 0, 0))
            yield draw_segment(to_origin), None

        extrusion_height = inch(1) + CORE_SIZE / 2
        to_core_dist = point.magnitude() - CORE_SIZE

        z_dir = up if to_core_dist > 0 else down

        edge_length = math.ceil(length)
        print(
            f"Rendering Edge {edge}:{edge_length} @ {point} (H: {extrusion_height}, D: {to_core_dist})"
        )

        label_distance = CORE_SIZE / 2
        if to_core_dist > 0:
            label_distance += to_core_dist

        fix = up(to_core_dist - CORE_SIZE / 4)(linear_extrude(extrusion_height)(base_fix.copy()))
        fix -= z_dir(label_distance - 10)(
            forward(FIXTURE_SIZE / 2 - FIXTURE_WALL_THICKNESS / 4)(
                box_align(
                    label_size(
                        f"E{edge}\n{edge_length}",
                        halign="center",
                        depth=2,
                        size=8,
                        width=16,
                    )[0],
                    forward,
                )
            )
        )
        fix -= up(to_core_dist - CORE_SIZE / 2)(
            linear_extrude(extrusion_height - FIXTURE_WALL_THICKNESS)(base_hole.copy())
        )
        fix = transform_to_point(fix, dest_point=point, dest_normal=point.normalized())
        yield part()(fix), point


def assembly(vertex: int, *args, **kwargs):
    a = union()

    progress = kwargs.pop("progress", None)
    fixture_points: List[Point3] = []
    fixtures: List[OpenSCADObject] = []
    for fix, point in assemble_vertex(vertex, *args, **kwargs):
        fixtures.append(fix)
        if point:
            fixture_points.append(point)

    core = assemble_core(vertex, fixture_points, *args, **kwargs, progress=progress)
    for fix in fixtures:
        core += fix

    a += core
    if kwargs.get("debug", False):
        a += grid_plane(plane="xyz", grid_unit=inch(1))
    return a


def create_model(vidx: int, *args, **kwargs):
    a = assembly(vidx, *args, **kwargs)
    scad_render_to_file(a, file_header=f"$fn = {SEGMENTS};", include_orig_code=True)


def load_model(model_path: Path) -> utils.ModelInfo:
    global MODEL_DATA, MODEL_DATA_PATH
    MODEL_DATA_PATH = model_path
    data: utils.ModelInfo = pickle.loads(MODEL_DATA_PATH.read_bytes())
    MODEL_DATA = data["data"]
    return data["info"]


def generate(
    model_path: PathLike, vertices=tuple(), debug=False, render=False, keep=False, file_type="stl"
):
    """Generate joint model from given vertex."""
    info = load_model(model_path)
    if not any(vertices):
        vertices = tuple(range(info.num_vertices))
        print(f"[bold orange]Rendering: {info.num_edges} edges | {info.num_vertices} vertices")
        print(vertices)
    output_dir = ROOT.parent / "renders"
    output_dir.mkdir(exist_ok=True)
    with progress.Progress(
        utils.ParentSpinnerColumn(),
        progress.TextColumn("[bold white]{task.description}"),
        utils.ParentProgressColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        utils.ComputeTestResultsColumn(),
        progress.BarColumn(bar_width=None),
        utils.ComputeTestResultsTextColumn(),
        transient=True,
    ) as prog:
        task = prog.add_task("[green]Generating Models...", total=info.num_vertices)
        for vertex in vertices:
            if not render:
                return create_model(vertex, debug=debug)
            a = assembly(vertex, debug=debug, progress=prog)
            _, file_name = tempfile.mkstemp(suffix=".scad")
            file_path = Path(tempfile.gettempdir()) / file_name
            out_render = scad_render(a, file_header=f"$fn = {SEGMENTS};")
            file_path.write_text(out_render)
            render_name = f"joint-v{vertex}.{file_type}"
            render_path = output_dir / render_name
            proc = utils.openscad_cmd("-o", str(render_path), str(file_path))
            for line in iter(proc.stderr.readline, b""):
                outline = line.decode().rstrip("\n")
                prog.console.print(f"[grey42]{outline}")
            if keep:
                scad_path = render_path.with_suffix(".scad")
                shutil.move(file_path, scad_path)
            prog.update(task, advance=1)

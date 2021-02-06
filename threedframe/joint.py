# -*- coding: utf-8 -*-

"""3DFrame joint module."""

import json
import pickle
import shutil
import tempfile
from os import PathLike

import numpy as np
import vg
from rich import print, progress
from solid import *
from solid.utils import *
from sympy import Float, Plane, Point

from threedframe import utils
from threedframe.utils import ModelData, label_size

ROOT = Path(__file__).parent

MODEL_DATA_PATH = None
MODEL_DATA: Optional[ModelData] = None

LIB_DIR = ROOT / "lib"
MCAD = LIB_DIR / "MCAD"

TAU = 6.2831853071  # 2*PI
deg = lambda x: 360 * x / TAU

mcad = import_scad(str(Path(ROOT / "lib/MCAD")))
dotSCAD = import_scad(str(Path(ROOT / "lib/dotSCAD/src")))

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


def assemble_vertex(vidx: int, debug=False, extrusion_height=None, solid=False):
    v_data = MODEL_DATA.vertices[vidx]

    base_fix = square(FIXTURE_SIZE, center=True)

    for edge in v_data.edges:
        print("")
        point = Point3(*[inch(p) for p in edge.vector_ingress])
        if debug:
            to_origin: LineSegment3 = point.connect(Point3(0, 0, 0))
            yield draw_segment(to_origin), None

        extrusion_height = extrusion_height or inch(1.5)

        print("Fixture mag:", point.magnitude())
        print("Fixture mag - CORE:", point.magnitude() - CORE_SIZE)
        to_origin_line: LineSegment3 = point.connect(Point3(*ORIGIN))
        norm_direction = (point - ORIGIN).normalized()
        print("Normalized dir:", norm_direction)
        to_core_dist = to_origin_line.length

        # Transform to origin, but look towards the normalized direction but reflect (so its recv the edge).
        reflected_dir = norm_direction.reflect(norm_direction)
        midpoint = (
            Point3(extrusion_height / 3, extrusion_height / 3, extrusion_height / 3)
            * norm_direction
        )
        label_point = Point3(extrusion_height, extrusion_height, extrusion_height) * norm_direction
        pin_point = (
            Point3(extrusion_height / 2, extrusion_height / 2, extrusion_height / 2)
            * norm_direction
        )

        fix = base_fix.copy()
        inspect_fix = base_fix.copy()
        if not solid:
            fix = dotSCAD.hollow_out.hollow_out(shell_thickness=3)(fix)

        fix = linear_extrude(extrusion_height)(fix)
        inspect_fix = linear_extrude(extrusion_height)(inspect_fix)

        print(extrusion_height / 3)

        # Calc distance from origin (aka, joint vertex) to determine how much less of an edge we need.
        dist = Point(*ORIGIN).distance(Point(midpoint.x, midpoint.y, midpoint.z))
        print("Distance from start of fixture to origin:", dist)
        edge.length = edge.length - dist

        print(
            f"Rendering Edge {edge}:{edge.length_in}'' -> {MODEL_DATA.get_edge_target_vertex(edge).label} @ {point} (H: {extrusion_height}, D: {to_core_dist})"
        )

        fix = transform_to_point(fix, dest_point=midpoint, dest_normal=reflected_dir)
        inspect_fix = transform_to_point(
            inspect_fix, dest_point=midpoint, dest_normal=reflected_dir
        )

        inspect_data = None
        verts_by_face = None
        face_verts = None
        with utils.TemporaryScadWorkspace(
            scad_objs=[("fix", union()(inspect_fix), "stl")]
        ) as tmpdata:
            tmp_path, tmp_files = tmpdata
            utils.exec_pymesh(
                "collect_verts", tmp_files[0][-1].name, "out.json", host_mount=tmp_path
            )
            inspect_data = json.loads((tmp_path / "out.json").read_text())
            verts_by_face = inspect_data["verts_by_face"]
            face_verts = inspect_data["verts"]

        first_verts = [Point(i) for i in face_verts]

        first_face_plane = Plane(*first_verts)
        last_face_plane = None
        last_face_verts = None
        last_dist = 0
        for fidx, verts in verts_by_face:
            test_verts = [Point(v) for v in verts]
            test_plane = Plane(*test_verts)
            dist = first_face_plane.distance(test_plane)
            print(fidx, verts)
            print(f"first to {fidx}", dist)
            if abs(Float(dist)) >= abs(Float(last_dist)):
                last_dist = dist
                last_face_plane = test_plane
                last_face_verts = test_verts

        cp1 = Point(last_face_verts[0])
        fcp1 = first_verts[0]
        coplaner_points: List[Point] = [
            Point(i) for i in last_face_verts[1:] if Point.are_coplanar(cp1, Point(i), fcp1)
        ]
        print("Coplaner:", coplaner_points)
        cp2 = max(coplaner_points, key=lambda p: cp1.canberra_distance(p))

        face_midpoint = cp1.midpoint(cp2)

        if not solid:
            # pin hole for small nail or M3
            pz = translate([face_midpoint.x, face_midpoint.y, face_midpoint.z])(sphere(r=5))
            pz.modifier = "%"
            fix += pz
            for point in last_face_verts:
                p = translate(point)(sphere(r=5))
                p.modifier = "%"
                fix += p

        print("loaded inspect data:", inspect_data)

        if not solid:
            label = label_size(
                f"{MODEL_DATA.get_edge_target_vertex(edge).label}\n{round(edge.length_in, 2)}",
                halign="center",
                valign="center",
                depth=1.5,
                size=6,
                width=9,
                center=False,
            )[0]
            np_reflected_dir = np.array((reflected_dir.x, reflected_dir.y, reflected_dir.z))
            np_up_vec = np.array((0, 0, 1))
            perp_normal = vg.perpendicular(np_reflected_dir, np_up_vec)
            print("Perp Normal: ", perp_normal)

            targ_normal = BACK_VEC
            slide_dir = forward

            abs_y = abs(midpoint.y)
            abs_x = abs(midpoint.x)
            abs_z = abs(midpoint.z)
            if abs_y >= abs_x and abs_y >= abs_z:
                targ_normal = LEFT_VEC
                slide_dir = right

            label = transform_to_point(
                label, dest_point=label_point, dest_normal=targ_normal, src_normal=reflected_dir
            )
            label = slide_dir(extrusion_height / 4 + 1.2)(label)

            fix -= label

        if debug:
            fix.modifier = "#"
        yield fix, midpoint, inspect_data


def find_core_vertice_cubes(fixture_datasets):
    """Create cubes on each fixture vertice.

    This creates a cube on each vertex of every fixture on the face
    closest to origin. Then, the core is created by taking the convex
    hull of all the cubes.

    """
    core_vertice_cubes = []
    for datasets in fixture_datasets:
        vert_set = datasets["verts"]
        vert_pts_set = [Point(*p) for p in vert_set]
        missing_pt = utils.find_missing_rect_vertex(*vert_pts_set)
        vert_set.append(missing_pt)
        # Find midpoint of inner corners of fixture
        fp_1 = Point(*tuple(vert_set[0]))
        fp_2 = max([Point(*tuple(p)) for p in vert_set], key=lambda p: fp_1.canberra_distance(p))
        face_midpoint = fp_1.midpoint(fp_2)
        for vert in vert_set:
            # First face is the one closest to origin.
            face_norm = datasets["norms_by_face"]["0"]
            core_cube = color("red")(cube(1, center=True))
            vert_point = Point(*tuple(vert))
            # Scale corner point with reference to midpoint to 'inset' cubes into corners
            scaled_point = vert_point.scale(0.9575, 0.9575, 0.9575, pt=face_midpoint)
            core_cube = transform_to_point(
                core_cube, dest_point=tuple(scaled_point), dest_normal=tuple(face_norm)
            )
            core_vertice_cubes.append(core_cube)

    return core_vertice_cubes


def assembly(vertex: int, *args, **kwargs):
    a = union()

    progress = kwargs.pop("progress", None)
    debug = kwargs.get("debug", False)

    fixtures = list(assemble_vertex(vertex, debug=False, solid=False))
    normal_fixtures = [f[0] for f in fixtures]

    solid_fixture_data = list(assemble_vertex(vertex, debug=False, solid=True))
    solid_fixtures = [f[0] for f in solid_fixture_data]
    fixture_datas = [f[2] for f in solid_fixture_data]

    core_vertice_cubes = find_core_vertice_cubes(fixture_datas)

    core = hull()(*core_vertice_cubes)

    inspect_core = core.copy()
    inspect_joint = core.copy()
    for f in solid_fixtures:
        inspect_joint += f

    inspect_data = None
    scad_inspects = [
        ("core", union()(inspect_core), "stl"),
        ("joint", union()(inspect_joint), "stl"),
    ]
    with utils.TemporaryScadWorkspace(scad_objs=scad_inspects) as tmpdata:
        tmp_path, tmp_files = tmpdata
        core_files = tmp_files[0]
        joint_files = tmp_files[1]
        utils.exec_pymesh(
            "inspect_core",
            core_files[-1].name,
            joint_files[-1].name,
            "out.json",
            host_mount=tmp_path,
        )
        inspect_data = json.loads((tmp_path / "out.json").read_text())

    print("core inspect data:", inspect_data)
    face_verts = inspect_data["face_verts"]
    face_norm = Vector3(*inspect_data["face_norm"])
    face_verts = [Point(*v) for v in face_verts]

    # Use center of gravity instead of canberra distance b/c face verts could only be 3 points.
    face_midpoint = utils.find_center_of_gravity(*face_verts)

    if debug:
        # face points for text label
        for vert in [*face_verts, face_midpoint]:
            core += translate(vert)(color("red")(cube(1, center=True)))

    text_el, _ = label_size(
        f"{MODEL_DATA.vertices[vertex].label}",
        halign="center",
        valign="center",
        size=6,
        width=9,
        depth=0.5,
        center=True,
    )

    text_el = transform_to_point(
        text_el,
        dest_point=Point3(face_midpoint.x, face_midpoint.y, face_midpoint.z),
        dest_normal=face_norm.reflect(face_norm),
    )

    core -= text_el

    for f in normal_fixtures:
        if debug:
            a += f
        else:
            core += f

    # Debug Core Hull vertices
    if debug:
        core.modifier = "*"
        core = color("blue")(core)
        for vert_cube in core_vertice_cubes:
            vert_cube.modifier = "%"
            a += vert_cube

    a += core

    if kwargs.get("debug", False):
        a += grid_plane(plane="xyz", grid_unit=inch(1))
    return a


def create_model(vidx: int, *args, **kwargs):
    a = assembly(vidx, *args, **kwargs)
    scad_render_to_file(a, file_header=f"$fn = {SEGMENTS};", include_orig_code=True)


def load_model(model_path: Path) -> utils.ModelData:
    global MODEL_DATA, MODEL_DATA_PATH
    MODEL_DATA_PATH = model_path
    data: utils.ModelData = pickle.loads(MODEL_DATA_PATH.read_bytes())
    MODEL_DATA = data
    return data


def generate(
    model_path: PathLike, vertices=tuple(), debug=False, render=False, keep=False, file_type="stl"
):
    """Generate joint model from given vertex."""
    model_data = load_model(model_path)
    if not any(vertices) and not vertices == tuple([0]):
        vertices = tuple(range(model_data.num_vertices))
        print(
            f"[bold orange]Rendering: {model_data.num_edges} edges | {model_data.num_vertices} vertices"
        )
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
        task = prog.add_task("[green]Generating Models...", total=model_data.num_vertices)
        for vertex in vertices:
            # if not render:
            #     return create_model(vertex, debug=debug)
            a = assembly(vertex, debug=debug, progress=prog)
            _, file_name = tempfile.mkstemp(suffix=".scad")
            file_path = Path(tempfile.gettempdir()) / file_name
            out_render = scad_render(a, file_header=f"$fn = {SEGMENTS};")
            file_path.write_text(out_render)
            render_name = f"joint-v{vertex}.{file_type}"
            render_path = output_dir / render_name
            if render:
                proc = utils.openscad_cmd("-o", str(render_path), str(file_path))
                for line in iter(proc.stderr.readline, b""):
                    outline = line.decode().rstrip("\n")
                    prog.console.print(f"[grey42]{outline}")
            if keep or not render:
                scad_path = render_path.with_suffix(".scad")
                shutil.move(file_path, scad_path)
            prog.update(task, advance=1)

"""3DFrame joint module."""

import pickle
import shutil
import tempfile
from os import PathLike
from copy import deepcopy
from typing import Iterator

from rich import print, progress
from solid import *
from sympy import Point
from solid.utils import *

from threedframe import mesh as meshutil
from threedframe import utils
from threedframe.utils import ModelData, label_size
from threedframe.config import config
from threedframe.constant import Constants

ROOT = Path(__file__).parent

MODEL_DATA_PATH = None
MODEL_DATA: Optional[ModelData] = None


def locate_vertex_label_pos(
    target_fixture: utils.JointFixture, other_fixtures: List[utils.JointFixture]
) -> Tuple[Point3, Vector3, utils.MeshFace]:
    """Locate appropriate position for fixture label.

    First, we simply check for faces larger than then first face (closest to origin).
    This will provide us with one of the 'side' longer faces.

    Then, to accommodate overlapping fixtures (which normally may place a label "inside" the overlap,
    leading to it being removed later), we calculate the absolute midpoints of all other fixtures
    and ensure that the target face is at least a fixtures size length away from it.

    This ensures the label will always be visible and in the same place.

    """
    # first face is closest to origin.
    first_face = target_fixture.inspect_mesh.faces[0]
    # calculate the absolute midpoints for all other fixtures besides the target.
    other_centers = [f.inspect_mesh.calc_absolute_midpoint() for f in other_fixtures]

    last_area = first_face.area
    label_face = None
    for face in target_fixture.inspect_mesh.faces:
        if face.area > last_area:
            # ensure the taxicab distance ( Σ{x-dist, y-dist} ) is at least a fixture away.
            oth_boundaries = [
                face.centroid_point.taxicab_distance(f) > config.FIXTURE_SIZE for f in other_centers
            ]
            print("Fixture label face boundary checks:", oth_boundaries)
            if all(oth_boundaries):
                last_area = face.area
                label_face = face

    # now that we have found an appropriate face, find the center of it to place the label.
    face_midpoint = utils.find_center_of_gravity(
        *label_face.sympy_vertices, label_face.missing_rect_vertex
    )
    print("Label face area:", label_face.area)
    return Point3(*tuple(face_midpoint)), label_face.normal_vector, label_face


def assemble_vertex(vidx: int, debug=False, extrusion_height=None, solid=False):
    v_data = MODEL_DATA.vertices[vidx]

    base_fix = square(config.FIXTURE_SIZE, center=True)
    base_inner = square(config.FIXTURE_SIZE - 6, center=True)

    for edge in v_data.edges:
        print("")
        point = Point3(*[(p * Constants.INCH) for p in edge.vector_ingress])
        if debug:
            to_origin: LineSegment3 = point.connect(Point3(0, 0, 0))
            yield draw_segment(to_origin), None

        extrusion_height = extrusion_height or (1.5 * Constants.INCH)

        print("Fixture mag:", point.magnitude())
        print("Fixture mag - CORE:", point.magnitude() - config.CORE_SIZE)
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

        fix = base_fix.copy()
        inspect_fix = base_fix.copy()
        inner_fix = base_inner.copy()

        if not solid:
            fix = config.dotSCAD.hollow_out.hollow_out(shell_thickness=3)(fix)

        fix = linear_extrude(extrusion_height)(fix)
        inner_fix = linear_extrude(extrusion_height + 10)(inner_fix)
        inspect_fix = linear_extrude(extrusion_height)(inspect_fix)

        # Calc distance from origin (aka, joint vertex) to determine how much less of an edge we need.
        dist = Point(*ORIGIN).distance(Point(midpoint.x, midpoint.y, midpoint.z))
        print("Distance from start of fixture to origin:", dist)
        edge.length = edge.length - dist

        print(
            f"Rendering Edge {edge}:{edge.length_in}'' -> {MODEL_DATA.get_edge_target_vertex(edge).label} @ {point} (H: {extrusion_height}, D: {to_core_dist})"
        )

        fix = transform_to_point(fix, dest_point=midpoint, dest_normal=reflected_dir)
        inner_fix = transform_to_point(inner_fix, dest_point=midpoint, dest_normal=reflected_dir)
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
            inspect_data = meshutil.collect_verts(tmp_files[0][-1])
            verts_by_face = inspect_data["verts_by_face"]
            face_verts = inspect_data["verts"]

        if debug:
            fix.modifier = "#"
        yield utils.JointFixture(
            scad_object=fix,
            inspect_object=inspect_fix,
            inner_object=inner_fix,
            model_edge=edge,
            model_vertex=MODEL_DATA.get_edge_target_vertex(edge),
            dest_point=(
                midpoint.x,
                midpoint.y,
                midpoint.z,
            ),
            dest_normal=(
                reflected_dir.x,
                reflected_dir.y,
                reflected_dir.z,
            ),
            inspect_data=inspect_data,
        )


def label_fixtures(
    inspect_fixtures: List[utils.JointFixture], **kwargs
) -> Iterator[utils.JointFixture]:
    debug = kwargs.pop("debug", False)
    for fidx, fixture in enumerate(inspect_fixtures):
        label = label_size(
            f"{fixture.model_vertex.label}\n{round(fixture.model_edge.length_in, 2)}",
            halign="center",
            valign="center",
            depth=1.5,
            size=6,
            width=9,
            center=True,
        )[0]
        oth_fixtures = deepcopy(inspect_fixtures)
        oth_fixtures.pop(fidx)
        label_point, label_normal, label_face = locate_vertex_label_pos(fixture, oth_fixtures)

        if debug:
            # Create spheres to represent the corners used for finding the label pos.
            lcolor = utils.rand_rgb_color()
            label_verts = label_face.euclid_vertices
            rec_vert = label_face.missing_rect_vertex
            label_verts.append(Point3(rec_vert.x, rec_vert.y, rec_vert.z))
            for p in label_verts:
                fixture.scad_object += translate(tuple(p))(color(lcolor)(sphere(r=2)))

        label = transform_to_point(
            label,
            dest_point=label_point,
            dest_normal=label_normal.reflect(label_normal),
            src_normal=Point3(*fixture.dest_normal),
        )
        fixture.scad_object -= label
        yield fixture


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
            face_norm = datasets["norms_by_face"][0]
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
    # normal_fixtures = [f.scad_object for f in fixtures]
    fixtures = list(label_fixtures(fixtures, **kwargs))
    normal_fixtures = [f.scad_object for f in fixtures]
    inner_fixtures = [f.inner_object for f in fixtures]

    solid_fixture_data = list(assemble_vertex(vertex, debug=False, solid=True))
    solid_fixtures = [f.scad_object for f in solid_fixture_data]
    fixture_datas = [f.inspect_data for f in solid_fixture_data]

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
        inspect_data = meshutil.inspect_core(core_files[-1], joint_files[-1])

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
        depth=1.5,
        center=True,
    )

    text_el = transform_to_point(
        text_el,
        dest_point=Point3(face_midpoint.x, face_midpoint.y, face_midpoint.z),
        dest_normal=face_norm.reflect(face_norm),
    )

    core -= text_el

    fixture_union = union()
    for fidx, f in enumerate(normal_fixtures):
        if debug:
            a += f
        else:
            fixture_union += f

    for inner_fix in inner_fixtures:
        fixture_union -= hole()(inner_fix)

    core += fixture_union

    # Debug Core Hull vertices
    if debug:
        core.modifier = "*"
        core = color("blue")(core)
        for vert_cube in core_vertice_cubes:
            vert_cube.modifier = "%"
            a += vert_cube

    a += core

    if kwargs.get("debug", False):
        a += grid_plane(plane="xyz", grid_unit=Constants.INCH * 1)
    return a


def create_model(vidx: int, *args, **kwargs):
    a = assembly(vidx, *args, **kwargs)
    scad_render_to_file(a, file_header=f"$fn = {config.SEGMENTS};", include_orig_code=True)


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
            a = assembly(vertex, debug=debug, progress=prog)
            _, file_name = tempfile.mkstemp(suffix=".scad")
            file_path = Path(tempfile.gettempdir()) / file_name
            out_render = scad_render(a, file_header=f"$fn = {config.SEGMENTS};")
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

#! ./.direnv/python-3.9.0/bin/python
import math
import pickle
import random
import statistics
import tempfile
import shutil
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

import click
from euclid3 import Point3, LineSegment3, Sphere
from rich import print, progress
from solid import *
from solid.utils import *

import utils

ROOT = Path(__file__).parent

# Cybersticks pickeled model data.
MODEL_DATA_PATH = ROOT / "cybertruck" / "cyber_joints.pkl"

# MODEL_DATA: Dict[int, List[Tuple[int, int,Tuple[float, float, float]]]] = pickle.loads(MODEL_DATA_PATH.read_bytes())
MODEL_DATA: Dict[
    int, List[Tuple[int, float, Tuple[float, float, float]]]
] = pickle.loads(MODEL_DATA_PATH.read_bytes())

LIB_DIR = ROOT / "lib"
MCAD = LIB_DIR / "MCAD"

TAU = 6.2831853071  # 2*PI
deg = lambda x: 360 * x / TAU

mcad = import_scad("lib/MCAD")

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
    center: bool =False,
        do_resize=True
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
            text=l, halign=halign, valign=valign, font=font, spacing=spacing, size=size, direction=direction
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
    resize_vals = (width, 0, depth,)
    if do_resize:
        result = resize(resize_vals)(result)
    restvals = (0, (len(lines) - 1) * size / 2, 0)
    if any(restvals):
        result = translate(restvals)(result)
    return result, resize_vals


@dataclass
class Dimension:
    x: int = 0
    y: int = 0
    z: int = 0

    @property
    def as_list(self):
        return [self.x, self.y, self.z]

    def add(self, modifier: "Dimension"):
        self.x += modifier.x
        self.y += modifier.y
        self.z += modifier.z
        return self


class Axis(Enum):
    x = 0
    y = 1
    z = 2


def from_core(obj_size: int):
    return CORE_SIZE / 3 + obj_size / 2


def with_modifiers(
    base: Union[float, Sequence[float]], modifiers: Optional[Dimension] = None
) -> Sequence[float]:
    mods = modifiers or Dimension()
    base_dims = base
    if isinstance(base, float):
        base_dims = [base, base, base]
    base_dims = Dimension(*base_dims)
    base_dims.add(mods)
    return base_dims.as_list


def assemble_core(vidx: int, fixture_points: List[Point3], debug=False):
    a = union()
    # core: OpenSCADObject = mcad.boxes.roundedCube(CORE_SIZE, 15, False, True)
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
    with progress.Progress(
        progress.SpinnerColumn(),
        progress.TextColumn("[bold white]Computing Core Label Position", justify="right"),
            utils.ComputeTestResultsColumn(),
            progress.BarColumn(bar_width=None),
        progress.TextColumn("[bold white]Testing point: [gold1]{task.fields[ran_point]}[/gold1] [bold white]@ [bold cyan]{task.fields[current_boundary]}[white] boundary."),
    ) as prog:
        # task = prog.add_task("", start=False)
        task = None
        while True:
            ran_x = points_gauss()
            ran_y = points_gauss()
            ran_z = points_gauss()
            norm = 1 / math.sqrt(
                math.pow(ran_x, 2) + math.pow(ran_y, 2) + math.pow(ran_z, 2)
            )
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
                task = prog.add_task("", ran_point=ran_point, current_boundary=current_boundary)
            else:
                prog.update(task, ran_point=ran_point, current_boundary=current_boundary)
            # print(f"[italic grey70]Testing point: [bold]{ran_point}[/bold] @ [bold]{current_boundary}[/bold] boundary.")
            # Create a sphere (with some breathing room) at each of
            # the previously collected points of fixture contact on the core.
            # Then, test to see if our random point does not intersect with any
            # of the spheres. This ensures our point is in a clear area on the core.
            is_clear_fixtures = [
                not ran_point.intersect(Sphere(p, FIXTURE_SIZE + current_boundary)) for p in points_on_core
            ]
            prog.update(task, results=is_clear_fixtures)
            # prog.print(f"[italic grey50]Fixtures cleared: {' '.join(['[bold green]✔[/]' if i else '[bold red]𐄂[/]' for i in is_clear_fixtures])}")
            if all(is_clear_fixtures):
                label_point = ran_point
                break

    print(f"[bold white]Found clear point: [/]{label_point} @ {current_boundary}[bold white] boundary.")

    text_el, res_vals = label_size(f"V{vidx}\n ",
                         halign="center",
                         size=min([current_boundary, 8]),
                         width=min([current_boundary, 16]),
                         depth=4,
                         )
    # if debug:
    #     core.modifier = "%"
    # core.modifier = '%'
    # a.add(core)
    inverse_label = Point3(-label_point.x, -label_point.y, -label_point.z)
    text_el = transform_to_point(text_el.copy(), dest_point=label_point, dest_normal=inverse_label.normalized())
    # core -= resize(res_vals)(text_el)
    core -= text_el
    # core -= hole()(text_el)
    return core


def assemble_fit(
    hole_axis: Axis = Axis.y,
    rotation=None,
    rotations=None,
    dimension_modifiers: Optional[Dimension] = None,
    label=None,
):
    size = with_modifiers(FIXTURE_SIZE, dimension_modifiers)
    fit = mcad.boxes.roundedCube(size, 1, False, True)
    fit -= hole()(
        up(FIXTURE_SIZE / 2)(
            color("red")(
                linear_extrude(4, center=True)(
                    text(
                        f"E{label or ''}",
                        size=6,
                        direction="ltr",
                        halign="center",
                        valign="center",
                    )
                )
            )
        )
    )

    hole_dims_base = [FIXTURE_HOLE_SIZE, FIXTURE_HOLE_SIZE, FIXTURE_HOLE_SIZE]
    hole_dims_base[hole_axis.value] = FIXTURE_SIZE + 1

    hole_dims = with_modifiers(hole_dims_base, dimension_modifiers)
    hole_cube = cube(hole_dims, center=True)

    fit -= hole()(hole_cube)

    if rotation:
        return rotation(fit)
    if rotations:
        for r in rotations:
            fit = r(fit)
    return fit


# def assemble_vertex(vidx: int):
#     vert_data = MODEL_DATA[vidx]
#
#     # fix_base = None
#     eidxs = set()
#     for e1idx, e2idx, angle, euler, length in vert_data:
#         # if fix_base is None:
#         fix_base = forward(from_core(FIXTURE_SIZE))(assemble_fit(hole_axis=Axis.y, label=math.ceil(length)))
#         print(f"[V{vidx}]: E{e1idx} <=> E{e2idx} [@{angle}\u00b0] ({euler})")
#         if euler is None:
#             # 180deg angle
#             eidxs.add(e1idx)
#             eidxs.add(e2idx)
#             yield fix_base.copy()
#         else:
#             bangle = angle
#             if e1idx in eidxs or e2idx in eidxs:
#                 bangle = angle * -1
#             fix_base = rotate(bangle, euler)(fix_base.copy())
#             yield fix_base
#             eidxs.add(e1idx)
#             eidxs.add(e2idx)


# def assemble_vertex(vidx: int):
#     colors = iter(["red", "green", "pink", "cyan", "lime"])
#     vert_data = MODEL_DATA[vidx]
#     uniq_edges = set()
#     for item in vert_data:
#         uniq_edges.add(item[0])
#         uniq_edges.add(item[1])
#
#     fixture_map: Dict[int, OpenSCADObject] = {}
#
#     base_fix = square(FIXTURE_SIZE, center=True)
#     base_hole = square(FIXTURE_HOLE_SIZE, center=True)
#     base_fix = linear_extrude(CORE_SIZE / 2 + inch(1))(base_fix)
#     base_fix -= hole()(
#         up(CORE_SIZE / 2 + FIXTURE_WALL_THICKNESS)(linear_extrude()(base_hole))
#     )
#
#     def with_text(obj: OpenSCADObject, content: str):
#         text_el = linear_extrude(2, center=True)(
#             text(content, size=6, halign="center", valign="center")
#         )
#         text_el = color("black")(text_el)
#         text_el = up(CORE_SIZE/2 + inch(.5))(text_el)
#         text_el = rot_z_to_left(text_el)
#         text_el = up(CORE_SIZE / 2 + inch(.5))(text_el)
#         text_el = right(FIXTURE_HOLE_SIZE + 2)(text_el)
#         obj -= hole()(text_el)
#         return obj
#
#     # Mapping over corner vertice' edge CONSTRAINTS
#     for e1idx, e2idx, angle in vert_data:
#         fixture_map.setdefault(e1idx, with_text(base_fix.copy(), f"E{e1idx}"))
#         fixture_map.setdefault(e2idx, with_text(base_fix.copy(), f"E{e2idx}"))
#         print(f"Rotating E{e2idx} @ {angle}")
#         fixture_map[e2idx] = rotate(angle)(fixture_map[e2idx])
#         # if axis:
#         #     print(f"Rotating E{e1idx} @ {angle} by {axis}")
#         #     # fixture_map[e2idx] = multmatrix(m=axis.tolist()) + fixture_map[e2idx]
#         #     # fixture_map[e2idx] = rotate((angle, 0))(fixture_map[e2idx])
#         #     fixture_map[e2idx] = rotate(angle, axis)(fixture_map[e2idx])
#
#     for key, item in fixture_map.items():
#         # item = color(next(colors))(item)
#         # # item.modifier = "%"
#         # item = with_text(item, f"E{key}")
#         # # item.modifier = '%'
#         item.modifier = '#'
#         yield item


def assemble_vertex(vidx: int, debug=False):
    v_data = MODEL_DATA[vidx]

    base_fix = square(FIXTURE_SIZE, center=True)
    base_hole = square(FIXTURE_HOLE_SIZE, center=True)

    for edge, length, vector in v_data:
        point = Point3(*[inch(p) for p in vector])
        # point = Point3(*vector)
        # yield linear_extrude(20)(square([point.x, point.y, point.z], center=True))
        if debug:
            # fix_points = [
            #     Point3(point.x + FIXTURE_SIZE)
            # ]
            # fix_points[0].x = point + FIXTURE_SIZE
            # fix_points[1].y = point + FIXTURE_SIZE
            # fix_points[2].z = point + FIXTURE_SIZE
            core_sphere = Sphere(Point3(0, 0, 0), radius=CORE_SIZE)
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

        fix = up(to_core_dist - CORE_SIZE / 4)(
            linear_extrude(extrusion_height)(base_fix.copy())
        )
        # Fixture label
        # fix -= hole()(
        #     z_dir(label_distance - 10)(
        #         forward(FIXTURE_SIZE / 2 - FIXTURE_WALL_THICKNESS / 4)(
        #             box_align(
        #                 label_size(
        #                     f"E{edge}\n{edge_length}",
        #                     halign="center",
        #                     depth=2,
        #                     size=8,
        #                     width=16,
        #                 ),
        #                 forward,
        #             )
        #         )
        #     )
        # )
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
        # Fixture main hole
        # fix -= hole()(
        #     up(to_core_dist - CORE_SIZE / 2)(
        #         linear_extrude(extrusion_height - FIXTURE_WALL_THICKNESS)(
        #             base_hole.copy()
        #         )
        #     )
        # )
        fix -= up(to_core_dist - CORE_SIZE / 2)(
                linear_extrude(extrusion_height - FIXTURE_WALL_THICKNESS)(
                    base_hole.copy()
                )
            )


        # fix -= hole()(
        #     down(CORE_SIZE / 2 + FIXTURE_WALL_THICKNESS)(linear_extrude(point.magnitude())(base_hole.copy()))
        # )
        # fix.modifier = '#'
        # fix = transform_to_point(fix, dest_point=point, dest_normal=point.normalized())
        # yield fix
        fix = transform_to_point(fix, dest_point=point, dest_normal=point.normalized())
        # fix.modifier = '%'
        yield part()(fix), point


def assembly(vertex: int, *args, **kwargs):
    a = union()

    # # 90deg straight fixture
    # core += forward(from_core(FIXTURE_SIZE))(assemble_fit())
    #
    # # 7.259deg tilted left-side fixture
    # left_rotate = rotate(-7.259, FORWARD_VEC)
    # left_modifiers = Dimension(x=2)
    # left_fix = left(from_core(FIXTURE_SIZE) - 2)(assemble_fit(flip_hole_dir=True, rotation=left_rotate, dimension_modifiers=left_modifiers))
    # core += left_fix
    #
    # # 18.325deg tilted right-side fixture
    # right_rotate = rotate(-18.325, BACK_VEC)
    # right_modifiers = Dimension(x=4)
    # right_fix = right(from_core(FIXTURE_SIZE) - 4)(assemble_fit(flip_hole_dir=True, rotation=right_rotate, dimension_modifiers=right_modifiers))
    # core += right_fix

    # rot = rotate((56.33, -48.7122, 31.74))
    # core += rot(right(from_core(FIXTURE_SIZE))(assemble_fit(hole_axis=Axis.y)))

    # rot = rotate((2.54, 75.46, 101.16))
    # core += rot(forward(from_core(FIXTURE_SIZE))(assemble_fit(hole_axis=Axis.y)))

    # rot = rotate((-78.17, -10.38, -82.02))

    # 5 -> 59 (CENTER -> CENTER)
    # rotations = [
    #     rotate(45, RIGHT_VEC),
    #     rotate(78, FORWARD_VEC),
    #     rotate(95, UP_VEC),
    # ]
    # a += forward(from_core(FIXTURE_SIZE))(assemble_fit(hole_axis=Axis.x, rotations=rotations))
    # a += assemble_fit(hole_axis=Axis.x, rotation=rotate(1.15, (1, 0, 0)))

    # 5 -> 111 (CENTER TO LEFT)
    # rot = rotate(61.8887723350703 / 2, DOWN_VEC)
    # core += left(from_core(FIXTURE_SIZE))(assemble_fit(hole_axis=Axis.z, rotation=rot))
    # core += left(from_core(FIXTURE_SIZE))(assemble_fit(hole_axis=Axis.y, rotation=rot))

    # 5 -> 2 (CENTER TO RIGHT)
    # rot_r = rotate(51.98882315664463 / 2, DOWN_VEC)
    # core += right(from_core(FIXTURE_SIZE))(assemble_fit(hole_axis=Axis.x, rotation=rot_r))

    # E179 (V5 -> V59 CENTER)
    # af = forward(from_core(FIXTURE_SIZE))(assemble_fit(hole_axis=Axis.y))
    # a += af
    # for fixture in assemble_vertex(vertex):
    #     a += fixture

    #
    # # E175 (V5 -> V2 RIGHT)
    # bf = forward(from_core(FIXTURE_SIZE))(assemble_fit(hole_axis=Axis.y))
    # bf = rotate(-97)(bf)
    # bf = rotate(151, (-0.053081825375556946, 1.1089521646499634, -0.03287731483578682) )(bf)
    # # bf = rotate(29, FORWARD_VEC)(bf)
    # a += bf
    #
    # # E178 (V5 -> V111 LEFT)
    # cf = (forward(from_core(FIXTURE_SIZE))(assemble_fit(hole_axis=Axis.y)))
    # cf = rotate(95)(cf)
    # cf = rotate(-151,(-0.053081825375556946, 1.1089521646499634, -0.03287731483578682))(cf)
    # a += cf

    # a += rotate(90, RIGHT_VEC)(arc(CORE_SIZE + 50, start_degrees=209/2+90, end_degrees=360))
    #
    # primary = assemble_fit()
    # a += forward(50)(primary)
    #
    # b = forward(50)(primary.copy())
    # b = rotate(-97)(b)
    # b = rotate(29, FORWARD_VEC)(b)
    # a += b
    #
    # c = forward(50)(primary.copy())
    # c = rotate(95)(c)
    # c = rotate(29, BACK_VEC)(c)
    # a += c

    p0 = Point3(0, 0, 0)
    p1 = Point3(-9.395675659179688, 105.18434143066406, -13.352337837219238)
    p2 = Point3(-9.488700866699219, -67.73377990722656, -22.688980102539062)
    p3 = Point3(37.84366989135742, -1.52587890625e-05, 0.0)

    # p1n = Point3(9.395675659179688, -105.18434143066406, 13.352337837219238)
    points = [p0, p1, p2]

    # points = offset_points([p0, p1, p2], CORE_SIZE)
    # paths = vectors_between_points(points)
    # a += extrude_along_path(points, paths)

    # c = cube(1, True)
    # c = translate((p1.x, p1.y, p1.z))(c)
    # a += c

    # b = cube(1, True)
    # b = translate((p2.x, p2.y, p2.z))(b)
    # a += b
    # c = transform_to_point(c, )

    base_fix = square(FIXTURE_SIZE, center=True)
    base_hole = square(FIXTURE_HOLE_SIZE, center=True)

    # base_fix = rotate(99)(base_fix)
    # core += rotate(180)(translate((p1.x, p1.y, -p1.z))((transform_to_point(base_fix.copy(), p1, p1.normalized()))))
    # def get_dest_point(dest_normal: Point3):
    #     base = Point3(0, CORE_SIZE / 2 + inch(1), 0)
    #     result = base.copy()
    #     norm_points = ['x', 'y', 'z']
    #     norm_attr = max(norm_points, key=lambda k: abs(getattr(dest_normal,k)))
    #     if getattr(dest_normal, norm_attr) < 0:
    #         setattr(result, norm_attr, getattr(result, norm_attr) * -1)
    #         setattr(result, norm_attr, getattr(result, norm_attr) / 2)
    # if dest_normal.y < 0:
    #     result.y = result.y * -1
    # result.y = result.y / 2
    # return result

    # a += transform_to_point(base_fix.copy(), dest_point=get_dest_point(p1.normalized()), dest_normal=p1.normalized())
    ba = up(inch(1))(linear_extrude(p2.magnitude() - inch(1))(base_fix.copy()))
    ba -= hole()(
        down(CORE_SIZE / 2 + FIXTURE_WALL_THICKNESS)(
            linear_extrude(p2.magnitude())(base_hole.copy())
        )
    )

    # mag = inch(p1.magnitude())
    #
    # diff_s = (inch(1)*-1) - mag
    # diff_s = diff_s + mag
    # print(diff_s)

    # bb = up(p1.magnitude() - CORE_SIZE)(linear_extrude(inch(1) + CORE_SIZE / 2)(base_fix.copy()))
    # bb -= hole()(
    #     down(CORE_SIZE / 2 + FIXTURE_WALL_THICKNESS)(linear_extrude(p1.magnitude())(base_hole.copy()))
    # )
    #
    # bc = up(p3.magnitude() - CORE_SIZE)(linear_extrude(inch(1) + CORE_SIZE / 2)(base_fix.copy()))
    # bc -= hole()(
    #     down(CORE_SIZE / 2 + FIXTURE_WALL_THICKNESS)(linear_extrude(p3.magnitude())(base_hole.copy()))
    # )

    fixture_points: List[Point3] = []
    fixtures: List[OpenSCADObject] = []
    for fix, point in assemble_vertex(vertex, *args, **kwargs):
        # a += fix
        fixtures.append(fix)
        if point:
            fixture_points.append(point)

    core = assemble_core(vertex, fixture_points, *args, **kwargs)
    for fix in fixtures:
        core += fix

    # core += list(assemble_vertex(vertex))[0]
    # v_data = MODEL_DATA[vertex]
    # for edge, vector in v_data:
    #     c = cube(20, center=True)
    #     # c = translate(vector)(c)
    #     c = transform_to_point(c, vector)
    #     a += c

    # a += transform_to_point(ba, dest_point=p2, dest_normal=p2.normalized())
    # a += transform_to_point(bb, dest_point=p1, dest_normal=p1.normalized())
    # a += transform_to_point(bc, dest_point=p3, dest_normal=p3.normalized())

    # a += transform_to_point(base_fix.copy(), dest_point=p1, dest_normal=p1.normalized())
    # a += transform_to_point(base_fix.copy(), dest_point=p3, dest_normal=p3.normalized())

    # core += transform_to_point(base_fix.copy(), p2, p2.normalized())

    a += core
    if kwargs.get('debug', False):
        a += grid_plane(plane="xyz", grid_unit=inch(1))
    return a


def create_model(vidx: int, *args, **kwargs):
    a = assembly(vidx, *args, **kwargs)
    scad_render_to_file(a, file_header=f"$fn = {SEGMENTS};", include_orig_code=True)


@click.command()
@click.option('-d', '--debug', is_flag=True, default=False)
@click.option('-r', '--render', is_flag=True, default=False)
@click.option('-k', '--keep', is_flag=True, default=False, help="Keep SCAD Files.")
@click.option('-f', '--file-type', default='stl', help="Exported file type.", )
@click.argument('vertices', type=int, nargs=-1)
def generate(vertices, debug=False, render=False, keep=False, file_type='stl'):
    """Generate joint model from given vertex."""
    output_dir = ROOT / 'renders'
    for vertex in vertices:
        if not render:
            return create_model(vertex, debug=debug)
        a = assembly(vertex, debug=debug)
        _, file_name = tempfile.mkstemp(suffix='.scad')
        file_path = Path(tempfile.gettempdir()) / file_name
        out_render = scad_render(a, file_header=f"$fn = {SEGMENTS};")
        file_path.write_text(out_render)
        render_name = f"joint-v{vertex}.{file_type}"
        render_path = output_dir / render_name
        utils.openscad_cmd('-o', str(render_path), str(file_path))
        if keep:
            scad_path = render_path.with_suffix('.scad')
            shutil.move(file_path, scad_path)


if __name__ == "__main__":
    generate()

from typing import TYPE_CHECKING, List, Tuple, Union, Iterator

import attr
import solid as sp
import sympy as S
import solid.extensions.legacy.utils as sputils
from solid.core.object_base import OpenSCADObject

from threedframe import utils
from threedframe.scad.interfaces import CoreMeta

if TYPE_CHECKING:
    from threedframe.models import MeshFace
    from threedframe.scad.interfaces import FixtureMeta


@attr.s(auto_attribs=True)
class Core(CoreMeta):
    @staticmethod
    def find_inner_face_midpoint(points: List[S.Point]) -> Tuple[S.Point, List[S.Point]]:
        """Find midpoint of inner (closest to core) face."""
        # Analyzed faces return 3 points, so calculate the 'missing' one.
        missing_pt = utils.find_missing_rect_vertex(*points)
        points.append(missing_pt)
        # Find midpoint of inner (core facing) face.
        face_midpoint = S.centroid(*points)
        return face_midpoint, points

    def create_vertex_cube(
        self,
        face: "MeshFace",
        face_midpoint: S.Point,
        vertex: S.Point,
        *,
        color: Union[str, Tuple[int, ...]] = "red",
    ) -> OpenSCADObject:
        # First face is nearest to origin.
        face_norm = face.normal
        cube_color = sp.color(color) if isinstance(color, str) else sp.color(c=color)
        cube_obj = cube_color(sp.cube(1, center=True))
        # Scale corner point with reference to midpoint to 'inset' cubes into corners
        scaled_point = vertex.scale(0.9575, 0.9575, 0.9575, pt=face_midpoint)
        cube_obj = sputils.transform_to_point(
            cube_obj, dest_point=tuple(scaled_point), dest_normal=face_norm
        )
        return cube_obj

    def create_fixture_inner_vertex_cubes(
        self,
        fixture: "FixtureMeta",
        **kwargs,
    ) -> Iterator[OpenSCADObject]:
        solid_mesh = self.meshes[fixture.params.label]
        face = solid_mesh.faces[0]
        vertices = [v.as_sympy for v in face.vertices]
        face_midpoint, all_vertices = self.find_inner_face_midpoint(vertices)
        for vertex in all_vertices:
            yield self.create_vertex_cube(face, face_midpoint, vertex, **kwargs)

    def create_hull_cubes(self) -> Iterator[OpenSCADObject]:
        color_gen = utils.rand_color_generator()
        for fix in self.fixtures:
            yield from self.create_fixture_inner_vertex_cubes(fix, color=next(color_gen))


class CoreDebugCubes(Core):
    def create_fixture_inner_vertex_cubes(
        self,
        fixture: "FixtureMeta",
        **kwargs,
    ) -> Iterator[OpenSCADObject]:
        solid_mesh = self.meshes[fixture.params.label]
        face = solid_mesh.faces[0]
        vertices = [v.as_sympy for v in face.vertices]
        face_midpoint, all_vertices = self.find_inner_face_midpoint(vertices)
        for vertex in all_vertices:
            yield self.create_vertex_cube(face, face_midpoint, vertex, **kwargs)
        yield sputils.transform_to_point(
            sp.cube(1, center=True), dest_point=tuple(face_midpoint), dest_normal=face.normal
        )

    def assemble(self):
        fixture_vertex_cubes = list(self.create_hull_cubes())
        obj = sp.union()(*fixture_vertex_cubes)
        self.scad_object = obj

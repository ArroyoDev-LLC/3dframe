from typing import TYPE_CHECKING, List, Tuple, Iterator

import attr
import solid as sp
import sympy as S
from solid import utils as sputils

from threedframe import utils
from threedframe.models.mesh import analyze_scad
from threedframe.scad.fixture import Fixture, SolidFixture
from threedframe.scad.interfaces import CoreMeta

if TYPE_CHECKING:
    from threedframe.models import MeshFace


@attr.s(auto_attribs=True)
class Core(CoreMeta):
    @staticmethod
    def create_solid_fixture(fixture: Fixture):
        params = fixture.params
        fix = SolidFixture(params=params)
        fix.assemble()
        return fix

    @staticmethod
    def find_inner_face_midpoint(points: List[S.Point]) -> Tuple[S.Point, List[S.Point]]:
        """Find midpoint of inner (closest to core) face."""
        # Analyzed faces return 3 points, so calculate the 'missing' one.
        missing_pt = utils.find_missing_rect_vertex(*points)
        points.append(missing_pt)
        # Find midpoint of inner (core facing) face.
        point_a = points[0]
        point_b = max(points, key=lambda p: point_a.canberra_distance(p))
        face_midpoint = point_a.midpoint(point_b)
        return face_midpoint, points

    def create_vertex_cube(
        self, face: "MeshFace", face_midpoint: S.Point, vertex: S.Point
    ) -> sp.OpenSCADObject:
        # First face is nearest to origin.
        face_norm = face.normal
        cube_obj = sp.color("red")(sp.cube(1, center=True))
        # Scale corner point with reference to midpoint to 'inset' cubes into corners
        scaled_point = vertex.scale(0.9575, 0.9575, 0.9575, pt=face_midpoint)
        cube_obj = sputils.transform_to_point(
            cube_obj, dest_point=tuple(scaled_point), dest_normal=tuple(face_norm)
        )
        return cube_obj

    def create_fixture_inner_vertex_cubes(self, fixture: Fixture) -> Iterator[sp.OpenSCADObject]:
        solid_fix = self.create_solid_fixture(fixture)
        solid_mesh = analyze_scad(solid_fix.scad_object)
        face = solid_mesh.faces[0]
        vertices = [v.as_sympy for v in face.vertices]
        face_midpoint, all_vertices = self.find_inner_face_midpoint(vertices)
        for vertex in all_vertices:
            yield self.create_vertex_cube(face, face_midpoint, vertex)

    def create_hull_cubes(self) -> Iterator[sp.OpenSCADObject]:
        for fix in self.fixtures:
            yield from self.create_fixture_inner_vertex_cubes(fix)

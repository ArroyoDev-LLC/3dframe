from typing import Tuple

import attr
import solid as sp
import sympy as S
from solid import utils as sputils
from euclid3 import Point3 as EucPoint3
from euclid3 import Vector3 as EucVector3
from pydantic.main import BaseModel

from threedframe.config import config
from threedframe.models import ModelEdge, ModelVertex
from threedframe.constant import Constants, PlanarConstants
from threedframe.scad.interfaces import FixtureMeta


class FixtureParams(BaseModel):
    source_edge: "ModelEdge"
    source_vertex: "ModelVertex"

    @property
    def source_coords(self) -> Tuple[float, ...]:
        return tuple((p * Constants.INCH) for p in self.source_edge.vector_ingress)

    @property
    def source_point(self) -> S.Point:
        return S.Point(*self.source_coords)

    @property
    def source_euclid_point(self) -> EucPoint3:
        return EucPoint3(*self.source_coords)

    @property
    def target_vertex(self) -> "ModelVertex":
        return self.source_edge.target_vertex

    @property
    def extrusion_height(self) -> float:
        return config.fixture_length

    @property
    def distance_to_origin(self) -> S.Mul:
        return self.source_point.distance(self.source_point.origin)

    @property
    def line_to_origin(self) -> S.Line3D:
        return S.Line(self.source_point, self.source_point.origin)

    @property
    def direction_to_origin(self) -> EucVector3:
        """Vector from origin <- point."""
        norm_direction = (self.source_euclid_point - PlanarConstants.ORIGIN.as_euclid).normalized()
        return norm_direction

    @property
    def vector_from_origin(self) -> EucVector3:
        """Vector from origin -> point."""
        return self.direction_to_origin.reflect(self.direction_to_origin)

    @property
    def midpoint(self) -> EucPoint3:
        """Fixture midpoint.

        This is the midpoint of the "end result"
        fixture, NOT between the source point and origin.

        """
        generic_coord = self.extrusion_height / 3
        generic_midpoint = EucPoint3(generic_coord, generic_coord, generic_coord)
        return generic_midpoint * self.direction_to_origin

    @property
    def midpoint_as_sympy(self) -> S.Point:
        return S.Point(self.midpoint.x, self.midpoint.y, self.midpoint.z)

    @property
    def edge_length_from_fixture(self) -> float:
        """Distance from origin to fixture midpoint.

        This is the adjusted length of the (end result)
        physical "edge" with accommodations for the length
        of material between the eventual core and fixture wall.

        """
        dist = PlanarConstants.ORIGIN.as_sympy.distance(self.midpoint_as_sympy)
        return float(dist)

    @property
    def adjusted_edge_length(self) -> float:
        """Final length of physical edge that accommodates core+fixture material."""
        return self.source_edge.length - self.edge_length_from_fixture

    @property
    def adjusted_edge_length_as_label(self) -> str:
        """Adjusted edge length properly formatted for label."""
        length_in = self.adjusted_edge_length / Constants.INCH
        val = str(round(length_in, 1))
        return val.rstrip(".0")

    @property
    def label(self) -> str:
        return "\n".join(
            (
                self.target_vertex.label,
                self.adjusted_edge_length_as_label,
                self.source_vertex.label,
            )
        )


@attr.s(auto_attribs=True)
class Fixture(FixtureMeta):
    def create_base(self) -> sp.OpenSCADObject:
        return sp.square(config.fixture_size + config.fixture_shell_thickness, center=True)

    def do_extrude(self, obj: sp.OpenSCADObject):
        obj -= sp.resize(tuple([config.fixture_hole_size] * 3))(obj.copy())
        obj = sp.linear_extrude(self.params.extrusion_height)(obj)
        return obj

    def do_transform(self, obj: sp.OpenSCADObject):
        obj = sputils.transform_to_point(
            obj, dest_point=self.params.midpoint, dest_normal=self.params.vector_from_origin
        )
        return obj


@attr.s(auto_attribs=True)
class SolidFixture(Fixture):
    def do_extrude(self, obj: sp.OpenSCADObject):
        obj = sp.linear_extrude(self.params.extrusion_height)(obj)
        return obj

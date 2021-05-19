import abc
from typing import TYPE_CHECKING, List, Tuple, Optional

import attr
import solid as sp
import sympy as S
from euclid3 import Point3 as EucPoint3
from euclid3 import Vector3 as EucVector3

from threedframe.constant import Constants, PlanarConstants

if TYPE_CHECKING:
    from threedframe.models import ModelEdge

    from .fixture import Fixture


@attr.s(auto_attribs=True)
class FixtureParams:
    source_edge: "ModelEdge"

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
    def extrusion_height(self) -> float:
        return 1.5 * Constants.INCH

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


@attr.s(auto_attribs=True)
class ScadMeta(abc.ABC):
    scad_object: Optional[sp.OpenSCADObject] = None

    @abc.abstractmethod
    def assemble(self):
        raise NotImplementedError


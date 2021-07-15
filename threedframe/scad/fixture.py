from typing import TYPE_CHECKING, Type, Tuple

import attr
import solid as sp
import sympy as S
import solid.extensions.bosl2.std as bosl2
import solid.extensions.legacy.utils as sputils
from loguru import logger
from euclid3 import Point3 as EucPoint3
from euclid3 import Vector3 as EucVector3
from pydantic.main import BaseModel
from solid.core.object_base import OpenSCADObject

from threedframe.config import config
from threedframe.models import ModelEdge, ModelVertex
from threedframe.constant import Constants, PlanarConstants
from threedframe.scad.label import FixtureLabel, FixtureLabelParams
from threedframe.scad.interfaces import FixtureMeta

if TYPE_CHECKING:
    from threedframe.scad.interfaces import LabelMeta


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
    def max_avail_extrusion_height(self) -> float:
        """Max available extrusion height.

        This is the theoretical 'longest'
        a fixture can be given the length of its edge.

        On a singular edge/support, two fixtures
        at this height would be touching.

        """
        return self.adjusted_edge_length / 2

    @property
    def extrusion_height(self) -> float:
        if config.fixture_length > self.max_avail_extrusion_height:
            # extrude to max available height w/
            # a 3mm buffer between source+target fixture.
            logger.warning(
                "[{}@{}] reduced height to: {}",
                self.source_label,
                self.target_label,
                self.max_avail_extrusion_height - 1.5,
            )
            return self.max_avail_extrusion_height - 1.5
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
        """Fixture origin-facing face midpoint.

        This is the midpoint of the "end result"
        fixture, NOT between the source point and origin.

        Midpoint of the face closest to origin.

        """
        generic_coord = config.fixture_length / 3
        generic_midpoint = EucPoint3(generic_coord, generic_coord, generic_coord)
        return generic_midpoint * self.direction_to_origin

    @property
    def target_face_midpoint(self) -> EucPoint3:
        coord = EucPoint3(*[self.extrusion_height] * 3) * self.direction_to_origin
        return coord + self.midpoint

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
        # count for source+target diff
        edge_diff = self.edge_length_from_fixture * 2
        return self.source_edge.length - edge_diff

    @property
    def adjusted_edge_length_as_label(self) -> str:
        """Adjusted edge length properly formatted for label."""
        length_in = self.adjusted_edge_length / Constants.INCH
        val = str(round(length_in, 1))
        return val.rstrip(".0")

    @property
    def source_label(self) -> str:
        return self.source_vertex.label

    @property
    def target_label(self) -> str:
        return self.target_vertex.label

    @property
    def vidx_label(self) -> str:
        """Alpha vertex source label + source vertex index."""
        return f"{self.source_label} ({self.source_vertex.vidx})"

    @property
    def length_label(self) -> str:
        return self.adjusted_edge_length_as_label

    @property
    def label_depth(self) -> str:
        return config.fixture_shell_thickness / 1.9

    @property
    def label(self) -> str:
        return "\n".join(
            (
                self.target_vertex.label,
                self.adjusted_edge_length_as_label,
                self.source_vertex.label,
            )
        )

    def create_tag(self, name: str) -> str:
        """Create BOSL2 tag name.

        Args:
            name: name of fixture tag.

        Returns:
            Tag with name unique to fixture.

        """
        return f"fixture_{self.source_label}-{self.target_label}_{name}"

    @property
    def base_tag(self) -> str:
        return self.create_tag("base")

    @property
    def hole_tag(self) -> str:
        return self.create_tag("hole")

    @property
    def labels_tag(self) -> str:
        return self.create_tag("labels")


@attr.s(auto_attribs=True)
class Fixture(FixtureMeta):
    label_builder: Type["LabelMeta"] = FixtureLabel

    def create_label(self, content: str) -> OpenSCADObject:
        params = FixtureLabelParams(content=content, target=self)
        label = self.label_builder(params=params)
        label.assemble()
        return label.scad_object

    @property
    def source_label_obj(self) -> OpenSCADObject:
        return bosl2.fwd(self.params.extrusion_height / 4)(
            self.create_label(self.params.source_label)
        )

    @property
    def target_label_obj(self) -> OpenSCADObject:
        return bosl2.back(self.params.extrusion_height / 3)(
            self.create_label(self.params.target_label)
        )

    @property
    def length_label_obj(self) -> OpenSCADObject:
        return bosl2.back(0.5)(self.create_label(self.params.adjusted_edge_length_as_label))

    def build_labels(self):
        yield self.source_label_obj
        yield self.target_label_obj
        yield self.length_label_obj

    def create_hole(self) -> OpenSCADObject:
        return bosl2.cube(
            [config.fixture_hole_size, config.fixture_hole_size, self.params.extrusion_height + 1],
            anchor=bosl2.CENTER,
            _tags=self.params.hole_tag,
        )

    def create_fillet(self, **kwargs) -> OpenSCADObject:
        fillet: OpenSCADObject = bosl2.interior_fillet(
            l=config.fixture_size, r=config.fixture_size / 4.5, _tags="fix_fillet", **kwargs
        )
        return fillet

    def create_base(self) -> OpenSCADObject:
        base: OpenSCADObject = bosl2.cube(
            [config.fixture_size, config.fixture_size, self.params.extrusion_height],
            anchor=bosl2.BOTTOM,
            _tags=self.params.base_tag,
        )
        return base

    def add_fillets(self, obj: OpenSCADObject) -> OpenSCADObject:
        y_fillet = self.create_fillet(spin=180, orient=bosl2.RIGHT)
        x_fillet = self.create_fillet(orient=bosl2.FRONT)
        obj.add(bosl2.yflip_copy()(bosl2.position([0, -1, -1])(y_fillet)))
        obj.add(bosl2.xflip_copy()(bosl2.position([1, 0, -1])(x_fillet)))
        return obj

    def add_labels(self, obj: OpenSCADObject) -> OpenSCADObject:
        right_att = bosl2.attach(bosl2.RIGHT)
        left_att = bosl2.attach(bosl2.LEFT)
        for lbl_obj in self.build_labels():
            obj.add(right_att(lbl_obj.copy()))
            obj.add(left_att(lbl_obj.copy()))
        return obj

    def do_extrude(self, obj: OpenSCADObject):
        hole = self.create_hole()
        obj.add(bosl2.attach(bosl2.CENTER)(hole))
        obj = self.add_fillets(obj)
        obj = self.add_labels(obj)
        diff_tags = " ".join([self.params.hole_tag, self.params.labels_tag])
        return bosl2.diff(diff_tags, self.params.base_tag)(obj)

    def do_transform(self, obj: sp.core.object_base.OpenSCADObject):
        obj = sputils.transform_to_point(
            obj, dest_point=self.params.midpoint, dest_normal=self.params.vector_from_origin
        )
        return obj


@attr.s(auto_attribs=True)
class SolidFixture(Fixture):
    def create_base(self) -> OpenSCADObject:
        obj = super().create_base()
        solid_tags = self.params.base_tag + " fixture_solid"
        obj.params.update(_tags=solid_tags)
        return obj

    def do_extrude(self, obj: sp.core.object_base.OpenSCADObject):
        return obj


@attr.s(auto_attribs=True)
class FixtureLabelDebug(Fixture):
    def do_extrude(self, obj: OpenSCADObject):
        hole = self.create_hole()
        obj.add(bosl2.attach(bosl2.CENTER)(hole))
        right_att = bosl2.attach(bosl2.RIGHT)
        left_att = bosl2.attach(bosl2.LEFT)
        for lbl_obj in self.build_labels():
            obj.add(right_att(lbl_obj.copy()))
            obj.add(left_att(lbl_obj.copy()))
        return bosl2.diff(self.params.hole_tag, self.params.base_tag)(obj)

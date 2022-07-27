import math
from enum import Enum
from typing import TYPE_CHECKING, Type, Tuple, Union, Optional, DefaultDict

import attr
import numpy as np
import solid as sp
import sympy as S
import open3d as o3d
import solid.extensions.bosl2 as bosl2
import solid.extensions.legacy.utils as sputils
from loguru import logger
from euclid3 import Point3 as EucPoint3
from euclid3 import Vector3 as EucVector3
from pydantic.main import BaseModel
from solid.core.object_base import OpenSCADObject

from threedframe import utils
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

    def angle_between(self, other: "FixtureParams") -> float:
        """Calculate angle between self and other fixture."""
        angle_rad = self.direction_to_origin.angle(other.direction_to_origin)
        return math.degrees(angle_rad)


class FixtureMeshType(str, Enum):
    BASE = "base"
    HOLE = "hole"
    SHELL = "shell"


@attr.s(auto_attribs=True)
class Fixture(FixtureMeta):
    label_builder: Type["LabelMeta"] = FixtureLabel
    meshes: DefaultDict[FixtureMeshType, Optional[o3d.geometry.TriangleMesh]] = attr.ib(
        factory=utils.default_nonedict
    )

    def copy(self) -> "Fixture":
        copied = super().copy(label_builder=self.label_builder)
        copied.extrusion_height = self.extrusion_height
        return copied

    def create_label(self, content: str) -> OpenSCADObject:
        params = FixtureLabelParams(content=content, target=self)
        label = self.label_builder(params=params)
        label.assemble()
        return label.scad_object

    @property
    def source_label_obj(self) -> OpenSCADObject:
        height_multi = self.params.extrusion_height / self.extrusion_height
        return bosl2.fwd(self.extrusion_height / 4 * height_multi)(
            self.create_label(self.params.source_label)
        )

    @property
    def target_label_obj(self) -> OpenSCADObject:
        height_multi = self.params.extrusion_height / self.extrusion_height
        return bosl2.back(self.extrusion_height / 3 * height_multi)(
            self.create_label(self.params.target_label)
        )

    @property
    def length_label_obj(self) -> OpenSCADObject:
        return bosl2.back(0.5)(self.create_label(self.final_edge_length_label))

    def build_labels(self):
        yield self.source_label_obj
        yield self.target_label_obj
        yield self.length_label_obj

    def create_hole(self) -> OpenSCADObject:
        return bosl2.cube(
            [config.fixture_hole_size, config.fixture_hole_size, self.params.extrusion_height],
            anchor=bosl2.BOTTOM,
            _tags="fixture_hole " + self.params.hole_tag,
        )

    def create_fillet(self, **kwargs) -> OpenSCADObject:
        fillet: OpenSCADObject = bosl2.interior_fillet(
            l=config.fixture_size, r=config.fixture_size / 4.5, _tags="fix_fillet", **kwargs
        )
        return fillet

    def create_base(self) -> OpenSCADObject:
        base: OpenSCADObject = bosl2.cube(
            [config.fixture_size, config.fixture_size, self.extrusion_height],
            anchor=bosl2.BOTTOM,
            _tags="fixture_base " + self.params.base_tag,
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

    def add_hole(self, obj: OpenSCADObject) -> OpenSCADObject:
        hole = self.create_hole()
        obj.add(bosl2.attach(bosl2.TOP, overlap=self.hole_length)(hole))
        return obj

    def subtract_parts(self, obj: OpenSCADObject) -> OpenSCADObject:
        diff_tags = " ".join([self.params.hole_tag, self.params.labels_tag])
        return bosl2.diff(diff_tags, self.params.base_tag)(obj)

    def do_extrude(self, obj: OpenSCADObject):
        obj = self.add_hole(obj)
        obj = self.add_fillets(obj)
        obj = self.add_labels(obj)
        obj = self.subtract_parts(obj)
        return obj

    def do_transform(self, obj: sp.core.object_base.OpenSCADObject):
        obj = sputils.transform_to_point(
            obj, dest_point=self.params.midpoint, dest_normal=self.params.vector_from_origin
        )
        return obj

    def create_hole_obj(self) -> OpenSCADObject:
        """Cuboid of inner fixture hole."""
        obj = self.create_base()
        obj = self.add_hole(obj)
        obj = self.do_transform(obj)
        obj = bosl2.hide(self.params.base_tag)(obj)
        return obj

    def create_hole_mesh(self):
        obj = self.create_hole_obj()
        return self.compute_mesh(obj)

    def create_base_mesh(self):
        obj = self.create_base()
        obj = self.do_transform(obj)
        return self.compute_mesh(obj)

    def create_shell_mesh(self):
        obj = self.create_base()
        obj = self.add_hole(obj)
        obj = self.subtract_parts(obj)
        obj = self.do_transform(obj)
        return self.compute_mesh(obj)

    def _lazy_mesh(self, mesh_type: FixtureMeshType):
        if self.meshes[mesh_type] is None:
            self.meshes[mesh_type] = getattr(self, f"create_{mesh_type}_mesh")()
        return self.meshes[mesh_type]

    @staticmethod
    def serialize_mesh(
        fixture: "Fixture", mesh_type: FixtureMeshType
    ) -> Tuple[str, utils.SerializableMesh, FixtureMeshType]:
        attr_name = f"create_{mesh_type}_mesh"
        mesh = getattr(fixture, attr_name)()
        fixture.meshes[mesh_type] = mesh
        return fixture.name, utils.SerializableMesh(mesh), mesh_type

    @property
    def base_mesh(self) -> o3d.geometry.TriangleMesh:
        return self._lazy_mesh(FixtureMeshType.BASE)

    @property
    def hole_mesh(self) -> o3d.geometry.TriangleMesh:
        return self._lazy_mesh(FixtureMeshType.HOLE)

    @property
    def shell_mesh(self) -> o3d.geometry.TriangleMesh:
        return self._lazy_mesh(FixtureMeshType.SHELL)

    def extend_fixture_base(self, offset: Union[int, float]):
        """Extend fixture extrusion height."""
        prev_sup_wall_pt = self.support_endpoint.copy()
        self.extrusion_height += offset
        logger.info("[{}] extending base: +{}mm -> {}mm", self.name, offset, self.extrusion_height)
        vec_diff = self.support_endpoint - prev_sup_wall_pt
        rel_vec = np.asarray(list(vec_diff), dtype=np.float64)
        logger.debug("[{}] relatively translated meshes by {}", self.name, rel_vec)
        for mesh_t in FixtureMeshType.__members__.values():
            if self.meshes[mesh_t] is not None:
                self.meshes[mesh_t] = self.meshes[mesh_t].translate(rel_vec, relative=True)

    def compare_to_other(self, other: "Fixture") -> Tuple[float, float]:
        angle_bet = self.params.angle_between(other.params)
        dist_between = self.support_endpoint.distance(other.support_endpoint)
        logger.debug(
            "[{}] <-> [{}] @ {:.2f}deg & {:.2f}mm", self.name, other.name, angle_bet, dist_between
        )
        return angle_bet, dist_between

    def does_intersect_other_support(self, other: "Fixture") -> bool:
        do_intersect = self.shell_mesh.is_intersecting(other.hole_mesh)
        logger.info(
            "intersection in Base[{}] & Hole[{}] -> {}", self.name, other.name, do_intersect
        )
        return do_intersect


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


@attr.s(auto_attribs=True)
class FixtureSimpleDebug(Fixture):
    def add_fillets(self, obj: OpenSCADObject) -> OpenSCADObject:
        return obj
